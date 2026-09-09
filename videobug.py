#!/usr/bin/env python3
"""videobug — explain a screen-recording to an AI coding agent that can't watch video.

100% local. Deps: system ffmpeg/ffprobe + Pillow. No network, no numpy, no cloud.

Flow:
  1. Android Screen Recorder -> bug.mp4 (copy to /workspace, never work on /sdcard directly)
  2. python3 videobug.py bug.mp4 --expected "..." --actual "..." --out ./bug_videobug
  3. Agent reads report.md + selected frame PNGs (it understands images, not video)
     and fixes the code. Temporal info (freeze/jank) is converted to text scores.

Typical animation bug: 5-15s clip, 2 fps, max 10 frames keeps the report small.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------- helpers

def find_bin(name: str) -> str:
    # Prefer a vendored ./bin/ binary (offline), fall back to system PATH (apk ffmpeg).
    local = SCRIPT_DIR / "bin" / name
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(f"missing dependency: '{name}' not found. Install once with: apk add ffmpeg")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe_video(ffmpeg_probe: str, src: Path) -> dict:
    p = run([ffmpeg_probe, "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(src)])
    if p.returncode != 0:
        raise SystemExit(f"ffprobe failed: {p.stderr.strip()[:500]}")
    info = json.loads(p.stdout or "{}")
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), streams[0] if streams else {})
    fmt = info.get("format", {})
    try:
        duration = float(fmt.get("duration") or video.get("duration") or 0)
    except ValueError:
        duration = 0.0
    return {
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "codec": video.get("codec_name", "?"),
        "fps_raw": video.get("avg_frame_rate") or video.get("r_frame_rate") or "?",
        "size_bytes": int(fmt.get("size") or src.stat().st_size),
    }


def extract_frames(ffmpeg: str, src: Path, dest_dir: Path, fps: float, width: int) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Clean previous extraction.
    for old in sorted(dest_dir.glob("f-*.png")):
        old.unlink()
    vf = f"fps={fps},scale=w='min(iw\\,{width})':h=-2"
    p = run([ffmpeg, "-hide_banner", "-y", "-i", str(src),
             "-vf", vf, "-q:v", "3", str(dest_dir / "f-%04d.png")])
    if p.returncode != 0:
        raise SystemExit(f"ffmpeg frame extract failed: {p.stderr.strip()[-800:]}")
    frames = sorted(dest_dir.glob("f-*.png"))
    if not frames:
        raise SystemExit("ffmpeg extracted 0 frames — is the input a valid mp4?")
    return frames


def diff_scores(frames: list[Path]) -> list[float]:
    """Mean absolute per-pixel diff (0-255) between consecutive frames, Pillow only."""
    from PIL import Image, ImageChops, ImageStat  # local import: keeps --help fast

    scores = [0.0]  # first frame has no predecessor
    prev = None
    for fp in frames:
        img = Image.open(fp).convert("L")
        img.thumbnail((160, 160))  # small proxy: fast + enough for motion
        if prev is None:
            prev = img
            continue
        if img.size != prev.size:
            img = img.resize(prev.size)
        diff = ImageChops.difference(img, prev)
        mean = ImageStat.Stat(diff).mean[0]
        scores.append(float(mean))
        prev = img
    return scores


def detect_events(scores: list[float], fps: float,
                  freeze_thresh: float, freeze_secs: float) -> tuple[list[dict], list[dict]]:
    """Return (freezes, janks). Pure-heuristic, tuned for 5-15s animation clips."""
    freezes, janks = [], []
    if len(scores) < 2:
        return freezes, janks
    step = 1.0 / fps
    # --- freezes: run of low-diff frames lasting >= freeze_secs
    # Note: from_idx is the first *still* frame itself (not the cut leading into it).
    run_start = None
    for i in range(1, len(scores)):
        if scores[i] < freeze_thresh:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                dur = (i - run_start) * step
                if dur >= freeze_secs:
                    freezes.append({"from_idx": run_start, "to_idx": i - 1,
                                    "dur": round(dur, 2)})
                run_start = None
    if run_start is not None:
        dur = (len(scores) - run_start) * step
        if dur >= freeze_secs:
            freezes.append({"from_idx": run_start, "to_idx": len(scores) - 1,
                            "dur": round(dur, 2)})
    # --- janks: spikes well above the median motion
    motion = scores[1:]
    med = statistics.median(motion) if motion else 0.0
    peak_cut = max(med * 3.0, freeze_thresh * 4.0, 8.0)
    for i in range(1, len(scores)):
        if scores[i] >= peak_cut:
            janks.append({"idx": i, "score": round(scores[i], 1)})
    # de-duplicate adjacent jank spikes (keep the local max)
    dedup: list[dict] = []
    for j in janks:
        if dedup and j["idx"] - dedup[-1]["idx"] == 1:
            if j["score"] > dedup[-1]["score"]:
                dedup[-1] = j
        else:
            dedup.append(j)
    return freezes, dedup


def select_keys(n: int, scores: list[float], freezes: list[dict],
                janks: list[dict], max_frames: int) -> list[tuple[int, str]]:
    """Pick (frame_idx, label) pairs, always including first+last. Ranked, then time-sorted."""
    picks: dict[int, str] = {0: "start", n - 1: "end"}
    for f in freezes:
        picks.setdefault(f["from_idx"], f"freeze-start {f['dur']}s")
        picks.setdefault(f["to_idx"], "freeze-end")
    for j in janks[:max_frames]:
        picks.setdefault(j["idx"], f"motion-spike {j['score']}")
    # Fill remaining slots uniformly so smooth animations still get coverage.
    # Skip indices inside freeze ranges (they're already represented by
    # freeze-start/freeze-end) to avoid redundant stills.
    if len(picks) < min(max_frames, n):
        import math
        frozen: set[int] = set()
        for f in freezes:
            frozen.update(range(f["from_idx"], f["to_idx"] + 1))
        need = min(max_frames, n) - len(picks)
        stride = max(1, math.floor(n / (need + 1)))
        for idx in range(stride, n - 1, stride):
            if len(picks) >= min(max_frames, n):
                break
            if idx in frozen:
                continue
            picks.setdefault(idx, "sample")
    # Enforce cap: keep start/end + highest-score frames.
    if len(picks) > max_frames:
        ranked = sorted(picks, key=lambda i: (i in (0, n - 1), scores[i] if i < len(scores) else 0),
                        reverse=True)[:max_frames]
        picks = {i: picks[i] for i in ranked}
    return sorted(picks.items())


# Where Android screen recordings usually land (FUSE, read-only is fine for search).
# Order matters only for the integer tiebreak; newest mtime always wins.
CANDIDATE_DIRS = [
    Path("/sdcard/DCIM/ScreenRecorder"),
    Path("/sdcard/Movies"),
    Path("/sdcard/Download"),
    Path("/sdcard/DCIM/Camera"),
    Path("/workspace"),
    Path("/tmp/opencode"),
]
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}


def find_latest_recording() -> Path | None:
    """Newest video file across candidate dirs (recursive, skips *_videobug outputs)."""
    best: Path | None = None
    best_mtime = -1.0
    for d in CANDIDATE_DIRS:
        if not d.is_dir():
            continue
        try:
            files = [p for p in d.rglob("*") if p.is_file()
                     and p.suffix.lower() in VIDEO_EXTS
                     and "_videobug" not in p.parts
                     and "frames" not in p.parts]
        except (PermissionError, OSError):
            continue
        for p in files:
            try:
                mt = p.stat().st_mtime
            except OSError:
                continue
            if mt > best_mtime:
                best_mtime, best = mt, p
    return best


# ---------------------------------------------------------------- main

def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="videobug",
        description="Convert an Android screen recording into an agent-readable report (local only).")
    ap.add_argument("input", nargs="?", default="",
                    help="input video; omit (or pass --latest) to auto-use newest recording")
    ap.add_argument("--latest", action="store_true",
                    help="auto-pick the newest recording from ScreenRecorder/Movies/Download/workspace")
    ap.add_argument("--out", default="", help="output dir (default: <input-stem>_videobug/ in cwd)")
    ap.add_argument("--fps", type=float, default=2.0, help="frames/sec to extract (default 2)")
    ap.add_argument("--max-frames", type=int, default=10, help="max key frames in report (default 10)")
    ap.add_argument("--width", type=int, default=720, help="max frame width px (default 720)")
    ap.add_argument("--expected", default="", help="one line: what should happen")
    ap.add_argument("--actual", default="", help="one line: what actually happens")
    ap.add_argument("--app", default="", help="app/screen name, e.g. 'PebbleDo home list'")
    ap.add_argument("--freeze-thresh", type=float, default=3.0,
                    help="mean-diff below this counts as still (0-255, default 3)")
    ap.add_argument("--freeze-secs", type=float, default=0.5,
                    help="still run this long counts as FREEZE (default 0.5s)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.latest or not args.input:
        found = find_latest_recording()
        if found is None:
            print("error: no recordings found.\n"
                  "hint: record on Android first (quick-settings -> Screen Recorder, 5-15s),\n"
                  "then re-run. Searched: ScreenRecorder, Movies, Download, /workspace.",
                  file=sys.stderr)
            return 2
        src = found
        print(f"using latest recording: {src}", file=sys.stderr)
    else:
        src = Path(args.input)
    if not src.is_file():
        print(f"error: input not found: {src}\n"
              f"hint: record first, or run with --latest to auto-pick the newest recording.",
              file=sys.stderr)
        return 2
    staged = src
    if str(src).startswith("/sdcard"):
        # Stage into /workspace (FUSE is slow + non-executable); keep original untouched.
        staged = Path.cwd() / f"vb_in_{src.stem}.mp4"
        try:
            shutil.copy2(src, staged)
            print(f"staged copy: {src} -> {staged}", file=sys.stderr)
        except OSError as e:
            print(f"warning: staging copy failed ({e}); reading in place.", file=sys.stderr)
            staged = src
    out = Path(args.out) if args.out else Path(f"{src.stem}_videobug")
    if out.exists() and any(out.iterdir()):
        print(f"error: output dir not empty: {out}  (use --out <empty-dir>)", file=sys.stderr)
        return 2

    ffmpeg = find_bin("ffmpeg")
    ffprobe = find_bin("ffprobe")

    meta = probe_video(ffprobe, staged)
    all_dir = out / "frames_all"
    frames = extract_frames(ffmpeg, staged, all_dir, args.fps, args.width)
    scores = diff_scores(frames)
    freezes, janks = detect_events(scores, args.fps, args.freeze_thresh, args.freeze_secs)
    keys = select_keys(len(frames), scores, freezes, janks, args.max_frames)

    # Copy selected frames with timestamped names.
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    key_files: list[tuple[float, str, str, float]] = []  # (t, label, filename, score)
    for idx, label in keys:
        t = round(idx / args.fps, 2)
        dest = frames_dir / f"frame-{t:06.2f}s-{label.split()[0]}.png"
        shutil.copy2(frames[idx], dest)
        key_files.append((t, label, dest.name, round(scores[idx], 1)))

    # motion.csv (every extracted frame)
    with open(out / "motion.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "t_sec", "motion_0_255", "flag"])
        freeze_idxs: set[int] = set()
        for f in freezes:
            freeze_idxs.update(range(f["from_idx"], f["to_idx"] + 1))
        jank_idxs = {j["idx"] for j in janks}
        for i in range(len(frames)):
            flag = "freeze" if i in freeze_idxs else ("jank" if i in jank_idxs else "")
            w.writerow([i, round(i / args.fps, 2), round(scores[i], 1), flag])

    with open(out / "meta.json", "w") as fh:
        json.dump({"input": src.name, "created_utc": datetime.now(timezone.utc).isoformat(),
                   "fps_extract": args.fps, "frames_extracted": len(frames),
                   "video": meta, "freezes": freezes, "janks": janks,
                   "tool": "videobug-local", "network": "none"}, fh, indent=2)

    # report.md — this is what the agent reads.
    lines = [
        f"# videobug: {src.name}",
        "",
        f"App/screen: {args.app or '(fill in)'}",
        f"Expected: {args.expected or '(one line: what should happen)'}",
        f"Actual: {args.actual or '(one line: what actually happens)'}",
        "",
        (f"Clip: {meta['duration']:.1f}s, {meta['width']}x{meta['height']}, "
         f"{meta['codec']}, {len(frames)} frames sampled at {args.fps:g}fps "
         f"→ {len(key_files)} key frames below. 100% local, no upload."),
        "",
        "## Key moments (look at these images in order)",
        "",
    ]
    for t, label, fname, sc in key_files:
        lines.append(f"### [{t:.2f}s] {label} (motion {sc})")
        lines.append(f"![](frames/{fname})")
        lines.append("")
    lines += [
        "## Motion analysis (text version of the animation)",
        "",
        f"- median motion: {statistics.median(scores[1:]) if len(scores) > 1 else 0.0:.1f}/255 per step "
        f"at {args.fps:g}fps; low = still, high = big visual change.",
    ]
    if freezes:
        lines.append(f"- FREEZE x{len(freezes)}: " + "; ".join(
            f"{f['dur']}s around {(f['from_idx']/args.fps):.1f}s" for f in freezes))
    else:
        lines.append("- FREEZE x0: no still run ≥ "
                     f"{args.freeze_secs:g}s (threshold {args.freeze_thresh:g}).")
    lines.append(f"- JANK spikes x{len(janks)}: " + (
        ", ".join(f"{(j['idx']/args.fps):.1f}s ({j['score']})" for j in janks[:8]) or "none"))
    lines += [
        "",
        "## For the fixing agent",
        "1. Describe the visible bug in one sentence using the timestamps above.",
        "2. Grep the repo for the screen/widget named above; map the timestamp to the animation/transition code.",
        f"3. Full timeline: `motion.csv`. All frames: `frames_all/` ({len(frames)} PNGs).",
        "4. Keep the fix minimal; re-record the same flow and re-run videobug to compare.",
        "",
        "<!-- generated locally by tools/videobug/videobug.py — safe to paste into any agent -->",
        "",
    ]
    (out / "report.md").write_text("\n".join(lines))

    print(f"videobug done: {out}/report.md")
    print(f"  clip {meta['duration']:.1f}s {meta['width']}x{meta['height']} "
          f"-> {len(frames)} sampled, {len(key_files)} key frames, "
          f"{len(freezes)} freeze(s), {len(janks)} jank spike(s)")
    print(f"  agent reads: {out}/report.md  (+ frames/*.png as images)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
