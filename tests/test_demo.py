from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from soulforge.cli import main
from soulforge.demo import demo_report_text
from tests.conftest import ROOT, SRC


def _clear_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOULFORGE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_demo_report_matches_the_documented_example() -> None:
    fixture = (ROOT / "tests" / "fixtures" / "demo_report.md").read_text(encoding="utf-8")
    assert demo_report_text() == fixture
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert fixture.strip() in readme


def test_demo_is_deterministic_and_ignores_api_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("demo mode tried to use the network")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    _clear_keys(monkeypatch)
    monkeypatch.setenv("SOULFORGE_API_KEY", "sentinel-should-not-appear")

    first = demo_report_text()
    second = demo_report_text()
    assert first == second
    assert "Mode: demo (offline)" in first
    assert "Model: demo-local" in first
    assert "01-user-stressed" in first
    assert "02-user-wants-blunt-truth" in first
    assert "Mean: 4.40" in first
    assert "Mean: 4.20" in first
    assert "Overall mean: 4.30" in first
    assert "sentinel-should-not-appear" not in first
    assert "sk-" not in first


def test_demo_command_forces_offline_even_if_config_says_openai(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("demo mode tried to use the network")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    _clear_keys(monkeypatch)
    text = (ROOT / "config.example.toml").read_text(encoding="utf-8")
    text = text.replace('provider = "demo"', 'provider = "openai"', 1)
    path = tmp_path / "live.toml"
    # Keep scenario paths pointed at the repo, not the temp directory.
    text = text.replace('scenarios_dir = "scenarios"', f'scenarios_dir = "{ROOT / "scenarios"}"', 1)
    text = text.replace(
        'rubric_path = "rubrics/scoring.md"',
        f'rubric_path = "{ROOT / "rubrics" / "scoring.md"}"',
        1,
    )
    path.write_text(text, encoding="utf-8")
    code = main(["demo", "--config", str(path)])
    assert code == 0


def test_score_openai_without_a_key_exits_before_the_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("score tried to use the network without a key")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    _clear_keys(monkeypatch)
    text = (ROOT / "config.example.toml").read_text(encoding="utf-8")
    text = text.replace('provider = "demo"', 'provider = "openai"', 1)
    path = tmp_path / "live.toml"
    path.write_text(text, encoding="utf-8")
    code = main(["score", "--config", str(path)])
    assert code == 2
    error = capsys.readouterr().err
    assert "SOULFORGE_API_KEY" in error
    assert "sk-" not in error


def test_score_demo_provider_matches_the_demo_command(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_keys(monkeypatch)
    code = main(["score", "--config", str(ROOT / "config.example.toml")])
    assert code == 0
    assert capsys.readouterr().out == demo_report_text()


def test_module_demo_needs_no_key() -> None:
    env = os.environ.copy()
    env.pop("SOULFORGE_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env["PYTHONPATH"] = str(SRC)
    completed = subprocess.run(
        [sys.executable, "-m", "soulforge", "demo"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Mode: demo (offline)" in completed.stdout
    assert "sk-" not in completed.stdout
    assert completed.stderr == ""


def test_additive_wrapper_help() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "soulforge_additive.py"), "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "--addendum-path" in completed.stdout
    assert "--apply" in completed.stdout
