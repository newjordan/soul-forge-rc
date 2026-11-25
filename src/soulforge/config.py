"""Load harness configuration.

API keys are the name of an environment variable, never the secret itself.
A config file that contains a raw key is rejected so it cannot be committed
by accident and then loaded.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class ConfigError(ValueError):
    """The config file is missing, malformed, or unsafe to load."""


_SECRET_FIELDS = frozenset(
    {"api_key", "apikey", "api_token", "secret", "token", "access_token"}
)
_AXES = (
    "warmth",
    "dry_humor",
    "weirdness",
    "verbosity",
    "directness",
    "initiative",
    "risk_tolerance",
    "playfulness",
    "formality",
    "boundary_strictness",
)


@dataclass(frozen=True)
class PersonalityProfile:
    name: str
    warmth: int
    dry_humor: int
    weirdness: int
    verbosity: int
    directness: int
    initiative: int
    risk_tolerance: int
    playfulness: int
    formality: int
    boundary_strictness: int
    always: tuple[str, ...]
    never: tuple[str, ...]
    ask_first: tuple[str, ...]

    def axis_value(self, axis: str) -> int:
        value = getattr(self, axis)
        if not isinstance(value, int):
            raise ConfigError(f"personality axis {axis} is not an int")
        return value


@dataclass(frozen=True)
class HarnessConfig:
    provider: str
    model: str
    base_url: str
    api_key_env: str
    temperature: float
    scenarios_dir: Path
    rubric_path: Path
    personality: PersonalityProfile


def load_config(path: Path) -> HarnessConfig:
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"config root must be a table: {path}")
    _reject_secret_fields(raw)
    model = _table(raw, "model", path)
    paths = _table(raw, "paths", path)
    personality_raw = _table(raw, "personality", path)
    provider = _string(model, "provider", "model.provider")
    if provider not in {"demo", "openai"}:
        raise ConfigError("model.provider must be 'demo' or 'openai'")
    base = path.parent
    scenarios_dir = _resolve(base, _string(paths, "scenarios_dir", "paths.scenarios_dir"))
    rubric_path = _resolve(base, _string(paths, "rubric_path", "paths.rubric_path"))
    temperature = model.get("temperature", 0.2)
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
        raise ConfigError("model.temperature must be a number")
    if not 0.0 <= float(temperature) <= 2.0:
        raise ConfigError("model.temperature must be between 0 and 2")
    return HarnessConfig(
        provider=provider,
        model=_string(model, "model", "model.model"),
        base_url=_string(model, "base_url", "model.base_url"),
        api_key_env=_string(model, "api_key_env", "model.api_key_env"),
        temperature=float(temperature),
        scenarios_dir=scenarios_dir,
        rubric_path=rubric_path,
        personality=_personality(personality_raw),
    )


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _table(raw: Mapping[str, object], key: str, path: Path) -> Mapping[str, object]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: missing [{key}] table")
    return value


def _string(table: Mapping[str, object], key: str, label: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} must be a non-empty string")
    return value.strip()


def _personality(table: Mapping[str, object]) -> PersonalityProfile:
    axes: dict[str, int] = {}
    for axis in _AXES:
        value = table.get(axis)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"personality.{axis} must be an integer from 1 to 10")
        if not 1 <= value <= 10:
            raise ConfigError(f"personality.{axis} must be from 1 to 10")
        axes[axis] = value
    name = table.get("name", "default")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError("personality.name must be a non-empty string")
    return PersonalityProfile(
        name=name.strip(),
        warmth=axes["warmth"],
        dry_humor=axes["dry_humor"],
        weirdness=axes["weirdness"],
        verbosity=axes["verbosity"],
        directness=axes["directness"],
        initiative=axes["initiative"],
        risk_tolerance=axes["risk_tolerance"],
        playfulness=axes["playfulness"],
        formality=axes["formality"],
        boundary_strictness=axes["boundary_strictness"],
        always=_string_list(table.get("always"), "personality.always"),
        never=_string_list(table.get("never"), "personality.never"),
        ask_first=_string_list(table.get("ask_first"), "personality.ask_first"),
    )


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ConfigError(f"{label} must be an array of non-empty strings")
    return tuple(item.strip() for item in value)


def _reject_secret_fields(value: object, prefix: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                continue
            normalized = key.lower().replace("-", "_")
            label = f"{prefix}{key}"
            if normalized in _SECRET_FIELDS:
                raise ConfigError(
                    f"Refusing field {label}: API keys belong in the environment, "
                    "not the config file."
                )
            _reject_secret_fields(child, prefix=f"{label}.")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_fields(child, prefix=f"{prefix}[{index}].")
