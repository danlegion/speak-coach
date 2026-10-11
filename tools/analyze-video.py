#!/usr/bin/env python3
"""Analyze a video drill: audio metrics + extracted frames for presence review.

Usage:
    analyze-video.py <video-file> [--transcript <text-file>] [--out <json-file>]
                     [--frame-every 10] [--workdir DIR]

Extracts the audio track and runs tools/analyze-audio.py on it, then pulls
one still frame every N seconds (default 10) for the visual review stage.
Frames are written to <workdir>/frames/frame_001.jpg etc.

The transcript comes from the chat platform's transcription of the sent file
or pasted by the speaker; without it, only acoustic metrics are reported.

Requires: ffmpeg, ffprobe, python3 + numpy.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "analyze_audio", Path(__file__).resolve().parent / "analyze-audio.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
analyze_audio = _mod.analyze


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])} failed: {p.stderr[:200]}")
    return p.stdout.strip()


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    src = Path(argv[1])
    if not src.exists():
        print(f"error: file not found: {src}", file=sys.stderr)
        return 1
    transcript, out, frame_every, workdir = None, None, 10, None
    args, i = argv[2:], 0
    while i < len(args):
        if args[i] == "--transcript" and i + 1 < len(args):
            transcript = Path(args[i + 1]).read_text(encoding="utf-8")
            i += 2
        elif args[i] == "--out" and i + 1 < len(args):
            out = args[i + 1]
            i += 2
        elif args[i] == "--frame-every" and i + 1 < len(args):
            frame_every = int(args[i + 1])
            i += 2
        elif args[i] == "--workdir" and i + 1 < len(args):
            workdir = Path(args[i + 1])
            i += 2
        else:
            print(f"error: unknown arg {args[i]}", file=sys.stderr)
            return 1

    td = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="vc_"))
    td.mkdir(parents=True, exist_ok=True)
    try:
        wav = td / "audio.wav"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
             "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
             str(wav)])
        audio = analyze_audio(wav, transcript)
        audio["file"] = str(src)

        frames_dir = td / "frames"
        frames_dir.mkdir(exist_ok=True)
        run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
             "-vf", f"fps=1/{frame_every}", "-q:v", "2",
             str(frames_dir / "frame_%03d.jpg")])
        frames = sorted(str(p) for p in frames_dir.glob("frame_*.jpg"))

        result = {
            "file": str(src),
            "video_duration_s": audio["duration_s"],
            "audio": audio,
            "frame_every_s": frame_every,
            "frame_count": len(frames),
            "frames": frames,
            "notes": [
                "frames are sampled stills, not motion — fidgeting between "
                "frames is invisible; review posture, gestures, and facial "
                "expression per frame."
            ] + audio.get("notes", []),
        }
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
