# Archival Rules

Run this check at session start when Drill History or Session Log has grown past 20 rows.

## When to archive
- Drill History > 20 rows, or Session Log > 20 rows.

## How
1. Keep the **most recent 20 rows** of each table in `training_state.md`.
2. Move older rows into a dated archive section at the bottom of `training_state.md` under `## Archive — YYYY-MM`, one subsection per month, preserving the exact row format.
3. Before moving, distill **one summary line per track** from the archived rows and append it to Coaching Notes, e.g.: "Voice (Sep): 6 drills, 4 Clear — filler rate fell 9/min → 5/min; pause placement still the fix."

## What never gets archived
- Track Levels table, Baselines, Calibration, and the current Coaching Notes bullets stay live.
- Test History rows are never archived — exams are few and each one matters for trend comparison.

## Why
State must stay loadable in one read. Twenty rows of drill history plus a per-track summary line preserves the signal (what improved, what's stuck) without the bulk.
