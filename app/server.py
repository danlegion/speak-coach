#!/usr/bin/env python3
"""Speak-coach mailbox server (M1, thin client).

The client (phone Pocket mode / Portal Station mode) only captures and
displays. This server is a dumb mailbox:

- GET  /                     -> the app page (app/static/index.html)
- GET  /static/<name>        -> static assets
- GET  /api/plan             -> today's session plan (app/plan.json)
- POST /api/upload?drill=V-L1-1&mode=audio
                             -> raw recording body; saves into
                                recordings/<date>-<drill>-<hhmmss>/
                                with meta.json (incl. Predict taps)
- GET  /api/status?session=<id>
                             -> received | processed | scored (+scorecard)

Processing (transcription, metrics, judgment) happens OUTSIDE this server,
in Felix's pass: app/process_session.py produces metrics.json, and the coach
writes scorecard.json. The server never invents numbers or scores.

Stdlib only. Optional shared-secret: set SPEAK_COACH_TOKEN and clients must
send header X-App-Token. Bind/port: HOST, PORT env (default 0.0.0.0:8765;
Render supplies PORT).
"""

import json
import os
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
STATIC_DIR = APP_DIR / "static"
RECORDINGS_DIR = REPO_DIR / "recordings"
TOKEN = os.environ.get("SPEAK_COACH_TOKEN", "")

EXT_BY_TYPE = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/mp4": "m4a",
    "video/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
}


def safe_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", text or "").strip("-")[:64]


class Handler(BaseHTTPRequestHandler):
    server_version = "SpeakCoachMailbox/0.1"

    # -- helpers ---------------------------------------------------------
    def _json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not TOKEN:
            return True
        return self.headers.get("X-App-Token", "") == TOKEN

    def _static(self, name: str):
        path = (STATIC_DIR / name).resolve()
        if STATIC_DIR.resolve() not in path.parents or not path.is_file():
            self._json({"error": "not found"}, 404)
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }.get(path.suffix, "application/octet-stream")
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- routes ----------------------------------------------------------
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._static("index.html")
        elif url.path.startswith("/static/"):
            self._static(url.path[len("/static/"):])
        elif url.path == "/api/plan":
            if not self._authorized():
                return self._json({"error": "unauthorized"}, 401)
            plan = APP_DIR / "plan.json"
            self._json(json.loads(plan.read_text("utf-8")))
        elif url.path == "/api/sessions":
            if not self._authorized():
                return self._json({"error": "unauthorized"}, 401)
            out = []
            if RECORDINGS_DIR.is_dir():
                for sdir in sorted(RECORDINGS_DIR.iterdir()):
                    if not sdir.is_dir():
                        continue
                    meta_path = sdir / "meta.json"
                    meta = (json.loads(meta_path.read_text("utf-8"))
                            if meta_path.is_file() else {})
                    recs = sorted(p.name for p in sdir.glob("recording.*"))
                    out.append({
                        "session": sdir.name,
                        "drill": meta.get("drill"),
                        "received_at": meta.get("received_at"),
                        "recording": recs[0] if recs else None,
                        "has_metrics": (sdir / "metrics.json").is_file(),
                        "has_scorecard": (sdir / "scorecard.json").is_file(),
                    })
            return self._json({"sessions": out})
        elif url.path.startswith("/api/sessions/"):
            if not self._authorized():
                return self._json({"error": "unauthorized"}, 401)
            parts = url.path.strip("/").split("/")
            # /api/sessions/<id>/recording|meta
            if len(parts) != 4:
                return self._json({"error": "not found"}, 404)
            session = safe_id(parts[2])
            sdir = RECORDINGS_DIR / session
            if not sdir.is_dir():
                return self._json({"error": "unknown session"}, 404)
            if parts[3] == "meta":
                meta = sdir / "meta.json"
                if not meta.is_file():
                    return self._json({"error": "no meta"}, 404)
                return self._json(json.loads(meta.read_text("utf-8")))
            if parts[3] == "recording":
                recs = sorted(p for p in sdir.glob("recording.*") if p.is_file())
                if not recs:
                    return self._json({"error": "no recording"}, 404)
                data = recs[0].read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{recs[0].name}"')
                self.end_headers()
                self.wfile.write(data)
                return
            return self._json({"error": "not found"}, 404)
        elif url.path == "/api/status":
            if not self._authorized():
                return self._json({"error": "unauthorized"}, 401)
            session = safe_id(parse_qs(url.query).get("session", [""])[0])
            sdir = RECORDINGS_DIR / session
            if not session or not sdir.is_dir():
                return self._json({"error": "unknown session"}, 404)
            scorecard = sdir / "scorecard.json"
            if scorecard.is_file():
                return self._json({
                    "status": "scored",
                    "scorecard": json.loads(scorecard.read_text("utf-8")),
                })
            if (sdir / "metrics.json").is_file():
                return self._json({"status": "processed"})
            return self._json({"status": "received"})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        url = urlparse(self.path)
        if url.path.startswith("/api/sessions/") and url.path.endswith("/results"):
            if not self._authorized():
                return self._json({"error": "unauthorized"}, 401)
            parts = url.path.strip("/").split("/")
            session = safe_id(parts[2]) if len(parts) == 4 else ""
            sdir = RECORDINGS_DIR / session
            if not session or not sdir.is_dir():
                return self._json({"error": "unknown session"}, 404)
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            written = []
            for key, fname in (("metrics", "metrics.json"),
                               ("scorecard", "scorecard.json")):
                if isinstance(payload.get(key), dict):
                    (sdir / fname).write_text(
                        json.dumps(payload[key], indent=2), "utf-8")
                    written.append(fname)
            return self._json({"session": session, "written": written})
        if url.path != "/api/upload":
            return self._json({"error": "not found"}, 404)
        if not self._authorized():
            return self._json({"error": "unauthorized"}, 401)
        qs = parse_qs(url.query)
        drill = safe_id(qs.get("drill", ["unknown"])[0]) or "unknown"
        mode = safe_id(qs.get("mode", ["audio"])[0]) or "audio"
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return self._json({"error": "empty body"}, 400)
        body = self.rfile.read(length)
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        ext = EXT_BY_TYPE.get(ctype, "bin")
        now = datetime.now()
        session = f"{now:%Y-%m-%d}-{drill}-{now:%H%M%S}"
        sdir = RECORDINGS_DIR / session
        suffix = 2
        while sdir.exists():
            session = f"{now:%Y-%m-%d}-{drill}-{now:%H%M%S}-{suffix}"
            sdir = RECORDINGS_DIR / session
            suffix += 1
        sdir.mkdir(parents=True)
        (sdir / f"recording.{ext}").write_bytes(body)
        meta = {
            "session": session,
            "drill": drill,
            "mode": mode,
            "received_at": now.isoformat(timespec="seconds"),
            "content_type": ctype,
            "bytes": length,
            "predict": {
                "pace": self.headers.get("X-Predict-Pace", ""),
                "fillers": self.headers.get("X-Predict-Fillers", ""),
            },
        }
        (sdir / "meta.json").write_text(json.dumps(meta, indent=2), "utf-8")
        self._json({"session": session, "status": "received"})

    def log_message(self, fmt, *args):  # keep stdout clean
        pass


def main():
    port = int(os.environ.get("PORT", "8765"))
    host = os.environ.get("HOST", "0.0.0.0")
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
