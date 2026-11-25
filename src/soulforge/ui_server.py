"""Local UI server for additive SOUL.md upgrades.

Stdlib only. Preview writes artifacts; the base file changes only on
``/api/apply``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from soulforge.additive import read_text, run_addendum
from soulforge.paths import repo_root


@dataclass(frozen=True)
class AppPaths:
    ui_dir: Path
    outputs_dir: Path
    seal_dir: Path


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def json_response(handler: BaseHTTPRequestHandler, code: int, payload: Mapping[str, object]) -> None:
    data = (json.dumps(payload) + "\n").encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class SoulForgeServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], paths: AppPaths) -> None:
        super().__init__(server_address, Handler)
        self.paths = paths


class Handler(BaseHTTPRequestHandler):
    server_version = "soulforge-ui/0.1"

    def _paths(self) -> AppPaths:
        paths = getattr(self.server, "paths", None)
        if not isinstance(paths, AppPaths):
            raise RuntimeError("server is missing paths")
        return paths

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        paths = self._paths()
        if parsed.path == "/api/health":
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "serverInfo": f"ui={paths.ui_dir}",
                },
            )
            return

        request_path = "/index.html" if parsed.path == "/" else parsed.path
        relative = request_path.lstrip("/")
        fs_path = (paths.ui_dir / relative).resolve()
        if not is_within(fs_path, paths.ui_dir):
            self.send_error(403)
            return
        if not fs_path.is_file():
            self.send_error(404)
            return

        content_type = "text/plain; charset=utf-8"
        if fs_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif fs_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif fs_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif fs_path.suffix == ".png":
            content_type = "image/png"

        data = fs_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            json_response(self, 400, {"ok": False, "error": "invalid JSON"})
            return
        if not isinstance(body, dict):
            json_response(self, 400, {"ok": False, "error": "invalid JSON"})
            return

        if parsed.path not in ("/api/load", "/api/preview", "/api/apply"):
            json_response(self, 404, {"ok": False, "error": "unknown endpoint"})
            return

        soul_value = body.get("soulPath")
        if not isinstance(soul_value, str) or not soul_value.strip():
            json_response(self, 400, {"ok": False, "error": "missing soulPath"})
            return
        soul_path = Path(soul_value).expanduser().resolve()
        if not soul_path.is_file():
            json_response(self, 404, {"ok": False, "error": f"SOUL not found: {soul_path}"})
            return

        if parsed.path == "/api/load":
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "baseText": read_text(soul_path),
                    "serverInfo": f"soul={soul_path}",
                },
            )
            return

        addendum_value = body.get("addendumText")
        addendum_text = addendum_value.strip() if isinstance(addendum_value, str) else ""
        if not addendum_text:
            json_response(self, 400, {"ok": False, "error": "empty addendumText"})
            return

        paths = self._paths()
        title = body.get("addendumTitle")
        title_text = title.strip() if isinstance(title, str) else ""
        extra: dict[str, object] = {
            "addendum_title": title_text,
            "raw_inputs": body.get("rawInputs"),
        }
        try:
            result = run_addendum(
                soul_path=soul_path,
                addendum_text=addendum_text,
                outputs_dir=paths.outputs_dir,
                seal_dir=paths.seal_dir,
                apply=parsed.path == "/api/apply",
                extra_inputs=extra,
            )
        except FileExistsError as exc:
            json_response(self, 409, {"ok": False, "error": str(exc)})
            return
        except (FileNotFoundError, ValueError) as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})
            return

        json_response(
            self,
            200,
            {
                "ok": True,
                "baseText": result.base_text,
                "combinedText": result.combined_text,
                "diffText": result.diff_text,
                "sealPath": str(result.seal_out),
                "serverInfo": (
                    f"soul={soul_path} outputs={paths.outputs_dir} seal={paths.seal_dir}"
                ),
            },
        )


def default_paths() -> AppPaths:
    root = repo_root()
    return AppPaths(
        ui_dir=root / "ui",
        outputs_dir=root / "outputs",
        seal_dir=root / "soul-seal",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="soulforge-ui")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18991)
    args = parser.parse_args(argv)
    server = SoulForgeServer((args.host, args.port), default_paths())
    print(f"Soul Forge UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
