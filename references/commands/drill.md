# drill [track] — run one drill

## Workflow
1. Determine the track: explicit argument wins; otherwise recommend per the session-start protocol (lowest level, weakest drill, or most recent un-re-drilled fix).
2. Pick the drill from `references/drill-library.md` matching the speaker's current level on that track. If the last drill on this track was a `Re-drill`, re-run the same drill with the one fix as the explicit focus (or its shrunken variant). For mastery-gate progress, vary prompt or dial from prior Clears.
3. Run the Drill Loop: brief (track, prompt, audience, time, constraints) → record → transcript → predict ("before you review — what will you see?") → three-stage review (mute, then audio-only, then transcript; speaker observes first at each stage) → dual scorecard → exactly one fix → immediate re-drill of the weak moment.
4. Score against the speaker's current level bar: `Clear` (at/above bar, counts toward mastery) or `Re-drill` (below bar).
5. Write the drill row to `training_state.md` (mid-session, silently). If this completes a mastery gate (three Clears at the bar, one with an above-baseline dial, third differing in prompt/dial), announce the level-up and update the level table in the same write.
6. End with `**Next**: [drill or re-drill] — [one-line reason].`
