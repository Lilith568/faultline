"""0.3 safeguards: model choice, model identity, signed-in privacy and settings fallback."""
import json
from dataclasses import replace

import httpx
import pytest

from faultline import server
from faultline.config import Settings
from faultline.hunt import Hunt
from faultline.meta import MetaClient, MetaError


def settings(tmp_path, **kwargs):
    base = Settings("private-test-key", "https://api.meta.test/v1", "muse-spark-1.3", "medium", False, tmp_path)
    return replace(base, **kwargs)


def answering(model_name, calls):
    def handle(request):
        calls.append(json.loads(request.content)["model"])
        return httpx.Response(200, json={"model": model_name, "choices": [{"message": {"content": '{"ok": true}'}}]})
    return httpx.MockTransport(handle)


async def ask(client):
    return await client.json_call(purpose="test", system="Return JSON.", user={}, schema_name="t",
                                  schema={"type": "object"})


@pytest.mark.asyncio
async def test_a_dated_snapshot_of_the_requested_model_is_accepted(tmp_path):
    calls = []
    client = MetaClient(settings(tmp_path), transport=answering("muse-spark-1.3-2026-10-20", calls))
    try:
        assert await ask(client) == {"ok": True}
        assert client.calls[0]["reported_model"] == "muse-spark-1.3-2026-10-20"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_another_model_fails_after_one_call_instead_of_three_billable_retries(tmp_path):
    calls = []
    client = MetaClient(settings(tmp_path), transport=answering("muse-wonder-1.0", calls))
    try:
        with pytest.raises(MetaError, match="another model"):
            await ask(client)
        assert len(calls) == 1
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_the_ui_can_choose_spark_or_wonder_but_nothing_else(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "get_settings", lambda: settings(tmp_path))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://localhost:8000") as c:
        config = (await c.get("/api/config")).json()
        assert config["models"] == ["muse-spark-1.3", "muse-wonder-1.0"]
        refused = await c.post("/api/hunts", headers={"Origin": "http://localhost:8000"}, json={
            "url": "http://localhost:8000/demo/search.html", "model": "gpt-4o"})
        assert refused.status_code == 400 and "muse-wonder-1.0" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_signed_in_pages_need_a_separate_opt_in_before_reaching_a_model(server_url, tmp_path):
    calls = []
    url = f"{server_url}/demo/checkout.html?mode=buggy"
    state = {"cookies": [{"name": "session", "value": "s", "domain": "127.0.0.1", "path": "/", "expires": -1}],
             "origins": []}
    report = await Hunt(url, planner="auto", rounds=1, settings=settings(tmp_path), storage_state=state,
                        meta_transport=answering("muse-spark-1.3", calls)).run()
    assert calls == [] and report["meta_calls"] == []
    assert report["planner"]["used"] == "heuristic"
    assert "--send-signed-in-pages" in report["planner"]["fallback_reason"]


@pytest.mark.asyncio
async def test_invalid_model_settings_fall_back_to_rules_instead_of_ending_the_hunt(server_url, tmp_path):
    bad = settings(tmp_path, reasoning_effort="ludicrous")
    report = await Hunt(f"{server_url}/demo/checkout.html?mode=buggy", planner="auto", rounds=1, settings=bad).run()
    assert report["planner"]["used"] == "heuristic"
    assert report["planner"]["fallback_reason"].startswith("Model settings rejected")
    assert report["counterexamples"], "the rules-only planner still finds the double submit"
