# Agent setup

videobug ships as a plain `SKILL.md` plus a command template, so it works with
any harness that reads Markdown skills. One-time copy, then just say
`/videobug` (or describe the bug) in chat.

## OpenCode (primary)

Global (every project):

```sh
git clone https://github.com/s17labs/videobug.git
cp -r videobug/skills/videobug ~/.config/opencode/skills/
cp videobug/commands/videobug.md ~/.config/opencode/commands/
```

Project-only (checked in with your app):

```sh
cp -r videobug/skills/videobug /path/to/app/.opencode/skills/
cp videobug/commands/videobug.md /path/to/app/.opencode/commands/
```

Then in chat:

> `/videobug` the settings toggle stutters. Expected: smooth slide.
> Actual: jumps halfway.

## Claude Code

```sh
cp -r videobug/skills/videobug ~/.claude/skills/
```

Claude Code auto-discovers `~/.claude/skills/*/SKILL.md`. Paste the
recording path (or record first, then say "latest") plus expected/actual.

## Cursor / Codex / Cline

These read skills from their own directories — copy the same folder:

```sh
cp -r videobug/skills/videobug /path/to/app/.cursor/skills/   # Cursor
```

Then attach `<name>_videobug/report.md` and drop `frames/*.png` into chat.
If your harness has no skill system at all, that manual attach *is* the
integration — no plugin required.

## No skill system? No problem

1. Run `python3 videobug.py --latest --expected "..." --actual "..."`.
2. Paste `report.md` into chat, attach `frames/*.png` as images.
3. Text-only harness? Skip the images: `report.md` + `motion.csv` alone
   describe the animation (timestamps, freeze durations, spike scores).
