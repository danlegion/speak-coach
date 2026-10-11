#!/usr/bin/env python3
"""Analyze a spoken-word recording: transcript metrics + acoustic measurements.

Usage:
    analyze-audio.py <audio-file> [--transcript <text-file>] [--out <json-file>]

The transcript comes from the chat platform's transcription of the sent file
(voice notes and uploaded audio are transcribed automatically) or pasted by
the speaker. Without it, only acoustic metrics are reported.

Output (JSON): duration, speech time, WPM, filler counts, pauses >= 1s with
timestamps, sub-second pause count, volume stats, pitch stats, and caveats.
Deterministic measurements only — judgment stays with the coach.

Requires: ffmpeg, ffprobe, python3 + numpy.
"""
import json
import math
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

FILLERS = ["um", "uh", "like", "you know", "basically", "actually"]
SAMPLE_RATE = 16000
FRAME_S = 0.02   # VAD frame
HOP_S = 0.01     # VAD hop
PAUSE_MIN_S = 1.0


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])} failed: {p.stderr[:200]}")
    return p.stdout.strip()


def to_wav(src, dst):
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(dst)])


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        n = w.getnframes()
        raw = w.readframes(n)
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def frame_rms(x, frame_n, hop_n):
    n_frames = 1 + (len(x) - frame_n) // hop_n
    if n_frames <= 0:
        return np.array([])
    idx = np.arange(frame_n)[None, :] + hop_n * np.arange(n_frames)[:, None]
    frames = x[idx]
    return np.sqrt(np.mean(frames ** 2, axis=1))


def detect_pauses(rms, hop_s, min_s=PAUSE_MIN_S):
    if len(rms) == 0:
        return [], 0.0
    thr = max(float(np.max(rms)) * 0.03, 1e-3)
    silent = rms < thr
    pauses, start = [], None
    short_pauses = 0
    for i, s in enumerate(silent):
        if s and start is None:
            start = i
        elif not s and start is not None:
            dur = (i - start) * hop_s
            if dur >= min_s:
                pauses.append({"start_s": round(start * hop_s, 2),
                               "duration_s": round(dur, 2)})
            elif dur >= 0.3:
                short_pauses += 1
            start = None
    if start is not None:
        dur = (len(silent) - start) * hop_s
        if dur >= min_s:
            pauses.append({"start_s": round(start * hop_s, 2),
                           "duration_s": round(dur, 2)})
        elif dur >= 0.3:
            short_pauses += 1
    speech_s = float(np.sum(~silent)) * hop_s
    return pauses, speech_s, short_pauses


def pitch_stats(x, rms, hop_n, thr):
    """Median/p10/p90 fundamental frequency over voiced frames (best effort)."""
    frame_n = int(0.03 * SAMPLE_RATE)
    f0s = []
    voiced = np.where(rms > thr * 2)[0]
    for i in voiced[::3]:  # every 3rd frame is plenty
        s = int(i * hop_n)
        seg = x[s:s + frame_n]
        if len(seg) < frame_n:
            continue
        seg = seg - np.mean(seg)
        ac = np.correlate(seg, seg, mode="full")[frame_n - 1:]
        if ac[0] < 1e-9:
            continue
        ac = ac / ac[0]
        lo, hi = int(SAMPLE_RATE / 400), int(SAMPLE_RATE / 75)
        if hi >= len(ac):
            continue
        peak = np.argmax(ac[lo:hi]) + lo
        if ac[peak] > 0.3:
            f0s.append(SAMPLE_RATE / peak)
    if len(f0s) < 10:
        return {"median_hz": None, "p10_hz": None, "p90_hz": None,
                "voiced_ratio": round(len(f0s) / max(len(voiced), 1), 3),
                "note": "too few voiced frames for reliable pitch"}
    a = np.array(f0s)
    return {"median_hz": round(float(np.median(a)), 1),
            "p10_hz": round(float(np.percentile(a, 10)), 1),
            "p90_hz": round(float(np.percentile(a, 90)), 1),
            "voiced_ratio": round(len(f0s) / max(len(voiced), 1), 3)}


def count_fillers(text):
    t = text.lower()
    counts = {}
    for f in FILLERS:
        counts[f] = len(re.findall(r"\b" + re.escape(f) + r"\b", t))
    # sentence-initial "so" ("So, ..." / ". So ...")
    counts["so (sentence-initial)"] = len(
        re.findall(r"(?:^|[.!?]\s+)so\b", t))
    return counts


def analyze(path, transcript_text=None):
    notes = []
    try:
        duration_s = float(run(["ffprobe", "-v", "error",
                                "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(path)]))
    except RuntimeError:
        raise RuntimeError("ffprobe failed — is ffmpeg installed and the file valid?")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "audio.wav"
        to_wav(path, wav)
        x = read_wav(wav)
    if len(x) == 0:
        raise RuntimeError("no audio decoded from file")
    frame_n, hop_n = int(FRAME_S * SAMPLE_RATE), int(HOP_S * SAMPLE_RATE)
    rms = frame_rms(x, frame_n, hop_n)
    pauses, speech_s, short_pauses = detect_pauses(rms, HOP_S)
    thr = max(float(np.max(rms)) * 0.03, 1e-3)

    result = {
        "file": str(path),
        "duration_s": round(duration_s, 1),
        "speech_s": round(speech_s, 1),
        "speech_ratio": round(speech_s / duration_s, 3) if duration_s else 0,
        "pauses": pauses,
        "pause_count": len(pauses),
        "short_pauses_count": short_pauses,
        "longest_pause_s": max([p["duration_s"] for p in pauses],
                               default=0.0),
    }

    # volume (speech frames only)
    speech_rms = rms[rms >= thr]
    if len(speech_rms):
        db = 20 * np.log10(speech_rms + 1e-9)
        result["volume"] = {
            "mean_dbfs": round(float(np.mean(db)), 1),
            "max_dbfs": round(float(np.max(db)), 1),
            "dynamic_range_db": round(float(np.percentile(db, 90)
                                            - np.percentile(db, 10)), 1),
        }
    else:
        result["volume"] = None
        notes.append("no speech frames detected — check the file")

    result["pitch"] = pitch_stats(x, rms, hop_n, thr)

    if transcript_text and transcript_text.strip():
        words = transcript_text.split()
        n = len(words)
        fillers = count_fillers(transcript_text)
        total_fillers = sum(fillers.values())
        result["transcript"] = {
            "word_count": n,
            "wpm": round(n / duration_s * 60, 1) if duration_s else 0,
            "wpm_speech_time": round(n / speech_s * 60, 1) if speech_s else 0,
            "fillers": fillers,
            "fillers_total": total_fillers,
            "fillers_per_min": round(total_fillers / duration_s * 60, 1)
            if duration_s else 0,
        }
    else:
        result["transcript"] = None
        notes.append("no transcript provided — WPM and filler counts skipped; "
                     "pass --transcript with the platform transcription")

    if duration_s < 10:
        notes.append("very short sample (<10s) — metrics are thin evidence")
    result["notes"] = notes
    return result


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    src = Path(argv[1])
    if not src.exists():
        print(f"error: file not found: {src}", file=sys.stderr)
        return 1
    transcript, out = None, None
    args = argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--transcript" and i + 1 < len(args):
            transcript = Path(args[i + 1]).read_text(encoding="utf-8")
            i += 2
        elif args[i] == "--out" and i + 1 < len(args):
            out = args[i + 1]
            i += 2
        else:
            print(f"error: unknown arg {args[i]}", file=sys.stderr)
            return 1
    try:
        result = analyze(src, transcript)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
