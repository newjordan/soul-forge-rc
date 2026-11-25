from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from soulforge.ui_server import AppPaths, SoulForgeServer, is_within
from tests.conftest import ROOT


def test_path_jail() -> None:
    parent = Path("/tmp/soulforge-ui-parent")
    child = parent / "ui" / "index.html"
    assert is_within(child, parent / "ui")
    assert not is_within(parent / "secret.txt", parent / "ui")


def test_default_soul_path_is_local() -> None:
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert 'value="SOUL.md"' in html
    assert "/home/" not in html


def _request(
    port: int,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
) -> tuple[int, dict[str, object] | str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    if "application/json" in content_type:
        parsed = json.loads(raw.decode("utf-8"))
        assert isinstance(parsed, dict)
        return status, parsed
    return status, raw.decode("utf-8")


def test_preview_apply_and_static_ui(tmp_path: Path) -> None:
    soul = tmp_path / "SOUL.md"
    original = "# Soul\n\nBe brief.\n"
    soul.write_text(original, encoding="utf-8")
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<html>Soul Forge ok</html>", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("do-not-serve", encoding="utf-8")
    paths = AppPaths(
        ui_dir=ui,
        outputs_dir=tmp_path / "outputs",
        seal_dir=tmp_path / "seals",
    )
    server = SoulForgeServer(("127.0.0.1", 0), paths)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    try:
        status, page = _request(port, "/")
        assert status == 200
        assert page == "<html>Soul Forge ok</html>"

        status, health = _request(port, "/api/health")
        assert status == 200
        assert isinstance(health, dict)
        assert health["ok"] is True

        status, blocked = _request(port, "/../secret.txt")
        assert status == 403
        assert "do-not-serve" not in str(blocked)

        status, missing = _request(port, "/api/load", method="POST", body={"soulPath": str(tmp_path / "nope.md")})
        assert status == 404
        assert isinstance(missing, dict)
        assert missing["ok"] is False

        status, loaded = _request(port, "/api/load", method="POST", body={"soulPath": str(soul)})
        assert status == 200
        assert isinstance(loaded, dict)
        assert loaded["baseText"] == original

        status, empty = _request(
            port,
            "/api/preview",
            method="POST",
            body={"soulPath": str(soul), "addendumText": "  "},
        )
        assert status == 400

        status, preview = _request(
            port,
            "/api/preview",
            method="POST",
            body={
                "soulPath": str(soul),
                "addendumText": "Be warmer.\n",
                "addendumTitle": "Tune",
                "rawInputs": {"sliders": []},
            },
        )
        assert status == 200
        assert isinstance(preview, dict)
        assert preview["ok"] is True
        assert "Be warmer." in str(preview["combinedText"])
        assert soul.read_text(encoding="utf-8") == original
        seal = json.loads(Path(str(preview["sealPath"])).read_text(encoding="utf-8"))
        assert seal["inputs"]["apply"] is False
        assert seal["inputs"]["raw_inputs"] == {"sliders": []}

        status, applied = _request(
            port,
            "/api/apply",
            method="POST",
            body={"soulPath": str(soul), "addendumText": "Be warmer.\n"},
        )
        assert status == 200
        assert isinstance(applied, dict)
        assert applied["ok"] is True
        assert "Be warmer." in soul.read_text(encoding="utf-8")
        backups = list(tmp_path.glob("SOUL.backup.*.md"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == original
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
