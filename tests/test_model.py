from __future__ import annotations

import urllib.request

import pytest

from soulforge.model import (
    ChatMessage,
    MissingApiKeyError,
    ModelError,
    OpenAICompatibleClient,
    resolve_api_key,
)


class _RecordingTransport:
    def __init__(self, payload: dict[str, object] | None = None, error: ModelError | None = None) -> None:
        self.payload = payload
        self.error = error
        self.urls: list[str] = []
        self.headers: list[dict[str, str]] = []
        self.bodies: list[dict[str, object]] = []

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout: float,
    ) -> dict[str, object]:
        self.urls.append(url)
        self.headers.append(dict(headers))
        self.bodies.append(dict(payload))
        if self.error is not None:
            raise self.error
        assert self.payload is not None
        return self.payload


def test_resolve_api_key_reads_the_mapping_it_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOULFORGE_API_KEY", "from-the-process-environment")
    assert (
        resolve_api_key(
            "SOULFORGE_API_KEY",
            {"SOULFORGE_API_KEY": "from-the-explicit-mapping"},
        )
        == "from-the-explicit-mapping"
    )


def test_resolve_api_key_rejects_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOULFORGE_API_KEY", "   ")
    with pytest.raises(MissingApiKeyError, match="SOULFORGE_API_KEY"):
        resolve_api_key("SOULFORGE_API_KEY")


def test_openai_client_sends_bearer_token_and_hides_it() -> None:
    secret = "unit-test-key"
    transport = _RecordingTransport(
        {
            "choices": [
                {"message": {"role": "assistant", "content": f"echo {secret} done"}}
            ]
        }
    )
    client = OpenAICompatibleClient(
        base_url="https://example.invalid/v1/",
        model="unit-model",
        api_key=secret,
        transport=transport,
    )
    assert secret not in repr(client)
    text = client.complete(
        [ChatMessage(role="user", content="hello")],
        temperature=0.2,
    )
    assert secret not in text
    assert text == "echo *** done"
    assert transport.urls == ["https://example.invalid/v1/chat/completions"]
    assert transport.headers[0]["Authorization"] == f"Bearer {secret}"
    assert transport.bodies[0]["model"] == "unit-model"
    assert transport.bodies[0]["temperature"] == 0.2
    encoded = str(transport.bodies[0])
    assert secret not in encoded


def test_openai_client_redacts_key_from_transport_errors() -> None:
    secret = "unit-test-key"
    transport = _RecordingTransport(error=ModelError(f"upstream rejected {secret}"))
    client = OpenAICompatibleClient(
        base_url="https://example.invalid/v1",
        model="unit-model",
        api_key=secret,
        transport=transport,
    )
    with pytest.raises(ModelError, match="upstream rejected") as raised:
        client.complete([ChatMessage(role="user", content="hello")])
    assert secret not in str(raised.value)
    assert "***" in str(raised.value)


def test_openai_client_rejects_empty_choices() -> None:
    transport = _RecordingTransport({"choices": []})
    client = OpenAICompatibleClient(
        base_url="https://example.invalid/v1",
        model="unit-model",
        api_key="unit-test-key",
        transport=transport,
    )
    with pytest.raises(ModelError, match="missing choices"):
        client.complete([ChatMessage(role="user", content="hello")])


def test_client_construction_does_not_open_a_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("network")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    OpenAICompatibleClient(
        base_url="https://example.invalid/v1",
        model="unit-model",
        api_key="unit-test-key",
    )
