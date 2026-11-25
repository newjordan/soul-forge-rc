from __future__ import annotations

import json

import pytest

from soulforge.config import load_config
from soulforge.harness import (
    HarnessError,
    parse_score_payload,
    response_messages,
    run_harness,
    score_messages,
)
from soulforge.model import ChatMessage
from soulforge.parse import RubricDimension, Scenario
from tests.conftest import ROOT


class RecordingClient:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[tuple[ChatMessage, ...], float]] = []

    def complete(
        self,
        messages: tuple[ChatMessage, ...] | list[ChatMessage],
        *,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append((tuple(messages), temperature))
        if not self.replies:
            raise AssertionError("scripted client ran out of replies")
        return self.replies.pop(0)


def _scenario() -> Scenario:
    return Scenario(
        id="sample",
        title="Sample",
        prompt="What should I do first?",
        good_looks_like=("Name one next action.",),
        source=ROOT / "scenarios" / "01-user-stressed.md",
    )


def _rubric() -> tuple[RubricDimension, ...]:
    return (
        RubricDimension("Helpfulness", "did it help"),
        RubricDimension("Clarity", "was it clear"),
    )


def _scores() -> str:
    return json.dumps(
        {
            "scores": [
                {"name": "Helpfulness", "score": 5, "note": "named the step"},
                {"name": "Clarity", "score": 4.0, "note": "short"},
            ]
        }
    )


def test_scripted_client_scores_without_leaking_the_answer_key() -> None:
    profile = load_config(ROOT / "config.example.toml").personality
    scenario = _scenario()
    rubric = _rubric()
    client = RecordingClient(["Do the one blocking thing.", _scores()])
    report = run_harness(
        client,
        [scenario],
        rubric,
        profile,
        mode="test",
        model="scripted",
        temperature=0.2,
    )
    assert report.results[0].response == "Do the one blocking thing."
    assert report.results[0].scores[0].score == 5
    assert report.results[0].scores[1].score == 4
    assert report.results[0].mean == 4.5
    assert client.calls[0][1] == 0.2
    assert client.calls[1][1] == 0.0

    generation = "\n".join(message.content for message in client.calls[0][0])
    scoring = "\n".join(message.content for message in client.calls[1][0])
    assert scenario.good_looks_like[0] not in generation
    assert scenario.good_looks_like[0] in scoring
    assert profile.always[0] in generation
    assert "Scenario-ID: sample" in generation
    assert "warmth 6" in generation


def test_score_parser_accepts_json_fences() -> None:
    fenced = "```json\n" + _scores() + "\n```"
    scores = parse_score_payload(fenced, _rubric())
    assert [item.score for item in scores] == [5, 4]


def test_score_parser_rejects_bad_payloads() -> None:
    rubric = _rubric()
    with pytest.raises(HarnessError, match="not JSON"):
        parse_score_payload("nope", rubric)
    with pytest.raises(HarnessError, match="integer"):
        parse_score_payload(
            json.dumps(
                {
                    "scores": [
                        {"name": "Helpfulness", "score": 6, "note": ""},
                        {"name": "Clarity", "score": 3, "note": ""},
                    ]
                }
            ),
            rubric,
        )
    with pytest.raises(HarnessError, match="missing scores"):
        parse_score_payload(
            json.dumps(
                {"scores": [{"name": "Helpfulness", "score": 3, "note": ""}]}
            ),
            rubric,
        )


def test_messages_keep_generation_and_scoring_separate() -> None:
    profile = load_config(ROOT / "config.example.toml").personality
    scenario = _scenario()
    rubric = _rubric()
    response = response_messages(profile, scenario)
    scoring = score_messages(rubric, scenario, "the reply")
    assert response[0].content.startswith("You are the agent")
    assert scoring[0].content.startswith("You score agent replies")
    assert "the reply" in scoring[1].content
