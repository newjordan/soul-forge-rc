#!/usr/bin/env python3
"""Soul Forge UI server (no deps).

Serves the HTML UI and exposes a tiny JSON API for:
- loading an existing SOUL.md
- previewing an additive upgrade (diff + generated artifacts + seal)
- applying the upgrade (backup + overwrite) ONLY when explicitly requested

This intentionally avoids external dependencies (no Flask).
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from soulforge_additive import (
    build_combined,
    now_ts,
    read_text,
    sha256_text,
    unified_diff,
)

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"


def json_response(handler: BaseHTTPRequestHandler, code: int, obj: dict) -> None:
    data = (json.dumps(obj) + "\n").encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def safe_path(p: str) -> Path:
    # Allow absolute paths, but normalize.
    return Path(p).expanduser().resolve()


class Handler(BaseHTTPRequestHandler):
    server_version = "soulforge-ui/0.1"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return json_response(
                self,
                200,
                {
                    "ok": True,
                    "serverInfo": f"root={ROOT} ui={UI_DIR}",
                },
            )

        # Static UI
        path = parsed.path
        if path == "/":
            path = "/index.html"
        fs_path = (UI_DIR / path.lstrip("/")).resolve()
        if not str(fs_path).startswith(str(UI_DIR)):
            self.send_error(403)
            return
        if not fs_path.exists() or fs_path.is_dir():
            self.send_error(404)
            return

        ctype = "text/plain"
        if fs_path.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        elif fs_path.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif fs_path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"

        data = fs_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            return json_response(self, 400, {"ok": False, "error": "invalid JSON"})

        if parsed.path not in ("/api/load", "/api/preview", "/api/apply"):
            return json_response(self, 404, {"ok": False, "error": "unknown endpoint"})

        soul_path = body.get("soulPath")
        if not soul_path:
            return json_response(self, 400, {"ok": False, "error": "missing soulPath"})

        soul_path = safe_path(soul_path)
        if not soul_path.exists():
            return json_response(self, 404, {"ok": False, "error": f"SOUL not found: {soul_path}"})

        base_text = read_text(soul_path)

        if parsed.path == "/api/load":
            return json_response(
                self,
                200,
                {"ok": True, "baseText": base_text, "serverInfo": f"soul={soul_path}"},
            )

        addendum_text = (body.get("addendumText") or "").strip()
        if not addendum_text:
            return json_response(self, 400, {"ok": False, "error": "empty addendumText"})

        ts = now_ts()
        combined_text = build_combined(base_text, addendum_text, ts)
        diff_text = unified_diff(base_text, combined_text, fromfile=str(soul_path), tofile=f"SOUL.md (combined {ts})")

        outputs_dir = ROOT / "outputs"
        seal_dir = ROOT / "soul-seal"

        add_out = outputs_dir / f"SOUL.ADDENDUM.{ts}.md"
        comb_out = outputs_dir / f"SOUL.COMBINED.{ts}.md"
        seal_out = seal_dir / f"{ts}.json"

        # Never clobber.
        for p in (add_out, comb_out, seal_out):
            if p.exists():
                return json_response(self, 409, {"ok": False, "error": f"refusing to overwrite: {p}"})

        outputs_dir.mkdir(parents=True, exist_ok=True)
        seal_dir.mkdir(parents=True, exist_ok=True)
        add_out.write_text(addendum_text.rstrip() + "\n", encoding="utf-8")
        comb_out.write_text(combined_text, encoding="utf-8")

        raw_inputs = body.get("rawInputs")

        seal = {
            "timestamp": ts,
            "inputs": {
                "soul_path": str(soul_path),
                "apply": bool(parsed.path == "/api/apply"),
                "addendum_title": (body.get("addendumTitle") or "").strip(),
                "raw_inputs": raw_inputs,
            },
            "hashes": {
                "base_sha256": sha256_text(base_text),
                "addendum_sha256": sha256_text(addendum_text),
                "combined_sha256": sha256_text(combined_text),
            },
            "artifacts": {
                "addendum_out": str(add_out),
                "combined_out": str(comb_out),
            },
        }
        seal_out.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # Apply only on /api/apply
        if parsed.path == "/api/apply":
            backup = soul_path.with_name(f"SOUL.backup.{ts}.md")
            if backup.exists():
                return json_response(self, 409, {"ok": False, "error": f"backup exists: {backup}"})
            backup.write_text(base_text, encoding="utf-8")
            soul_path.write_text(combined_text, encoding="utf-8")

        return json_response(
            self,
            200,
            {
                "ok": True,
                "baseText": base_text,
                "combinedText": combined_text,
                "diffText": diff_text,
                "sealPath": str(seal_out),
                "serverInfo": f"soul={soul_path} outputs={outputs_dir} seal={seal_dir}",
            },
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=18991)
    args = ap.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Soul Forge UI: http://{args.host}:{args.port}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
