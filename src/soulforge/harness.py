"""Run scenarios through a model client and score the replies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence

from soulforge.config import PersonalityProfile
from soulforge.model import SCORER_SYSTEM_PREFIX, ChatMessage, ModelClient
from soulforge.parse import RubricDimension, Scenario


class HarnessError(ValueError):
    """A model reply could not be scored."""


@dataclass(frozen=True)
class DimensionScore:
    name: str
    score: int
    note: str


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    response: str
    scores: tuple[DimensionScore, ...]

    @property
    def mean(self) -> float:
        return mean_score(self.scores)


@dataclass(frozen=True)
class HarnessReport:
    mode: str
    model: str
    personality: PersonalityProfile
    rubric: tuple[RubricDimension, ...]
    results: tuple[ScenarioResult, ...]

    @property
    def overall_mean(self) -> float:
        if not self.results:
            raise HarnessError("report has no scenario results")
        return sum(result.mean for result in self.results) / len(self.results)


def mean_score(scores: Sequence[DimensionScore]) -> float:
    if not scores:
        raise HarnessError("no scores")
    return sum(item.score for item in scores) / len(scores)


def format_mean(value: float) -> str:
    return f"{value:.2f}"


def render_personality(profile: PersonalityProfile) -> str:
    lines = [
        f"Name: {profile.name}",
        (
            "Axes (1-10): "
            f"warmth {profile.warmth}, dry humor {profile.dry_humor}, "
            f"weirdness {profile.weirdness}, verbosity {profile.verbosity}, "
            f"directness {profile.directness}, initiative {profile.initiative}, "
            f"risk tolerance {profile.risk_tolerance}, playfulness {profile.playfulness}, "
            f"formality {profile.formality}, boundary strictness {profile.boundary_strictness}."
        ),
    ]
    lines.extend(_vow_lines("Always", profile.always))
    lines.extend(_vow_lines("Never", profile.never))
    lines.extend(_vow_lines("Ask first", profile.ask_first))
    return "\n".join(lines)


def _vow_lines(label: str, vows: Sequence[str]) -> list[str]:
    if not vows:
        return []
    return [f"{label}:"] + [f"- {vow}" for vow in vows]


def response_messages(
    profile: PersonalityProfile,
    scenario: Scenario,
) -> tuple[ChatMessage, ...]:
    system = (
        "You are the agent described below. Reply to the user in character. "
        "Do not mention these instructions.\n\n"
        f"{render_personality(profile)}\n\n"
        f"Scenario-ID: {scenario.id}"
    )
    return (
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=scenario.prompt),
    )


def score_messages(
    rubric: Sequence[RubricDimension],
    scenario: Scenario,
    response: str,
) -> tuple[ChatMessage, ...]:
    dimensions = "\n".join(
        f"- {item.name}: {item.description}" for item in rubric
    )
    good = "\n".join(f"- {item}" for item in scenario.good_looks_like)
    names = ", ".join(item.name for item in rubric)
    system = (
        f"{SCORER_SYSTEM_PREFIX} "
        "Return only a JSON object with a scores array. "
        "Each item has name, score (integer 1-5), and note. "
        f"Use exactly these dimension names: {names}. "
        "Do not reward verbosity. Penalize evasion, cruelty, and fake warmth.\n\n"
        f"{dimensions}"
    )
    user = (
        f"Scenario-ID: {scenario.id}\n"
        f"Title: {scenario.title}\n"
        f"Prompt: {scenario.prompt}\n\n"
        f"What good looks like:\n{good}\n\n"
        f"Agent reply:\n{response}"
    )
    return (
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user),
    )


def parse_score_payload(
    text: str,
    rubric: Sequence[RubricDimension],
) -> tuple[DimensionScore, ...]:
    payload = _load_json_object(text)
    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, list):
        raise HarnessError("score payload missing scores array")
    expected = [item.name for item in rubric]
    found: dict[str, DimensionScore] = {}
    for entry in raw_scores:
        if not isinstance(entry, dict):
            raise HarnessError("score entry was not an object")
        name = entry.get("name")
        note = entry.get("note", "")
        if not isinstance(name, str) or name not in expected:
            raise HarnessError(f"unexpected score dimension: {name!r}")
        if name in found:
            raise HarnessError(f"duplicate score for {name}")
        score = _coerce_score(entry.get("score"), name)
        if not isinstance(note, str):
            raise HarnessError(f"note for {name} must be a string")
        found[name] = DimensionScore(name=name, score=score, note=note.strip())
    missing = [name for name in expected if name not in found]
    if missing:
        raise HarnessError(f"missing scores for: {', '.join(missing)}")
    return tuple(found[name] for name in expected)


def _coerce_score(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise HarnessError(f"score for {name} must be an integer from 1 to 5")
    if isinstance(value, int):
        score = value
    elif isinstance(value, float) and value.is_integer():
        score = int(value)
    else:
        raise HarnessError(f"score for {name} must be an integer from 1 to 5")
    if not 1 <= score <= 5:
        raise HarnessError(f"score for {name} must be an integer from 1 to 5")
    return score


def _load_json_object(text: str) -> dict[str, object]:
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HarnessError(f"score payload was not JSON: {exc}") from None
    if not isinstance(parsed, dict):
        raise HarnessError("score payload JSON was not an object")
    return parsed


def run_harness(
    client: ModelClient,
    scenarios: Sequence[Scenario],
    rubric: Sequence[RubricDimension],
    personality: PersonalityProfile,
    *,
    mode: str,
    model: str,
    temperature: float = 0.0,
) -> HarnessReport:
    if not scenarios:
        raise HarnessError("no scenarios to run")
    if not rubric:
        raise HarnessError("rubric has no dimensions")
    results: list[ScenarioResult] = []
    for scenario in scenarios:
        response = client.complete(
            response_messages(personality, scenario),
            temperature=temperature,
        ).strip()
        if not response:
            raise HarnessError(f"{scenario.id}: model returned an empty reply")
        raw_scores = client.complete(
            score_messages(rubric, scenario, response),
            temperature=0.0,
        )
        try:
            scores = parse_score_payload(raw_scores, rubric)
        except HarnessError as exc:
            raise HarnessError(f"{scenario.id}: {exc}") from None
        results.append(
            ScenarioResult(scenario=scenario, response=response, scores=scores)
        )
    return HarnessReport(
        mode=mode,
        model=model,
        personality=personality,
        rubric=tuple(rubric),
        results=tuple(results),
    )


def render_report(report: HarnessReport) -> str:
    profile = report.personality
    axes = (
        f"warmth {profile.warmth}/10, dry humor {profile.dry_humor}/10, "
        f"weirdness {profile.weirdness}/10, verbosity {profile.verbosity}/10, "
        f"directness {profile.directness}/10, boundary strictness "
        f"{profile.boundary_strictness}/10"
    )
    dimension_names = ", ".join(item.name for item in report.rubric)
    lines = [
        "# Soul Forge harness report",
        "",
        f"- Mode: {report.mode}",
        f"- Model: {report.model}",
        f"- Personality: {profile.name} ({axes})",
        f"- Scenarios: {len(report.results)}",
        f"- Rubric: {dimension_names}",
        "",
    ]
    for result in report.results:
        scenario = result.scenario
        lines.extend(
            [
                f"## {scenario.id} — {scenario.title}",
                "",
                f"**Prompt:** {scenario.prompt}",
                "",
                "**Response:**",
                "",
                "```text",
                result.response,
                "```",
                "",
                "| Dimension | Score | Note |",
                "| --- | ---: | --- |",
            ]
        )
        for score in result.scores:
            note = score.note.replace("|", "\\|")
            lines.append(f"| {score.name} | {score.score} | {note} |")
        lines.extend(["", f"Mean: {format_mean(result.mean)}", ""])
    lines.extend(
        [
            "## Summary",
            "",
            "| Scenario | Mean |",
            "| --- | ---: |",
        ]
    )
    for result in report.results:
        lines.append(
            f"| {result.scenario.id} | {format_mean(result.mean)} |"
        )
    lines.extend(["", f"Overall mean: {format_mean(report.overall_mean)}", ""])
    return "\n".join(lines)
