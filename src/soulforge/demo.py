"""Offline demo: score the shipped scenarios with the built-in client."""

from __future__ import annotations

from pathlib import Path

from soulforge.config import HarnessConfig, load_config
from soulforge.harness import HarnessReport, render_report, run_harness
from soulforge.model import DemoModelClient
from soulforge.parse import load_scenarios, parse_rubric
from soulforge.paths import repo_root


def default_config_path() -> Path:
    return repo_root() / "config.example.toml"


def run_demo(config_path: Path | None = None) -> HarnessReport:
    """Run the harness without a network call or an API key.

    ``config_path`` selects scenarios, the rubric, and the personality.
    The provider in that file is ignored: demo mode always uses
    ``DemoModelClient``.
    """

    path = default_config_path() if config_path is None else config_path
    config = load_config(path)
    return run_configured(config, client=DemoModelClient(), mode="demo (offline)")


def run_configured(
    config: HarnessConfig,
    *,
    mode: str,
    client: DemoModelClient | None = None,
) -> HarnessReport:
    model_client = client if client is not None else DemoModelClient()
    scenarios = load_scenarios(config.scenarios_dir)
    rubric = parse_rubric(config.rubric_path)
    return run_harness(
        model_client,
        scenarios,
        rubric,
        config.personality,
        mode=mode,
        model=model_client.model_name,
        temperature=config.temperature,
    )


def demo_report_text(config_path: Path | None = None) -> str:
    return render_report(run_demo(config_path))
