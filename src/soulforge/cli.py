"""Command line entry points."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from soulforge import __version__
from soulforge.additive import add_arguments, main as additive_main
from soulforge.config import ConfigError, HarnessConfig, load_config
from soulforge.demo import demo_report_text
from soulforge.harness import HarnessError, render_report, run_harness
from soulforge.model import (
    DemoModelClient,
    ModelClient,
    ModelError,
    OpenAICompatibleClient,
    resolve_api_key,
)
from soulforge.parse import ParseError, load_scenarios, parse_rubric


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="soulforge",
        description="Personality tuning harness for AI agents.",
    )
    parser.add_argument("--version", action="version", version=f"soulforge {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser(
        "demo",
        help="Score the scenarios with the offline model client (no API key)",
    )
    demo.add_argument(
        "--config",
        type=Path,
        default=None,
        help="TOML config (default: config.example.toml). The provider is forced offline.",
    )

    score = subparsers.add_parser(
        "score",
        help="Score the scenarios with the model named in the TOML file",
    )
    score.add_argument("--config", type=Path, required=True)

    additive = subparsers.add_parser(
        "additive",
        help="Preview or apply a SOUL.md addendum",
    )
    add_arguments(additive)

    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "demo":
            print(demo_report_text(args.config), end="")
            return 0
        if args.command == "score":
            report_text = score_text(args.config)
            print(report_text, end="")
            return 0
        if args.command == "additive":
            return additive_main(_additive_argv(args))
    except (ConfigError, ParseError, HarnessError, ModelError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"error: unknown command {args.command}", file=sys.stderr)
    return 2


def score_text(config_path: Path) -> str:
    config = load_config(config_path)
    client = client_for_config(config)
    mode = "demo (offline)" if config.provider == "demo" else "live"
    model_name = config.model if config.provider == "openai" else DemoModelClient.model_name
    report = run_harness(
        client,
        load_scenarios(config.scenarios_dir),
        parse_rubric(config.rubric_path),
        config.personality,
        mode=mode,
        model=model_name,
        temperature=config.temperature,
    )
    return render_report(report)


def client_for_config(config: HarnessConfig) -> ModelClient:
    """Build the client named by the config.

    ``demo`` never reads the environment. ``openai`` reads only the env var
    named by ``api_key_env``.
    """

    if config.provider == "demo":
        return DemoModelClient()
    if config.provider == "openai":
        return OpenAICompatibleClient(
            base_url=config.base_url,
            model=config.model,
            api_key=resolve_api_key(config.api_key_env),
        )
    raise ConfigError("model.provider must be 'demo' or 'openai'")


def _additive_argv(args: argparse.Namespace) -> list[str]:
    argv = ["--soul-path", str(args.soul_path), "--addendum-path", str(args.addendum_path)]
    argv.extend(["--outputs-dir", str(args.outputs_dir), "--seal-dir", str(args.seal_dir)])
    if args.apply:
        argv.append("--apply")
    return argv
