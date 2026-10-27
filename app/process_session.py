#!/usr/bin/env python3
"""Felix's processing pass for one uploaded speak-coach session (M1).

Given a session directory under recordings/ (created by app/server.py),
this script does the deterministic half of the drill loop:

1. Transcribe the recording locally (faster-whisper) -> transcript.txt
   (+ transcript.json with segment timings). If faster-whisper is not
   installed or fails, it degrades gracefully: acoustic-only metrics and a
   transcript note, exactly as references/recording-pipeline.md prescribes.
2. Run the existing measurement tools (tools/analyze-audio.py, or
   analyze-video.py for video sessions) -> raw metrics.
3. Run tools/repetition.py on the transcript -> phrase-repetition metrics.
4. Merge into metrics.json in the app's scorecard shape.

It deliberately does NOT write scorecard.json — the judged half (strengths,
one fix, verdict, next step) is the coach's, written after reviewing
metrics + transcript + frames.

Usage: process_session.py <session-dir>
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
TOOLS_DIR = REPO_DIR / "tools"


def load_repetition():
    spec = importlib.util.spec_from_file_location(
        "repetition", TOOLS_DIR / "repetition.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def transcribe(recording: Path, sdir: Path) -> dict:
    """Return {'ok': bool, 'note': str}. Writes transcript.txt on success."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return {"ok": False, "note": "faster-whisper not installed"}
    try:
        import os
        import subprocess as sp

        import numpy as np

        model_name = os.environ.get("WHISPER_MODEL", "base")
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        # Decode with ffmpeg and pass raw PCM: faster-whisper's PyAV decode
        # path breaks on some av versions (metadata_errors kwarg), while the
        # ndarray input path is stable across versions.
        pcm = sp.run(
            ["ffmpeg", "-v", "error", "-i", str(recording),
             "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
            capture_output=True, check=True).stdout
        audio = np.frombuffer(pcm, dtype=np.float32)
        segments, info = model.transcribe(audio)
        segs = [{"start": s.start, "end": s.end, "text": s.text.strip()}
                for s in segments]
        text = " ".join(s["text"] for s in segs)
        (sdir / "transcript.txt").write_text(text, encoding="utf-8")
        (sdir / "transcript.json").write_text(json.dumps({
            "language": info.language,
            "duration_s": info.duration,
            "segments": segs,
        }, indent=2), encoding="utf-8")
        return {"ok": True, "note": f"faster-whisper {model_name}, lang={info.language}"}
    except Exception as exc:  # never block the drill on transcription
        return {"ok": False, "note": f"transcription failed: {exc}"}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: process_session.py <session-dir>", file=sys.stderr)
        return 2
    sdir = Path(sys.argv[1]).resolve()
    meta = json.loads((sdir / "meta.json").read_text("utf-8"))
    recordings = sorted(p for p in sdir.glob("recording.*") if p.is_file())
    if not recordings:
        print(f"no recording.* in {sdir}", file=sys.stderr)
        return 1
    recording = recordings[0]
    mode = meta.get("mode", "audio")

    transcript_path = sdir / "transcript.txt"
    tinfo = {"ok": transcript_path.is_file(), "note": "existing transcript"}
    if not transcript_path.is_file():
        tinfo = transcribe(recording, sdir)

    tool = "analyze-video.py" if mode == "video" else "analyze-audio.py"
    raw_out = sdir / "metrics_raw.json"
    cmd = [sys.executable, str(TOOLS_DIR / tool), str(recording),
           "--out", str(raw_out)]
    if transcript_path.is_file():
        cmd += ["--transcript", str(transcript_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    raw = {}
    if raw_out.is_file():
        raw = json.loads(raw_out.read_text("utf-8"))
    elif proc.returncode != 0:
        print(f"{tool} failed: {proc.stderr.strip()}", file=sys.stderr)
        return 1

    reps = None
    if transcript_path.is_file():
        rep_mod = load_repetition()
        duration = raw.get("duration_s") or raw.get("duration")
        reps = rep_mod.analyze(transcript_path.read_text("utf-8"),
                               float(duration) if duration else None)

    tx = raw.get("transcript", {}) if isinstance(raw.get("transcript"), dict) else {}
    metrics = {
        "duration_s": raw.get("duration_s", raw.get("duration")),
        "word_count": tx.get("word_count"),
        "wpm": tx.get("wpm", raw.get("wpm")),
        "wpm_speech_time": tx.get("wpm_speech_time",
                                  raw.get("wpm_speech_time")),
        "fillers_per_min": tx.get("fillers_per_min",
                                  raw.get("fillers_per_min")),
        "fillers": tx.get("fillers", raw.get("fillers")),
        "fillers_total": tx.get("fillers_total"),
        "pauses_1s": (len(raw.get("pauses", []))
                      if isinstance(raw.get("pauses"), list)
                      else raw.get("pause_count")),
        "pauses": raw.get("pauses"),
        "short_pauses_count": raw.get("short_pauses_count"),
        "volume": raw.get("volume"),
        "pitch": raw.get("pitch"),
        "speech_ratio": raw.get("speech_ratio"),
        "repetitions_per_min": (reps or {}).get("repetitions_per_min"),
        "repetition_events": (reps or {}).get("repetition_events"),
        "repeated_phrases": (reps or {}).get("repeated_phrases"),
        "transcription": tinfo,
        "raw_tool": tool,
    }
    (sdir / "metrics.json").write_text(json.dumps(metrics, indent=2),
                                       encoding="utf-8")
    print(json.dumps({
        "session": meta.get("session"),
        "transcription": tinfo,
        "metrics_written": True,
        "duration_s": metrics["duration_s"],
        "wpm": metrics["wpm"],
        "fillers_per_min": metrics["fillers_per_min"],
        "repetitions_per_min": metrics["repetitions_per_min"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
