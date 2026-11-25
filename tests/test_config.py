from __future__ import annotations

from pathlib import Path

import pytest

from soulforge.config import ConfigError, load_config
from tests.conftest import ROOT


def test_example_config_loads_and_resolves_next_to_the_file() -> None:
    path = ROOT / "config.example.toml"
    config = load_config(path)
    assert config.provider == "demo"
    assert config.api_key_env == "SOULFORGE_API_KEY"
    assert config.model == "demo-local"
    assert config.temperature == 0.2
    assert config.scenarios_dir == (ROOT / "scenarios").resolve()
    assert config.rubric_path == (ROOT / "rubrics" / "scoring.md").resolve()
    assert config.personality.warmth == 6
    assert config.personality.directness == 7
    assert config.personality.boundary_strictness == 8
    assert config.personality.always[0].startswith("Give the next concrete step")
    text = path.read_text(encoding="utf-8")
    assert "api_key =" not in text
    assert "api_key=" not in text


def test_config_refuses_inline_secret_without_echoing_it(tmp_path: Path) -> None:
    secret = "this-is-the-secret-value"
    path = tmp_path / "unsafe.toml"
    path.write_text(
        "[model]\napi_key = \"" + secret + "\"\nprovider = \"demo\"\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match=r"Refusing field model\.api_key") as raised:
        load_config(path)
    assert secret not in str(raised.value)


def test_config_refuses_nested_token(tmp_path: Path) -> None:
    secret = "nested-token-value"
    path = tmp_path / "nested.toml"
    path.write_text(
        "[model.headers]\ntoken = \"" + secret + "\"\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="model.headers.token") as raised:
        load_config(path)
    assert secret not in str(raised.value)


def test_config_rejects_axis_out_of_range(tmp_path: Path) -> None:
    text = (ROOT / "config.example.toml").read_text(encoding="utf-8")
    text = text.replace("warmth = 6", "warmth = 11", 1)
    path = tmp_path / "bad-axis.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="warmth"):
        load_config(path)


def test_config_rejects_unknown_provider(tmp_path: Path) -> None:
    text = (ROOT / "config.example.toml").read_text(encoding="utf-8")
    text = text.replace('provider = "demo"', 'provider = "mystery"', 1)
    path = tmp_path / "bad-provider.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="provider"):
        load_config(path)
