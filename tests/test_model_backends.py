"""Meta-only endpoint configuration, safe call accounting, and optional open weights."""
import json
from dataclasses import replace

import httpx
import pytest

from faultline.config import Settings, get_settings
from faultline.meta import MetaClient, MetaError


def settings(tmp_path, **kwargs):
    original = Settings("private-test-key", "https://api.meta.test/v1", "muse-spark-1.3", "medium", False, tmp_path)
    return replace(original, **kwargs)


async def call(client, image_png=None):
    return await client.json_call(purpose="test", system="Return JSON.", user={"test": True},
                                  schema_name="test", schema={"type": "object"}, image_png=image_png)


def okay(request):
    model = json.loads(request.content)["model"]
    return httpx.Response(200, json={"model": model, "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                                     "choices": [{"message": {"content": '{"ok": true}'}}]})


@pytest.mark.asyncio
async def test_base_path_is_preserved(tmp_path):
    seen = []
    def handle(request):
        seen.append(request.url.path)
        return okay(request)
    client = MetaClient(settings(tmp_path), transport=httpx.MockTransport(handle))
    try:
        assert await call(client) == {"ok": True}
        assert seen == ["/v1/chat/completions"]
        assert client.calls[0]["success"] and client.calls[0]["input_tokens"] == 10
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_failed_attempts_count_and_do_not_echo_secrets(tmp_path):
    calls = 0
    def handle(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("private-test-key and user source", request=request)
        if calls == 2:
            return httpx.Response(503, text="private-test-key and user source")
        return okay(request)
    client = MetaClient(settings(tmp_path), transport=httpx.MockTransport(handle))
    try:
        assert await call(client) == {"ok": True}
        assert [c["status"] for c in client.calls] == ["transport_error", "http_error", "success"]
        assert all("seconds" in c for c in client.calls)
        assert "private-test-key" not in json.dumps(client.calls)
        assert "user source" not in json.dumps(client.calls)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_http_error_is_safe_and_not_retried_when_unauthorized(tmp_path):
    client = MetaClient(settings(tmp_path), transport=httpx.MockTransport(
        lambda request: httpx.Response(401, text="private-test-key")))
    try:
        with pytest.raises(MetaError, match="HTTP 401") as error:
            await call(client)
        assert "private-test-key" not in str(error.value)
        assert len(client.calls) == 1 and client.calls[0]["status"] == "http_error"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_redirect_is_not_followed(tmp_path):
    client = MetaClient(settings(tmp_path), transport=httpx.MockTransport(
        lambda request: httpx.Response(307, headers={"location": "https://other.example/steal"})))
    try:
        with pytest.raises(MetaError, match="HTTP 307"):
            await call(client)
        assert len(client.calls) == 1
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_local_open_weights_without_key_and_no_image_by_default(tmp_path):
    seen = []
    def handle(request):
        seen.append(request)
        return okay(request)
    config = settings(tmp_path, backend="open_weights", api_key=None, model="muse-glimmer",
                      base_url="http://127.0.0.1:11434/v1", supports_vision=False, json_mode="json_object")
    assert config.meta_configured
    client = MetaClient(config, transport=httpx.MockTransport(handle))
    try:
        assert await call(client, image_png=b"example") == {"ok": True}
        request = seen[0]
        body = json.loads(request.content)
        assert body["model"] == "muse-glimmer" and body["response_format"] == {"type": "json_object"}
        assert isinstance(body["messages"][1]["content"], str)
        assert "authorization" not in request.headers
        assert client.calls[0]["backend"] == "open_weights" and client.calls[0]["image_sent"] is False
    finally:
        await client.close()


@pytest.mark.parametrize("options", [
    {"model": "gpt-4o"}, {"model": "claude-sonnet"},
    {"backend": "open_weights", "model": "muse-spark-1.3"},
    {"backend": "other"}, {"base_url": "https://user:pass@api.meta.ai/v1"},
    {"base_url": "https://api.meta.ai/v1?key=abc"},
    {"backend": "open_weights", "model": "muse-glimmer", "base_url": "http://inference.example/v1"},
    {"backend": "open_weights", "model": "muse-glimmer", "base_url": "https://api.openai.com/v1"},
])
def test_non_meta_models_or_unsafe_endpoints_rejected(tmp_path, options):
    with pytest.raises(MetaError):
        MetaClient(settings(tmp_path, **options), transport=httpx.MockTransport(okay))


def test_real_meta_backend_cannot_be_redirected_to_unrelated_provider(tmp_path):
    with pytest.raises(MetaError, match="api.meta.ai"):
        MetaClient(settings(tmp_path, base_url="https://inference.example/v1"))


def test_env_backend_uses_separate_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("FAULTLINE_MODEL_BACKEND", "open_weights")
    monkeypatch.setenv("MODEL_API_KEY", "do-not-forward-meta-key")
    monkeypatch.setenv("META_OPEN_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.delenv("META_OPEN_API_KEY", raising=False)
    monkeypatch.setenv("META_OPEN_MODEL", "muse-glimmer")
    loaded = get_settings()
    assert loaded.api_key is None and loaded.model == "muse-glimmer" and loaded.meta_configured
    assert loaded.supports_vision is False


@pytest.mark.asyncio
async def test_another_meta_model_cannot_silently_replace_the_requested_model(tmp_path):
    def handle(request):
        return httpx.Response(200, json={"model": "muse-wonder-1.0",
            "choices": [{"message": {"content": '{"ok": true}'}}]})
    client = MetaClient(settings(tmp_path), transport=httpx.MockTransport(handle))
    try:
        with pytest.raises(MetaError):
            await call(client)
        assert all(not c["success"] and c["reported_model"] == "muse-wonder-1.0" for c in client.calls)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_baseten_hackathon_model_alias_is_sent_and_recorded_exactly(tmp_path):
    seen = []
    def handle(request):
        seen.append(request)
        return okay(request)
    alias = "meta-models/muse-spark-open-1026"
    config = settings(tmp_path, backend="open_weights", model=alias,
                      base_url="https://baseten.example.test/v1", api_key="test-partner-key")
    client = MetaClient(config, transport=httpx.MockTransport(handle))
    try:
        assert await call(client) == {"ok": True}
        assert json.loads(seen[0].content)["model"] == alias
        assert client.calls[0]["model"] == client.calls[0]["reported_model"] == alias
        assert client.calls[0]["backend"] == "open_weights"
    finally:
        await client.close()
