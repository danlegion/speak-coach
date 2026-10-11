# kickoff — profile + placement

First-run command for a new speaker. Do NOT re-run once levels are set.

## Workflow
0. If `training_state.md` doesn't exist, copy `training_state.template.md` to `training_state.md` first (it's gitignored — personal data stays local).
1. Ask: name/handle, primary speaking goal, and constraints (audio-only? camera comfort? contexts: interviews, team, stage?).
2. Run three short placement samples — text by default, voice where the track demands it:
   - **Delivery sample (voice):** 60s recorded on a familiar topic (scores Voice). The one required recording: delivery can't be placed from text.
   - **Structure sample (text):** ~130 words recommending something you like, written in one go without editing (scores Structure).
   - **Impromptu sample (text):** ~130 words on a topic named on the spot, written without editing (scores Impromptu).
   For the voice sample: brief → record → ingest & analyze → predict → dual scorecard. For text samples: brief → write → re-read → content scorecard (delivery N/A).
3. Set starting levels: match each sample against the L1–L5 bars in COACH.md; place conservatively (the highest level whose bar the sample *clearly* meets). Interview, Everyday, and Stage start at `—` (unplaced) unless the speaker asks to place them — note them as "not yet attempted".
4. Write `training_state.md`: profile, level table, three drill-history rows (result: `Clear` or `Re-drill` at the placed bar), session log row #1, baselines pointers (ask where the recordings live), one coaching-notes bullet if a pattern already shows.
5. Close with the prescriptive recommendation per the session-start protocol: the highest-leverage next drill and why.

## Rules
- Three recordings max — placement is a sample, not an exam.
- If a sample is too thin to place (under 20s, tech failure), mark that track `—` and move on.
