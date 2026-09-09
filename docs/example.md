# Example: stalled spinner, 8-second clip

Scenario: tapping checkout shows a spinner that visibly stalls mid-animation.
The recording is 8s, 480x800. Command:

```sh
python3 videobug.py --latest \
  --app "demo checkout" \
  --expected "smooth loading spinner" \
  --actual "spinner stalls mid-animation"
```

Output:

```
videobug done: bug_videobug/report.md
  clip 8.0s 480x800 -> 16 sampled, 8 key frames, 1 freeze(s), 2 jank spike(s)
  agent reads: bug_videobug/report.md (+ frames/*.png as images)
```

## What the agent sees

| 0.00s — start | 3.50s — freeze-start (1.5s still) | 5.00s — motion spike |
|---|---|---|
| ![start](assets/shot-start.png) | ![freeze](assets/shot-freeze.png) | ![spike](assets/shot-spike.png) |

## What the agent reads (`report.md`, trimmed)

```md
## Motion analysis (text version of the animation)

- median motion: 4.5/255 per step at 2fps; low = still, high = big visual change.
- FREEZE x1: 1.5s around 3.5s
- JANK spikes x2: 3.0s (79.1), 5.0s (79.6)
```

One sentence the agent can now state before touching code: *"The spinner
freezes for ~1.5s around 3.5s, bracketed by two hard cuts at 3.0s and 5.0s."*
From there it greps for the checkout spinner/transition code instead of
guessing from a paragraph.
