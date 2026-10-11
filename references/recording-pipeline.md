# Recording Pipeline

How recordings become measurements. The pipeline measures; the coach judges.
Deterministic metrics come from code (`tools/`), never from impression.

## Inputs

- The speaker sends a recording in chat: an audio/video file attachment, or a
  voice note. Voice notes and uploaded audio files are transcribed
  automatically by the chat platform; that transcript is passed to the tools
  via `--transcript`.
- Accepted formats: anything ffmpeg reads (mp3, wav, m4a, ogg, mp4, mov...).
- Size guidance: the automatic voice-note path caps around 8 MB. Longer takes
  go as file attachments; if a file is very long, split it first.
- No transcript available (e.g., some video files): the tools report
  acoustic-only metrics and note the gap. The coach then works from the
  speaker's dictation or a follow-up voice note. The pipeline degrades
  gracefully — it never blocks a drill.

## Tools

- `tools/analyze-audio.py <audio> [--transcript <txt>] [--out <json>]`: WPM
  (overall + over speech time), filler counts per type and per minute,
  pauses ≥1s with timestamps, sub-second pause count, volume stats
  (mean/max/dynamic range in dBFS), pitch stats (median/p10/p90 Hz, best
  effort), speech ratio, and caveats.
- `tools/analyze-video.py <video> [same flags] [--frame-every 10]
  [--workdir DIR]`: everything above via the audio track, plus one still
  frame every N seconds (default 10) for the visual review stage.

Requires: ffmpeg, ffprobe, python3 + numpy. Both scripts exit non-zero with a
plain error when inputs are invalid; they never invent numbers.

## What the numbers mean (quick map to the scorecard)

- `wpm` / `wpm_speech_time` → Pace band (120–150 target).
- `fillers_per_min` → Fillers band (<4 strong, 4–8 workable, >8 drill target).
- `pauses` (timestamps) + `pause_count` → Pause placement: deliberate
  (before answers, key points, emotion) vs. absent.
- `short_pauses_count` → micro-pausing habit; high counts with zero long
  pauses often mean rushing.
- `volume.dynamic_range_db` → Volume variety (flat = one volume throughout).
- `pitch` p10/p90 spread → Melody/tonality variety (narrow = monotone risk).
  Best effort only — noisy audio degrades it; the JSON says so when it does.
- `frames[]` → Presence review: posture, gestures, face-vs-words match,
  eye contact. Sampled stills, not motion — fidgeting between frames is
  invisible; the JSON notes this.

## Storage

Per-drill artifacts live under `recordings/<yyyy-mm-dd>-<drill-code>/`:
the original file, `metrics.json`, and `frames/` for video. This directory
is gitignored — practice recordings never touch the public repo. The Score
History row for the drill logs the path to `metrics.json`.

## For plain-chat LLMs

Without code execution the pipeline can't run. The coach still works: the
speaker reports their own numbers (or the coach estimates from the
transcript) and scores normally, flagging lower confidence. The repo
degrades gracefully by design.
