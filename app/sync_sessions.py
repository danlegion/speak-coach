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
        ctype: str = "application/json",
        extra_headers: dict | None = None) -> bytes:
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("X-App-Token", token())
    if data is not None:
        r.add_header("Content-Type", ctype)
    for k, v in (extra_headers or {}).items():
        r.add_header(k, v)
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.read()


def remote_sessions() -> list[dict]:
    return json.loads(req("GET", "/api/sessions"))["sessions"]


def do_down() -> list[str]:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    # Hash-dedupe: a mailbox reset + restore gives an old recording a NEW
    # remote id. Without this, the restored copy downloads as a brand-new
    # local session and gets judged as a fresh rep (the Nov 3 watcher
    # misfire). Match by recording bytes, not by id.
    import hashlib

    def recording_hashes() -> dict[str, str]:
        out = {}
        if RECORDINGS_DIR.is_dir():
            for sdir in RECORDINGS_DIR.iterdir():
                if not sdir.is_dir():
                    continue
                for rec in sdir.glob("recording.*"):
                    if rec.is_file():
                        out[hashlib.sha256(rec.read_bytes()).hexdigest()] = sdir.name
        return out

    hashes = recording_hashes()
    mapping = load_map()
    map_changed = False
    new = []
    for s in remote_sessions():
        sdir = RECORDINGS_DIR / s["session"]
        if (sdir / "meta.json").is_file():
            continue
        meta = req("GET", f"/api/sessions/{s['session']}/meta")
        blob = b""
        if s.get("recording"):
            blob = req("GET", f"/api/sessions/{s['session']}/recording")
        if blob:
            digest = hashlib.sha256(blob).hexdigest()
            if digest in hashes:
                existing = hashes[digest]
                print(f"down: {s['session']} duplicates {existing}, skipped")
                if mapping.get(existing) != s["session"]:
                    mapping[existing] = s["session"]
                    map_changed = True
                continue
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "meta.json").write_bytes(meta)
        if s.get("recording"):
            (sdir / s["recording"]).write_bytes(blob)
            hashes[hashlib.sha256(blob).hexdigest()] = s["session"]
        new.append(s["session"])
        print(f"down: {s['session']} ({s.get('recording')})")
    if map_changed:
        MAP_FILE.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
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


MAP_FILE = RECORDINGS_DIR / ".remote-map.json"


def load_map() -> dict:
    if MAP_FILE.is_file():
        try:
            return json.loads(MAP_FILE.read_text("utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def do_restore() -> None:
    """Re-upload local sessions missing from the mailbox.

    Render's free disk is wiped on every deploy, so the mailbox is not
    durable — the VM's recordings/ is. A restored session gets a NEW
    remote id (recorded in .remote-map.json) so later runs don't
    duplicate it; the Past scorecards list in the app is id-agnostic.
    """
    remote = {s["session"] for s in remote_sessions()}
    mapping = load_map()
    changed = False
    if not RECORDINGS_DIR.is_dir():
        print("restore: no local recordings")
        return
    for sdir in sorted(RECORDINGS_DIR.iterdir()):
        if not sdir.is_dir() or not (sdir / "scorecard.json").is_file():
            continue
        recs = sorted(p for p in sdir.glob("recording.*") if p.is_file())
        if not recs:
            continue
        rid = mapping.get(sdir.name, sdir.name)
        if rid in remote:
            continue
        meta = json.loads((sdir / "meta.json").read_text("utf-8")) \
            if (sdir / "meta.json").is_file() else {}
        headers = {"X-Predict-Pace": (meta.get("predict") or {}).get("pace", ""),
                   "X-Predict-Fillers": (meta.get("predict") or {}).get("fillers", "")}
        out = json.loads(req(
            "POST",
            f"/api/upload?drill={meta.get('drill', 'V-L1-1')}"
            f"&mode={meta.get('mode', 'audio')}",
            recs[0].read_bytes(),
            ctype=meta.get("content_type", "application/octet-stream"),
            extra_headers=headers))
        new_id = out["session"]
        payload = {}
        for key, fname in (("metrics", "metrics.json"),
                           ("scorecard", "scorecard.json")):
            f = sdir / fname
            if f.is_file():
                payload[key] = json.loads(f.read_text("utf-8"))
        req("POST", f"/api/sessions/{new_id}/results",
            json.dumps(payload).encode("utf-8"))
        mapping[sdir.name] = new_id
        changed = True
        print(f"restore: {sdir.name} -> {new_id} (with metrics + scorecard)")
    if changed:
        MAP_FILE.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    else:
        print("restore: nothing missing")


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
    if cmd in ("restore", "all"):
        do_restore()
    if cmd not in ("down", "process", "up", "restore", "all"):
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
