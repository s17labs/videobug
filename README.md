# videobug — show a video bug to an AI that can't watch video

100% local. Turns a phone screen recording into an agent-readable report:
key frames (PNG, the agent *can* see) + motion analysis as text (freeze/jank).

No cloud, no video model, no upload. Deps: `ffmpeg`/`ffprobe` + `Pillow`.

Built for giving animation-bug feedback (flicker, stall, jank, frozen
transitions) to AI coding agents whose harness accepts images but not video.

## Install

```sh
git clone https://github.com/s17labs/videobug.git
cd videobug

# one-time system setup (then airplane-mode safe):
apk add ffmpeg            # Alpine / PRoot
# or: sudo apt install ffmpeg   # Debian/Ubuntu
# or: brew install ffmpeg       # macOS
pip install -r requirements.txt
```

## Easiest flow — no terminal (chat only, OpenCode)

Install the skill + command once:

```sh
cp -r skills/videobug ~/.config/opencode/skills/
cp commands/videobug.md ~/.config/opencode/commands/
```

Then:

1. Record on Android (quick-settings → Screen Recorder, 5–15s of the bug).
2. In the agent chat, just say (or `/videobug`):
   > The login button flickers. Expected: smooth fade. Actual: flashes twice.
3. The agent does the rest: finds your newest recording itself (`--latest`),
   converts, looks at the frames, fixes the code.

You never type a path or a command. If it needs anything, it asks only for:
app + screen name, one line expected, one line actual.

## Manual flow (terminal)

```sh
# Omit the filename to auto-use your newest recording
# (searches ScreenRecorder/Movies/Download/workspace on Android):
python3 videobug.py --latest \
  --app "app + screen name" \
  --expected "what should happen" \
  --actual "what actually happens"

# Or point at a file explicitly:
python3 videobug.py bug.mp4 --app "..." --expected "..." --actual "..."

# Then give the agent the report + frames:
#   - read <name>_videobug/report.md
#   - attach <name>_videobug/frames/*.png as images
```

## What you get in `<name>_videobug/`

* `report.md` — what the agent reads: expected/actual, key moments with embedded
  frames, motion analysis (FREEZE runs, JANK spikes), fix instructions.
* `frames/` — ≤10 key PNGs: `start`, `freeze-start/end`, `motion-spike`, `sample`, `end`.
* `motion.csv` — per-frame timestamp + motion score (0–255) + flag.
* `frames_all/` — every sampled frame (for deep dives).
* `meta.json` — probe info + events, `"network": "none"` by design.

## Tuning

```sh
python3 videobug.py bug.mp4 --fps 4 --max-frames 12        # subtle fast jank
python3 videobug.py bug.mp4 --freeze-thresh 5 --freeze-secs 0.8  # noisy screen
python3 videobug.py bug.mp4 --width 480                    # fewer tokens
```

## Limits

* Silent: no audio transcription (stays local + light). Narrate via `--expected/--actual`.
* Heuristic motion, not semantic understanding — the *coding model looking at the
  key frames* does the explaining; this tool just converts time → text + stills.
* Browser-extension tools (FlowLens/ThinkRun/Clipy) give console+network for web;
  this gives frames+motion for native mobile apps, offline.

## Verify offline

```sh
grep -rEn "urllib|requests|http\.|socket" videobug.py || echo "no network calls"
```

## Layout

```
videobug.py              # the converter (stdlib + Pillow only)
skills/videobug/         # OpenCode agent skill (this repo's chat flow)
commands/videobug.md     # OpenCode /videobug command
requirements.txt         # pillow
```

## License

MIT — see [LICENSE](LICENSE).
