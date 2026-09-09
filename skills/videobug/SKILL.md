---
name: videobug
description: Turn a phone screen recording into a local agent-readable bug report (key frames plus freeze/jank analysis) for animation and UI bugs. The user never touches the terminal.
---

## What I do

The user shows me a video of an app bug and I handle everything: find the
recording, convert it locally (no upload), look at the key frames, and fix the
code. The user only records and describes expected vs actual in words.

## When to use me

Use when the user attaches/shares a video, names a `.mp4`/`.mov`/`.mkv`, says
`/videobug`, or describes an animation bug (flicker, stall, jank, frozen
transition) on Android + AndCode/OpenCode.

## Workflow — I do all terminal work, the user does none

1. **Find the video (me, not the user).** If the user gave a path, use it. If
   they attached a file, resolve where the harness saved it. Otherwise run with
   `--latest` — the script auto-picks the newest recording from
   ScreenRecorder/Movies/Download/workspace itself:
   `python3 <videobug-repo>/videobug.py --latest --app "<app+screen>" --expected "<one line>" --actual "<one line>"`
   If expected/actual/app are missing, ask the user for those three things in
   plain words (no paths, no commands) and then proceed.
2. **Convert.** Deps are system `ffmpeg`/`ffprobe` + Pillow
   (`apk add ffmpeg`, `pip install pillow` — one-time, then offline). The
   script stages `/sdcard` files into `/workspace` itself and writes
   `<stem>_videobug/` with `report.md`, `frames/` (≤10 key PNGs), `motion.csv`,
   `frames_all/`, `meta.json`.
3. **Look.** Read `<stem>_videobug/report.md` and view `frames/*.png` as images
   (native vision) in timestamp order. State the bug in one sentence with
   timestamps before touching code.
4. **Fix.** Grep the repo for the named screen/widget, map the timestamp to the
   animation/transition code, keep the fix minimal, then ask the user to
   re-record the same flow and re-run (again via `--latest`) to compare.

## Rules

- Never ask the user to run terminal commands or copy files — do it with my
  own tools.
- Stay local: never upload video or frames. The script makes zero network
  calls (verify: `grep -rEn "urllib|requests|http\.|socket" videobug.py`).
- Keep reports small (default `--fps 2 --max-frames 10`); use `--fps 4
  --max-frames 12` only for fast subtle jank.
- The script is `videobug.py` at this repo's root; install with
  `pip install -r requirements.txt` plus a system `ffmpeg`.
