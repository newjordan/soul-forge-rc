"""Parse the markdown scenarios and rubric shipped with the repo."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class ParseError(ValueError):
    """A scenario or rubric file was not in the expected shape."""


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    prompt: str
    good_looks_like: tuple[str, ...]
    source: Path


@dataclass(frozen=True)
class RubricDimension:
    name: str
    description: str


_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_PROMPT_RE = re.compile(r"^\*\*Prompt:\*\*\s*(.+?)\s*$", re.MULTILINE)
_GOOD_HEADING_RE = re.compile(
    r"^##\s+What\s+.+good.+\s+looks like\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$")
_DIMENSION_RE = re.compile(
    r"^\d+\)\s+\*\*(.+?)\*\*\s+[—–-]\s+(.+?)\s*$",
    re.MULTILINE,
)
_WRAP_QUOTES = "\"'“”‘’"


def _strip_wrapping_quotes(text: str) -> str:
    value = text.strip()
    if len(value) >= 2 and value[0] in _WRAP_QUOTES and value[-1] in _WRAP_QUOTES:
        return value[1:-1].strip()
    return value


def parse_scenario(path: Path) -> Scenario:
    text = path.read_text(encoding="utf-8")
    title_match = _TITLE_RE.search(text)
    if title_match is None:
        raise ParseError(f"{path}: missing a level-1 heading")
    prompt_match = _PROMPT_RE.search(text)
    if prompt_match is None:
        raise ParseError(f"{path}: missing a **Prompt:** line")
    heading = _GOOD_HEADING_RE.search(text)
    if heading is None:
        raise ParseError(f"{path}: missing a 'what good looks like' section")
    rest = text[heading.end() :]
    next_heading = re.search(r"^##\s+", rest, re.MULTILINE)
    section = rest[: next_heading.start()] if next_heading else rest
    bullets: list[str] = []
    for line in section.splitlines():
        bullet = _BULLET_RE.match(line.strip())
        if bullet:
            bullets.append(bullet.group(1).strip())
    if not bullets:
        raise ParseError(f"{path}: 'what good looks like' has no bullets")
    return Scenario(
        id=path.stem,
        title=title_match.group(1).strip(),
        prompt=_strip_wrapping_quotes(prompt_match.group(1)),
        good_looks_like=tuple(bullets),
        source=path,
    )


def load_scenarios(directory: Path) -> tuple[Scenario, ...]:
    if not directory.is_dir():
        raise ParseError(f"scenarios directory not found: {directory}")
    paths = sorted(path for path in directory.glob("*.md") if path.is_file())
    if not paths:
        raise ParseError(f"no scenario markdown files in {directory}")
    return tuple(parse_scenario(path) for path in paths)


def parse_rubric(path: Path) -> tuple[RubricDimension, ...]:
    if not path.is_file():
        raise ParseError(f"rubric not found: {path}")
    text = path.read_text(encoding="utf-8")
    dimensions = [
        RubricDimension(name=match.group(1).strip(), description=match.group(2).strip())
        for match in _DIMENSION_RE.finditer(text)
    ]
    if not dimensions:
        raise ParseError(f"{path}: no numbered rubric dimensions")
    return tuple(dimensions)
