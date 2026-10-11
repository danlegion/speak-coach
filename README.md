# Speak Coach

A portable communication-skills coach: a GitHub-repo-shaped prototype that turns any LLM with file access into a rigorous speaking trainer — drills, tests, and mastery-gated progression across six tracks.

## How to use

1. Load `COACH.md` into your LLM (it's the brain: persona, drill loop, scoring, levels, commands).
2. Say `kickoff` — three short placement recordings set your starting level per track.
3. Train with `drill [track]`, `roleplay [scenario]`, `warmup`; check in with `test` (weekly) and `progress`; suffer `bossfight` (monthly).
4. Your state persists in `training_state.md` — the coach reads it at session start and writes it after every drill.

Works with any LLM that can read and write files.

## The six tracks

**Voice** (delivery mechanics) · **Structure** (storytelling & frameworks) · **Impromptu** (thinking on your feet) · **Interview** (answers under evaluation) · **Everyday** (conversation as a skill) · **Stage** (presence & persuasion)

Levels L1–L5 are defined by observable behavior, earned by mastery (three `Clear` drills at the bar, one with a difficulty dial above baseline) — not by streaks.

**Text-first:** drills default to written answers (content scored only); voice and video recording are the upgrade path — the gate-closing Clear must be voiced. See Response Modes in COACH.md.

## Layout

- `COACH.md` — the coach brain
- `training_state.md` — your persistent state, gitignored (copy from `training_state.template.md` on first run)
- `references/drill-library.md` — 60 starter drills, 2 per level per track
- `references/training-state-schema.md` — the state file format
- `references/rubrics.md` — scoring detail per track
- `references/cross-cutting.md` — transcript metrics, predict protocol, difficulty dials
- `references/coaching-voice.md` — how the coach sounds
- `references/recording-pipeline.md` — how recordings become measurements
- `tools/analyze-audio.py`, `tools/analyze-video.py` — deterministic delivery metrics + frame extraction (requires ffmpeg + python3/numpy)
- `references/archival-rules.md` — keeping state files lean
- `references/commands/` — `kickoff`, `drill`, `warmup`, `roleplay`, `test`, `bossfight`, `progress`, `help`

## Status

Prototype scaffold (Oct 2026). No story bank by design — this coach trains the speaker, not the script.
