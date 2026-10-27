#!/usr/bin/env python3
"""Sync speak-coach sessions between the hosted mailbox (Render) and Felix's
VM, where processing and judgment happen.

    sync_sessions.py all     # down -> process -> up
    sync_sessions.py down    # pull new recordings + meta into recordings/
    sync_sessions.py process # run process_session.py on unprocessed locals
    sync_sessions.py up      # push local metrics.json / scorecard.json back

Config: SPEAK_COACH_BASE (e.g. https://speak-coach.onrender.com) and the
token from SPEAK_COACH_TOKEN env or app/.token (gitignored, local only).
The hosted copy is a mailbox with an ephemeral disk; the VM's recordings/
directory is the durable store.
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
RECORDINGS_DIR = REPO_DIR / "recordings"
BASE = os.environ.get("SPEAK_COACH_BASE", "").rstrip("/")


def token() -> str:
    if os.environ.get("SPEAK_COACH_TOKEN"):
        return os.environ["SPEAK_COACH_TOKEN"]
    tf = APP_DIR / ".token"
    return tf.read_text().strip() if tf.is_file() else ""


def req(method: str, path: str, data: bytes | None = None,
        ctype: str = "application/json") -> bytes:
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("X-App-Token", token())
    if data is not None:
        r.add_header("Content-Type", ctype)
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.read()


def remote_sessions() -> list[dict]:
    return json.loads(req("GET", "/api/sessions"))["sessions"]


def do_down() -> list[str]:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    new = []
    for s in remote_sessions():
        sdir = RECORDINGS_DIR / s["session"]
        if (sdir / "meta.json").is_file():
            continue
        sdir.mkdir(parents=True, exist_ok=True)
        meta = req("GET", f"/api/sessions/{s['session']}/meta")
        (sdir / "meta.json").write_bytes(meta)
        if s.get("recording"):
            blob = req("GET", f"/api/sessions/{s['session']}/recording")
            (sdir / s["recording"]).write_bytes(blob)
        new.append(s["session"])
        print(f"down: {s['session']} ({s.get('recording')})")
    if not new:
        print("down: nothing new")
    return new


def do_process() -> None:
    if not RECORDINGS_DIR.is_dir():
        print("process: no local recordings")
        return
    for sdir in sorted(RECORDINGS_DIR.iterdir()):
        if not sdir.is_dir() or (sdir / "metrics.json").is_file():
            continue
        if not list(sdir.glob("recording.*")):
            continue
        print(f"process: {sdir.name}")
        proc = subprocess.run(
            [sys.executable, str(APP_DIR / "process_session.py"), str(sdir)],
            capture_output=True, text=True)
        print(proc.stdout.strip() or proc.stderr.strip())


def do_up() -> None:
    remote = {s["session"]: s for s in remote_sessions()}
    if not RECORDINGS_DIR.is_dir():
        print("up: no local recordings")
        return
    for sdir in sorted(RECORDINGS_DIR.iterdir()):
        if not sdir.is_dir() or sdir.name not in remote:
            continue
        payload = {}
        for key, fname in (("metrics", "metrics.json"),
                           ("scorecard", "scorecard.json")):
            f = sdir / fname
            if f.is_file() and not remote[sdir.name].get(f"has_{key}"):
                payload[key] = json.loads(f.read_text("utf-8"))
        if payload:
            req("POST", f"/api/sessions/{sdir.name}/results",
                json.dumps(payload).encode("utf-8"))
            print(f"up: {sdir.name} -> {sorted(payload)}")
    print("up: done")


def main() -> int:
    if not BASE:
        print("set SPEAK_COACH_BASE", file=sys.stderr)
        return 2
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("down", "all"):
        do_down()
    if cmd in ("process", "all"):
        do_process()
    if cmd in ("up", "all"):
        do_up()
    if cmd not in ("down", "process", "up", "all"):
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
