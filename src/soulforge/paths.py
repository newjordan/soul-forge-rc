"""Locate the repository when running from a checkout."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Return the checkout root when this file lives in ``src/soulforge``.

    Falls back to the current working directory so an installed copy can
    still be pointed at a local ``scenarios/`` tree.
    """

    here = Path(__file__).resolve()
    candidate = here.parents[2]
    if (candidate / "pyproject.toml").is_file() and (candidate / "scenarios").is_dir():
        return candidate
    return Path.cwd()
