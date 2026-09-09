# Example: stalled slider, 6.5-second clip

Scenario: a slider glides across the screen, stalls dead for ~2s mid-screen, then resumes.
The recording is 8s, 480x800. Command:

```sh
python3 videobug.py --latest \
  --app "demo player" \
  --expected "slider glides across smoothly" \
  --actual "slider stalls dead mid-screen for 2s"
```

Output:

```
videobug done: bug_videobug/report.md
  clip 6.5s 480x800 -> 13 sampled, 10 key frames, 1 freeze(s), 0 jank spike(s)
  agent reads: bug_videobug/report.md (+ frames/*.png as images)
```

## What the agent sees

| 2.00s — gliding | 3.00s — stalled dead | 6.00s — resumed |
|---|---|---|
| ![gliding](assets/shot-start.png) | ![stalled](assets/shot-freeze.png) | ![resumed](assets/shot-resume.png) |

## What the agent reads (`report.md`, trimmed)

```md
## Motion analysis (text version of the animation)

- median motion: 3.9/255 per step at 2fps; low = still, high = big visual change.
- FREEZE x1: 2.5s around 3.0s
- JANK spikes x0: none
```

One sentence the agent can now state before touching code: *"The slider
stalls dead for ~2s around 3.0s, then resumes."* From there it greps for the
slider/transition code instead of
guessing from a paragraph.
