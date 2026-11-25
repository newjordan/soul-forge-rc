from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import ROOT

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "outputs",
    "soul-seal",
    "dist",
    "build",
}

# Well-known credential prefixes. The patterns themselves are not credentials.
# Inline config keys are rejected separately in test_config.py.
_TOKEN_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def test_repository_does_not_contain_credential_material() -> None:
    offenders: list[str] = []
    for path in _tracked_text_files(ROOT):
        text = path.read_text(encoding="utf-8")
        for pattern in _TOKEN_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(ROOT)} matches {pattern.pattern}")
    assert offenders == []


def test_gitignore_keeps_env_files_out() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in text.splitlines()
    assert "!.env.example" in text.splitlines()


def _tracked_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in _SKIP_DIRS or part.endswith(".egg-info") for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc"}:
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append(path)
    return files
