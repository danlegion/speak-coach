# Training State Schema

The format for `training_state.md`. The coach reads it at session start and writes it after every drill/test and at session end. Keep it plain markdown — any LLM with file access must be able to read and update it without tooling.

## Sections

### 1. Speaker Profile
- Name (or handle), primary goal (e.g., "lead eng interviews", "team presentations"), start date.
- Known constraints: e.g., "audio-only for now", "nervous on camera", "non-native English — clarity over accent".

### 2. Track Levels
A table with one row per track. Level is `—` (unplaced) until `kickoff` or the first scored drill sets it.

| Track | Level | Set on | Notes |
|---|---|---|---|
| Voice | L2 | 2026-10-12 | placed via kickoff |
| Structure | L1 | 2026-10-12 | … |
| Impromptu | — | — | not yet attempted |
| Interview | L3 | 2026-10-15 | … |
| Everyday | — | — | … |
| Stage | L1 | 2026-10-12 | … |

### 3. Drill History
One row per completed drill, newest last. `Result` is `Clear` or `Re-drill`. `Mode` is `text`, `voice`, or `video`. `Dial` records any difficulty dial used above baseline (`none`, `time-shrink`, `constraint-stack`, `hostile-followup`, `camera-on`, `audience-upgrade`). `Metrics` points to the pipeline's `metrics.json` for the drill (`recordings/<yyyy-mm-dd>-<drill>/metrics.json`, gitignored) when a recording was analyzed.

| Date | Track | Drill | Mode | Level bar | Result | Dial | One fix carried forward | Metrics |
|---|---|---|---|---|---|---|---|---|
| 2026-10-12 | Voice | Sixty Clean | voice | L2 | Clear | none | pause before the number | recordings/2026-10-12-V-L1-1/metrics.json |

Mastery counting: a track advances Ln → Ln+1 after **three `Clear` rows at that track scored against the Ln bar**, with at least one row using a dial above baseline, and the third Clear differing in prompt or dial from the first two. The coach announces the level-up and updates the Track Levels table in the same write.

### 4. Test History
| Date | Type | Track | Score summary | vs. last | Notes |
|---|---|---|---|---|---|
| 2026-10-19 | weekly | Structure | delivery 4/5, content 4/5 | +fillers | first exam |

`Type` is `weekly` or `bossfight`. Weekly exams are due every 7 days — the session-start protocol nags when the latest `weekly` row is older than 7 days.

### 5. Session Log
One row per session. Every 3rd session (row count multiple of 3) triggers the coaching meta-check ("Is this feedback landing?").

| # | Date | Focus | Drills done | Level changes | Meta-check |
|---|---|---|---|---|---|
| 1 | 2026-10-12 | kickoff | 3 placement | Voice L2, Structure L1, Stage L1 | — |

### 6. Baselines (Before/After Library)
Pointers to baseline vs. current recordings per track, so progress is audible. Store whatever pointer the speaker uses — file path, link, or "phone voice memo 2026-10-12".

| Track | Baseline | Current |
|---|---|---|
| Voice | … | … |

### 7. Coaching Notes
1–3 bullets per session, only patterns that change how to coach: "freezes on abstract impromptu topics", "pace spikes when nervous", "stronger with a framework than without". No laundry lists.

### 8. Calibration
The speaker's self-assessment gap: `over-rater`, `under-rater`, or `calibrated`, with one line of evidence and the adjustment in force. Revisit during `progress`.

## Update Rules

- Write after every completed drill and test (mid-session, silently), and at session end with confirmation.
- Never rewrite history: append rows, update the level table and notes in place.
- If Drill History or Session Log exceeds 20 rows, run the archival check (`references/archival-rules.md`) before writing.
- Keep the whole file skimmable: tables over prose, one line per row.
