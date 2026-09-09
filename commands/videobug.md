---
description: Fix a screen-recorded bug without touching the terminal. Finds the recording, converts it locally, and fixes from frames.
---

Load the `videobug` skill and do everything yourself for: $ARGUMENTS

Never ask the user to run commands. If no video path is in the request, use `--latest` (auto-picks the newest recording). If app+screen / expected / actual are missing, ask for just those three in plain words, then run `python3 <videobug-repo>/videobug.py`, read `<stem>_videobug/report.md` plus `frames/*.png` as images, and fix from that evidence. Stay 100% local.
