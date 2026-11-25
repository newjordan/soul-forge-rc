from __future__ import annotations

from pathlib import Path

import pytest

from soulforge.parse import ParseError, load_scenarios, parse_rubric, parse_scenario
from tests.conftest import ROOT


def test_shipped_scenarios_and_rubric() -> None:
    scenarios = load_scenarios(ROOT / "scenarios")
    assert [item.id for item in scenarios] == [
        "01-user-stressed",
        "02-user-wants-blunt-truth",
    ]
    stressed, blunt = scenarios
    assert stressed.prompt.startswith("I")
    assert "overwhelmed" in stressed.prompt
    assert stressed.prompt[0] not in "\"'“”"
    assert len(stressed.good_looks_like) == 4
    assert "is this idea bad" in blunt.prompt
    assert any("cruelty" in item for item in blunt.good_looks_like)

    rubric = parse_rubric(ROOT / "rubrics" / "scoring.md")
    assert [item.name for item in rubric] == [
        "Helpfulness",
        "Clarity",
        "Tone fit",
        "Safety/boundaries",
        "Delight",
    ]


def test_parse_scenario_rejects_missing_prompt(tmp_path: Path) -> None:
    path = tmp_path / "bad.md"
    path.write_text("# Title\n\n## What good looks like\n\n- A bullet\n", encoding="utf-8")
    with pytest.raises(ParseError, match="Prompt"):
        parse_scenario(path)


def test_load_scenarios_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="no scenario"):
        load_scenarios(tmp_path)
