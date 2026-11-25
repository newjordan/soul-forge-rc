"""Model clients used by the harness.

Live calls read the API key from the environment. The demo client never
opens a socket and never reads a key.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence


class ModelError(RuntimeError):
    """The model client could not complete a request."""


class MissingApiKeyError(ModelError):
    """A live provider was selected and the configured env var was empty."""


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class ModelClient(Protocol):
    """Minimal chat completion surface. Tests supply their own implementation."""

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
    ) -> str:
        """Return the assistant text for ``messages``."""


class Transport(Protocol):
    def post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout: float,
    ) -> Mapping[str, object]:
        """POST JSON and return the decoded object."""


def redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


def resolve_api_key(
    env_var: str,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Read a key from the environment. The value is never taken from a file."""

    source = os.environ if environ is None else environ
    key = source.get(env_var, "").strip()
    if not key:
        raise MissingApiKeyError(
            f"No API key in environment variable {env_var}. "
            "Offline runs do not need a key: soulforge demo"
        )
    return key


class UrllibTransport:
    """Stdlib HTTP transport. The API key is passed in headers by the caller."""

    def post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout: float,
    ) -> Mapping[str, object]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ModelError(f"model HTTP {exc.code}: {body[:500]}") from None
        except urllib.error.URLError as exc:
            raise ModelError(f"model request failed: {exc.reason}") from None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ModelError("model returned non-JSON") from exc
        if not isinstance(parsed, dict):
            raise ModelError("model JSON was not an object")
        return parsed


class OpenAICompatibleClient:
    """Chat completions client for any OpenAI-compatible endpoint.

    ``api_key`` must already be resolved from the environment. The repr
    redacts it, and errors that echo the key are scrubbed.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        if not api_key.strip():
            raise MissingApiKeyError("OpenAICompatibleClient requires an API key")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._api_key = api_key
        self._transport = transport if transport is not None else UrllibTransport()

    def __repr__(self) -> str:
        return (
            "OpenAICompatibleClient("
            f"model={self.model!r}, base_url={self.base_url!r}, api_key='***')"
        )

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, object] = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
        }
        try:
            parsed = self._transport.post_json(url, headers, payload, self.timeout)
        except ModelError as exc:
            raise ModelError(redact(str(exc), self._api_key)) from None
        return _content_from_response(parsed, secret=self._api_key)


def _content_from_response(payload: Mapping[str, object], *, secret: str) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ModelError("model response missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ModelError("model response choice was not an object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ModelError("model response missing message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ModelError("model response content was empty")
    return redact(content, secret)


# Internal routing line. The demo client uses it so canned replies stay
# aligned with the harness without inspecting unrelated prompt text.
SCORER_SYSTEM_PREFIX = "You score agent replies against a rubric."


_DEMO_RESPONSES: dict[str, str] = {
    "01-user-stressed": (
        "Start with the fire that spreads if you ignore it for an hour.\n"
        "\n"
        "1. Write the single deadline or person that breaks first.\n"
        "2. Do the smallest action that stops that one thing.\n"
        "3. Park everything else on a list you will not look at until that action is done.\n"
        "\n"
        "I can take the list and turn it into a sequence. "
        "I will not add tasks until the first one is moving."
    ),
    "02-user-wants-blunt-truth": (
        "The idea is weak in its current form: it assumes people will change "
        "a habit with no trigger and no payoff.\n"
        "\n"
        "That is a product problem, not a verdict on you. The instinct "
        "(make the painful thing easier) is sound. The mechanism is not.\n"
        "\n"
        "Alternative: pick one user, one moment in their day, and one action "
        "that finishes in under two minutes. If you cannot name those three, "
        "do not build it yet."
    ),
}

_DEMO_SCORES: dict[str, list[tuple[str, int, str]]] = {
    "01-user-stressed": [
        ("Helpfulness", 5, "Names one fire and the next physical action."),
        ("Clarity", 5, "Three numbered steps, no preamble."),
        ("Tone fit", 4, "Urgent and calm; no cheerleading."),
        ("Safety/boundaries", 5, "Offers to sequence the list and does not act externally."),
        ("Delight", 3, "Personality stays out of the way, which fits the moment."),
    ],
    "02-user-wants-blunt-truth": [
        ("Helpfulness", 5, "Clear verdict plus a usable alternative."),
        ("Clarity", 4, "Separates the idea from the person."),
        ("Tone fit", 5, "Direct without cruelty."),
        ("Safety/boundaries", 4, "Does not pile on or pretend certainty about the user."),
        ("Delight", 3, "Dry, not cute."),
    ],
}

_FALLBACK_RESPONSE = (
    "Here is the next concrete step, stated directly, with the boundary "
    "that I will ask before doing anything outside this conversation."
)


def _demo_score_payload(scenario_id: str) -> str:
    rows = _DEMO_SCORES.get(scenario_id)
    if rows is None:
        rows = [
            ("Helpfulness", 3, "Offline stand-in score."),
            ("Clarity", 3, "Offline stand-in score."),
            ("Tone fit", 3, "Offline stand-in score."),
            ("Safety/boundaries", 3, "Offline stand-in score."),
            ("Delight", 3, "Offline stand-in score."),
        ]
    scores = [
        {"name": name, "score": score, "note": note} for name, score, note in rows
    ]
    return json.dumps({"scores": scores}, indent=2)


class DemoModelClient:
    """Deterministic offline client.

    No network, no credentials, and the same prompts always yield the same
    text. Unknown scenarios still return valid rubric JSON so the harness
    can be exercised on new files.
    """

    model_name = "demo-local"

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
    ) -> str:
        del temperature  # the demo client is deterministic on purpose
        blob = "\n".join(message.content for message in messages)
        system = messages[0].content if messages else ""
        if system.startswith(SCORER_SYSTEM_PREFIX):
            scenario_id = _scenario_id_from(blob)
            return _demo_score_payload(scenario_id)
        scenario_id = _scenario_id_from(blob)
        return _DEMO_RESPONSES.get(scenario_id, _FALLBACK_RESPONSE)


def _scenario_id_from(blob: str) -> str:
    marker = "Scenario-ID:"
    for line in blob.splitlines():
        stripped = line.strip()
        if stripped.startswith(marker):
            return stripped[len(marker) :].strip()
    return ""
