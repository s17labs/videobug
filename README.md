# videobug — show a video bug to an AI that can't watch video

[![version](https://img.shields.io/github/v/tag/s17labs/videobug?label=version)](https://github.com/s17labs/videobug/releases)
[![license](https://img.shields.io/github/license/s17labs/videobug)](LICENSE)
[![python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](videobug.py)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-orange)](https://ffmpeg.org)
[![local](https://img.shields.io/badge/100%25_local-no_cloud_no_account-brightgreen)](#privacy)

**Your coding agent can't watch video. Stop narrating bugs at it.**

videobug turns a phone screen recording into an *agent-readable report*: key
frames your agent can **see**, plus the animation described as **text**
(freeze runs, motion spikes). 100% local — no account, no upload, no video
model, one Python file.

Works with **OpenCode**, **Claude Code**, **Cursor**, **Codex** — anything that
reads Markdown + images. See [docs/agent-setup.md](docs/agent-setup.md).

## Demo

```console
$ python3 videobug.py --latest \
    --app "demo checkout" \
    --expected "smooth loading spinner" --actual "spinner stalls mid-animation"
using latest recording: /sdcard/DCIM/ScreenRecorder/bug.mp4
videobug done: bug_videobug/report.md
  clip 8.0s 480x800 -> 16 sampled, 8 key frames, 1 freeze(s), 2 jank spike(s)
  agent reads: bug_videobug/report.md (+ frames/*.png as images)
```

| 0.00s — start | 3.50s — freeze, 1.5s still | 5.00s — motion spike |
|---|---|---|
| ![start](docs/assets/shot-start.png) | ![freeze](docs/assets/shot-freeze.png) | ![spike](docs/assets/shot-spike.png) |

Full annotated walkthrough: [docs/example.md](docs/example.md).

## The problem

Coding agents live in the terminal, and the terminal can't see your screen.
For an animation bug you become the lossy adapter: which screen, what moved on
which frame, what the stutter looked like. The fix is only as good as your
description — and the description is the weakest part of the loop.

videobug removes you from the middle. The recording *is* the bug report:
timestamps, key frames, and a motion timeline the agent can act on.

## What the agent gets

Each run writes `<name>_videobug/` next to your video:

| File | Contents |
|---|---|
| `report.md` | Expected/actual, key moments with embedded frames, freeze/jank analysis, fix instructions |
| `frames/` | ≤10 key PNGs: `start`, `freeze-start/end`, `motion-spike`, `sample`, `end` |
| `motion.csv` | Per-frame timestamp + motion score (0–255) + flag |
| `frames_all/` | Every sampled frame, for deep dives |
| `meta.json` | Probe info + events, `"network": "none"` by design |

<details>
<summary>Peek at a real <code>report.md</code> motion section</summary>

```md
## Motion analysis (text version of the animation)

- median motion: 4.5/255 per step at 2fps; low = still, high = big visual change.
- FREEZE x1: 1.5s around 3.5s
- JANK spikes x2: 3.0s (79.1), 5.0s (79.6)
```

</details>

## Quickstart

**Chat-only (no terminal):** install the skill once ([setup](docs/agent-setup.md)),
then record 5–15s of the bug and just say:

> `/videobug` the login button flickers. Expected: smooth fade. Actual: flashes twice.

The agent finds your newest recording itself, converts, looks at the frames,
and fixes the code. It only ever asks for plain words: app + screen, expected,
actual.

<details>
<summary>Manual flow (terminal)</summary>

```sh
git clone https://github.com/s17labs/videobug.git && cd videobug
pip install -r requirements.txt
# plus a system ffmpeg: apk add ffmpeg / apt install ffmpeg / brew install ffmpeg

python3 videobug.py --latest --app "..." --expected "..." --actual "..."
# then: read <name>_videobug/report.md + attach frames/*.png as images
```

</details>

## videobug vs the alternatives

| | **videobug** | Screen-recorder SaaS (Clipy…) | Browser MCPs (FlowLens, ThinkRun) | Raw `ffmpeg` stills |
|---|---|---|---|---|
| Price / account | Free OSS, none needed | Freemium, sign-in | OSS, some need tokens/links | Free, none |
| Uploads your video to a cloud | **Never** | Yes | Sometimes (share links) | Never |
| Works fully offline | **Yes** | No | Partly | Yes |
| Phone-app recordings (any mp4) | **Yes** | Yes | No, browser only | Manual |
| Console / network / DOM context | No | Partial | **Yes** | No |
| Agent skill included | **Yes** | Yes | Yes | No |

Pick videobug when the bug is *visual*, the app is *native mobile*, and the
recording *stays on the device*. Pick a browser MCP when you need console and
network logs from a web app.

## How it works

```
mp4 → ffprobe → ffmpeg (2fps stills) → Pillow frame-diffs →
      freeze runs + motion spikes → report.md + frames/ + motion.csv
```

No NumPy, no ML model, zero network calls (verify:
`grep -rEn "urllib|requests|http\.|socket" videobug.py`). The *coding model
looking at the key frames* does the explaining — this tool just converts time
into text + stills. Heuristics are tuned for 5–15s clips; longer videos work
but stay capped at `--max-frames`.

## Tuning

| Goal | Flags |
|---|---|
| Subtle fast jank | `--fps 4 --max-frames 12` |
| Noisy screen, false freezes | `--freeze-thresh 5 --freeze-secs 0.8` |
| Fewer tokens | `--width 480` |
| Exact input file | `videobug.py bug.mp4 …` instead of `--latest` |

## FAQ

<details>
<summary>Does it upload my video anywhere?</summary>

No. There is no network code in the project — no requests library, no sockets,
no API keys. Airplane-mode safe after the one-time `ffmpeg` install.
</details>

<details>
<summary>My harness can't see images either — pure text?</summary>

Works anyway. `report.md` + `motion.csv` describe the animation fully in text
(timestamps, freeze durations, spike scores); the PNGs are a bonus.
</details>

<details>
<summary>iPhone / desktop recordings?</summary>

Any `.mp4` / `.mov` / `.mkv` / `.webm`. On non-Android machines `--latest`
searches the workspace and temp dirs instead of `/sdcard`.
</details>

<details>
<summary>Does it transcribe narration?</summary>

No — that would need a heavy local model or a cloud API. Put the narration in
`--expected` / `--actual` instead; one line each beats a transcript.
</details>

<details>
<summary>Long videos?</summary>

They run, but the report stays capped at `--max-frames` key moments. For
animation bugs, trim to the 5–15s around the bug — smaller report, better fix.
</details>

## Privacy

Your recording never leaves the machine. The only files videobug writes are
the report directory next to your video. Staged `/sdcard` copies
(`vb_in_*.mp4`) and `*_videobug/` dirs are git-ignored by default.

## Contributing

Issues and PRs welcome. House rules: stdlib + Pillow only, zero network
dependencies, keep 5–15s clips first-class. One concern per PR.

## License

MIT — see [LICENSE](LICENSE). © 2026 [s17 Labs](https://s17labs.github.io).
