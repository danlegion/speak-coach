#!/usr/bin/env python3
"""Phrase-repetition counter for speak-coach transcripts.

Daniel's filler pattern is phrase repetition ("I'm working on surface, I'm
working on surface inputs"), not um/uh. The stock filler counter in
analyze-audio.py cannot see it; this tool can.

Method: normalize words (lowercase, strip punctuation), count repeated
n-grams (n = 2..6) with non-overlapping occurrences, keep phrases repeated
>= 2 times, then drop any phrase fully contained in a longer repeated phrase
with the same count (report the maximal phrase). A "repetition event" is each
occurrence after the first.

Usage:
    repetition.py <transcript.txt> [--duration-seconds 62.5]
    repetition.py --text "some words ..." [--duration-seconds 60]

Output: JSON on stdout — top phrases with counts, total repetition events,
and per-minute rates when a duration is given.
"""

import argparse
import json
import re
import sys
from collections import defaultdict

MIN_N, MAX_N = 2, 6


def normalize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def count_ngrams(words: list[str], n: int) -> dict[tuple, int]:
    """Non-overlapping occurrence counts for each n-gram."""
    counts: dict[tuple, int] = defaultdict(int)
    seen_at: dict[tuple, int] = {}
    for i in range(len(words) - n + 1):
        gram = tuple(words[i:i + n])
        if seen_at.get(gram, -10**9) + n <= i:
            counts[gram] += 1
            seen_at[gram] = i
    return counts


def find_repetitions(words: list[str]) -> list[dict]:
    raw: dict[tuple, int] = {}
    for n in range(MIN_N, MAX_N + 1):
        for gram, c in count_ngrams(words, n).items():
            if c >= 2:
                raw[gram] = c
    # Maximal phrases only: drop a phrase if a strictly longer repeated
    # phrase contains it contiguously and repeats the same number of times.
    grams = sorted(raw.keys(), key=len, reverse=True)
    kept: list[tuple] = []
    for gram in grams:
        contained = False
        for longer in kept:
            if len(longer) <= len(gram) or raw[longer] != raw[gram]:
                continue
            for j in range(len(longer) - len(gram) + 1):
                if longer[j:j + len(gram)] == gram:
                    contained = True
                    break
            if contained:
                break
        if not contained:
            kept.append(gram)
    out = [
        {"phrase": " ".join(g), "words": len(g), "count": raw[g],
         "events": raw[g] - 1}
        for g in kept
    ]
    out.sort(key=lambda r: (-r["events"], -r["words"]))
    return out


def analyze(text: str, duration_s: float | None = None) -> dict:
    words = normalize(text)
    reps = find_repetitions(words)
    events = sum(r["events"] for r in reps)
    result = {
        "word_count": len(words),
        "repeated_phrases": reps[:20],
        "repetition_events": events,
    }
    if duration_s:
        minutes = duration_s / 60.0
        result["duration_s"] = round(duration_s, 1)
        result["repetitions_per_min"] = round(events / minutes, 2) if minutes else 0.0
        for r in result["repeated_phrases"]:
            r["events_per_min"] = round(r["events"] / minutes, 2) if minutes else 0.0
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", nargs="?", help="transcript text file")
    ap.add_argument("--text", help="transcript text directly")
    ap.add_argument("--duration-seconds", type=float, default=None)
    args = ap.parse_args()
    if args.text:
        text = args.text
    elif args.transcript:
        text = open(args.transcript, encoding="utf-8").read()
    else:
        ap.error("give a transcript file or --text")
    print(json.dumps(analyze(text, args.duration_seconds), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
