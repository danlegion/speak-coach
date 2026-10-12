# Speak Coach

Most people who want to speak better collect advice. Advice doesn't change how you sound in a meeting on Tuesday. Reps do.

Speak Coach is a communication-skills trainer that lives in a GitHub repo. Load it into any LLM that can read and write files, and the LLM becomes a coach: it places you with short samples, runs timed drills, scores what you actually said, gives you one fix at a time, and makes you re-drill it on the spot. Your history lives in a state file on your own machine, so session twelve knows exactly what session three found.

## What training looks like

**Kickoff** places you. Three short samples — two written, one recorded — set a starting level on each track. No generic "beginner/intermediate": levels are defined by observable behavior, so L2 on Voice means something specific you did, not a vibe.

**A drill** runs a tight loop:

1. **Brief** — one prompt, a time limit, one focus.
2. **Respond** — written in one go, or recorded. No editing, no restarts; a flubbed rep is data.
3. **Measure** — the coach transcribes and counts before it judges: words per minute, fillers, pauses, and (from a recording) volume and pitch range.
4. **Predict** — before you see any review, you say how you think that went. The gap between your read and the coach's is where self-awareness gets built.
5. **Review** — a three-stage audit: muted (body only), audio only (voice only), transcript (words only). Each stage catches what the others hide.
6. **Scorecard** — two scores, always separate: *delivery* (how it sounded) and *content* (whether it landed). Conflating them is how people with good ideas get told they're "not confident."
7. **One fix** — never a laundry list. The single highest-leverage correction, taught as a principle with a replacement: not "stop saying *um*," but "when the next word isn't there, take one full second of silence — silence reads as confidence, and the word arrives."
8. **Re-drill** — immediately, same prompt, just the fix. Knowing isn't the skill; the second rep is.

**Progression is gated by mastery, not streaks.** A level is earned with three Clears at that level's bar, one of them with a difficulty dial turned up: less time, a stacked constraint, a hostile follow-up question, the camera on, a bigger imagined audience. A weekly `test` checks retention; a monthly `bossfight` chains everything under pressure.

**It's text-first on purpose.** Drills default to written answers, so content — structure, clarity, thinking on your feet — can be trained anywhere, silently, in a chat window. Voice and video are the upgrade path once the content holds up, and the Clear that closes a level gate has to be performed out loud. Thinking it and saying it are different skills; this trains them in that order.

## The six tracks

| Track | What it trains | It sounds like |
|---|---|---|
| **Voice** | Delivery mechanics: pace, pauses, melody, volume, fillers | Finishing 60 seconds cleanly → holding a room without rushing |
| **Structure** | Storytelling and frameworks: openings, points that land, closes | A recommendation with a spine → a story someone retells at dinner |
| **Impromptu** | Thinking on your feet: no-prep answers that stay coherent | Surviving a surprise question → enjoying one |
| **Interview** | Answers under evaluation: concise, evidenced, un-rattled | Rambling through your résumé → landing a point in 90 seconds |
| **Everyday** | Conversation as a skill: listening, follow-ups, disagreement | Small talk that dies → exchanges people remember |
| **Stage** | Presence and persuasion: body, space, an audience of many | Reading slides aloud → owning the room |

Pick one track or let the coach recommend the highest-leverage next drill from your state.

## Commands

| Command | What it does |
|---|---|
| `kickoff` | Placement samples; sets your starting levels |
| `drill [track]` | One drill at your current level, full loop |
| `warmup` | A short pre-meeting or pre-talk primer |
| `roleplay [scenario]` | Conversation practice against a character (a skeptical exec, a curious stranger) |
| `test` | The weekly exam at your level bars |
| `bossfight` | The monthly gauntlet: chained drills, dials up |
| `progress` | Where you stand, what's working, what's next |
| `help` | The coach explains itself |

## Getting started

1. Clone or download this repo.
2. Open it in an LLM with file read/write access and let it read `COACH.md`.
3. Say **`kickoff`**.

On first run the coach copies `training_state.template.md` to `training_state.md` — that file is gitignored, as is the `recordings/` folder. Your training history, scores, and recordings never leave your machine and are never committed.

Optional: if you record drills, `tools/analyze-audio.py` and `tools/analyze-video.py` turn audio/video into measurements (pace, fillers, pause map, volume, pitch range, video frames) that the coach scores against. They need `ffmpeg` and Python 3 with `numpy`. See `references/recording-pipeline.md`.

## Repository layout

- `COACH.md` — the brain: coaching persona, the drill loop, scoring, levels, session protocols
- `references/principles.md` — the teachable rules behind the corrections, per track
- `references/drill-library.md` — 60 starter drills (two per level per track), each with a Clear bar
- `references/rubrics.md` — the dual scorecards in detail
- `references/cross-cutting.md` — transcript metrics, the predict protocol, difficulty dials, the exposure ladder
- `references/coaching-voice.md` — how the coach talks (and what it never does)
- `references/commands/` — one file per command
- `references/recording-pipeline.md` — how recordings become measurements
- `references/training-state-schema.md` — the state file format
- `references/archival-rules.md` — keeping a long training history lean
- `tools/` — the audio/video analysis scripts
- `training_state.template.md` — the starter state file

## Contributing

This is a young prototype, and the library is the product — pull requests are how it gets better.

- **Drills.** Two per level per track is a floor, not a ceiling. New drills follow the format in `references/drill-library.md`: a code (`V-L1-1` style), a prompt, a time or word target, and an observable bar for what counts as a Clear.
- **Principles.** `references/principles.md` holds the rules the coach teaches. A principle earns its place only if it tells the speaker what to *do* — "say Y instead" — not merely what to avoid.
- **Rubrics and dials.** Sharper observable behaviors for a level, fairer scoring lines, new difficulty dials: all welcome, with a note on what speaker behavior prompted the change.
- **Tools.** The analysis pipeline is deliberately simple. Better pause detection, pitch tracking, or frame analysis makes every scorecard downstream more honest.

House rules: keep everything generic — principles and drills, no named programs, personalities, or personal data. Training state and recordings are never committed.

## Status

Prototype, October 2026, in active use. No story bank by design: this coach trains the speaker, not the script.
