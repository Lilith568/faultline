"""Strict API mode must never turn a failed live demonstration into a replay or a rule run.

HTTP transports and browser execution are injected; these tests must never claim real-network evidence.
"""
import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

import faultline.hunt as orchestration
from faultline.config import Settings
from faultline.hunt import Hunt, live_api_evidence
from faultline.meta import MetaClient, MetaError
from faultline.reports import ci_issues


INVENTORY = {"title": "Local test page", "elements": [
    {"ref": "e1", "role": "button", "name": "Check", "visible": True, "editable": False, "password": False},
], "endpoints": [], "notes": []}
HYPOTHESIS = {"id": "check", "claim": "A click throws a page error", "fault_class": "other", "rationale": "",
              "steps": [{"action": "click", "ref": "e1", "value": "", "key": "", "ms": 0}],
              "perturbations": [], "invariants": [{"kind": "no_page_errors", "ref": "", "value": "",
                                                    "endpoint": "", "max": 0}]}


def settings(tmp_path, **updates):
    return replace(Settings("private-test-key", "https://api.meta.ai/v1", "muse-spark-1.3", "medium", False, tmp_path),
                   **updates)


@pytest.fixture
def browser_boundary(monkeypatch):
    """Run the actual planner/client/orchestrator while replacing only browser I/O."""
    class Browser:
        async def close(self):
            pass

    class Playwright:
        async def __aenter__(self):
            async def launch():
                return Browser()
            return SimpleNamespace(chromium=SimpleNamespace(launch=launch))

        async def __aexit__(self, *args):
            pass

    async def discover(*args, **kwargs):
        return copy.deepcopy(INVENTORY)

    async def execute(*args, **kwargs):
        return {"status": "passed", "signature": [], "invariants": [{"kind": "no_page_errors", "status": "pass"}],
                "network": [], "duration_ms": 1}

    def rules_forbidden(*args, **kwargs):
        raise AssertionError("Strict mode invoked the rule planner")

    monkeypatch.setattr(orchestration, "async_playwright", Playwright)
    monkeypatch.setattr(orchestration, "discover", discover)
    monkeypatch.setattr(orchestration, "run_experiment", execute)
    monkeypatch.setattr(orchestration, "heuristic_plan", rules_forbidden)


def meta_transport(*, failing_stage=None, empty_initial=False, empty_diagnosis=False):
    def handle(request):
        body = json.loads(request.content)
        user = body["messages"][1]["content"]
        payload = json.loads(user if isinstance(user, str) else user[0]["text"])
        stage = ("diagnosis" if body["response_format"]["json_schema"]["name"] == "faultline_diagnosis"
                 else "followup" if "previous_round" in payload else "plan")
        if stage == failing_stage:
            return httpx.Response(401, text="private-test-key and page source must not be logged")
        content = ({} if stage == "diagnosis" and empty_diagnosis else
                   {"hypotheses": [] if stage == "followup" or empty_initial else [copy.deepcopy(HYPOTHESIS)]})
        return httpx.Response(200, json={"model": body["model"], "usage": {"prompt_tokens": 12, "completion_tokens": 8},
                                         "choices": [{"message": {"content": json.dumps(content)}}]})
    return httpx.MockTransport(handle)


@pytest.mark.parametrize("updates,kwargs,match", [
    ({"api_key": None}, {}, "MODEL_API_KEY"),
    ({}, {"planner": "heuristic"}, "Meta planner"),
    ({}, {"planner": "recorded"}, "Meta planner"),
    ({}, {"recorded_plan": {}}, "recorded plan"),
    ({"model": "other-model"}, {}, "Only the documented Meta"),
    ({"base_url": "https://wrong-provider.example/v1"}, {}, "api.meta.ai"),
])
def test_strict_configuration_is_rejected_before_browser(tmp_path, updates, kwargs, match):
    with pytest.raises(ValueError, match=match):
        Hunt("http://localhost:8080", settings=settings(tmp_path, **updates), require_live=True, **kwargs)


def test_strict_signed_in_requires_explicit_consent(tmp_path):
    state = {"cookies": [{"name": "session", "value": "test-session", "domain": "localhost", "path": "/"}], "origins": []}
    with pytest.raises(ValueError, match="send-signed-in-pages"):
        Hunt("http://localhost:8080", settings=settings(tmp_path), require_live=True, storage_state=state)
    Hunt("http://localhost:8080", settings=settings(tmp_path), require_live=True,
         storage_state=state, share_signed_in_pages=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["plan", "followup"])
async def test_strict_failures_stop_and_persist_partial_evidence(tmp_path, browser_boundary, stage):
    hunt = Hunt("http://localhost:8080", settings=settings(tmp_path), require_live=True,
                meta_transport=meta_transport(failing_stage=stage))
    with pytest.raises(MetaError, match="HTTP 401"):
        await hunt.run()
    saved = json.loads((hunt.dir / "report.json").read_text())
    assert saved == hunt.report
    assert saved["status"] == "error" and saved["finished_at"] and saved["stats"]["meta_calls"] >= 1
    assert saved["planner"]["used"] != "heuristic"
    assert saved["live_api"]["status"] == "incomplete"
    assert saved["live_api"]["network_successes"] == 0
    assert saved["meta_calls"][-1]["http_status"] == 401
    assert "private-test-key" not in json.dumps(saved)
    assert "page source must not" not in json.dumps(saved)


@pytest.mark.asyncio
async def test_empty_initial_plan_never_falls_back_in_strict_mode(tmp_path, browser_boundary):
    hunt = Hunt("http://localhost:8080", settings=settings(tmp_path), require_live=True,
                meta_transport=meta_transport(empty_initial=True))
    with pytest.raises(MetaError, match="no valid experiments"):
        await hunt.run()
    assert hunt.report["status"] == "error" and hunt.report["rounds"] == []


@pytest.mark.asyncio
async def test_strict_injected_flow_and_valid_empty_followup_are_not_live_evidence(tmp_path, browser_boundary):
    report = await Hunt("http://localhost:8080", settings=settings(tmp_path), require_live=True,
                        meta_transport=meta_transport()).run()
    assert report["status"] == "complete" and report["planner"]["used"] == "meta"
    assert [call["purpose"] for call in report["meta_calls"]] == ["plan", "follow-up plan"]
    assert report["live_api"]["status"] == "incomplete" and report["live_api"]["network_successes"] == 0
    assert all(call["transport"] == "injected" for call in report["live_api"]["calls"])
    assert all(call["started_at"] and call["endpoint_host"] == "api.meta.ai" for call in report["live_api"]["calls"])
    assert "The required live Meta API evidence is incomplete" in ci_issues(report)


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["http_error", "empty"])
async def test_strict_diagnosis_failure_never_uses_template(tmp_path, browser_boundary, monkeypatch, response):
    async def fail(browser, url, experiment, inventory, **kwargs):
        return {"status": "failed", "signature": ["no_page_errors"], "duration_ms": 1, "network": [],
                "invariants": [{"kind": "no_page_errors", "status": "fail", "expected": "no errors", "actual": "error"}]}

    async def minimize(runner, experiment, *args):
        return {"experiment": experiment, "attempts": 0, "controls": []}

    def template_forbidden(*args, **kwargs):
        raise AssertionError("Strict mode used a template diagnosis")

    monkeypatch.setattr(orchestration, "run_experiment", fail)
    monkeypatch.setattr(orchestration, "minimize", minimize)
    monkeypatch.setattr(orchestration, "template_diagnosis", template_forbidden)
    hunt = Hunt("http://localhost:8080", settings=settings(tmp_path), require_live=True, rounds=1,
                meta_transport=meta_transport(failing_stage="diagnosis" if response == "http_error" else None,
                                              empty_diagnosis=response == "empty"))
    with pytest.raises(MetaError, match="HTTP 401" if response == "http_error" else "no substantive diagnosis"):
        await hunt.run()
    assert hunt.report["status"] == "error" and hunt.report["live_api"]["status"] == "incomplete"
    assert hunt.report["meta_calls"][-1]["purpose"] == "diagnosis"
    assert json.loads((hunt.dir / "report.json").read_text())["status"] == "error"


@pytest.mark.asyncio
async def test_missing_reported_model_is_unknown_not_invented(tmp_path):
    client = MetaClient(settings(tmp_path), transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        "choices": [{"message": {"content": '{"ok": true}'}}]})))
    try:
        await client.json_call(purpose="test", system="Return JSON", user="synthetic", schema_name="test",
                               schema={"type": "object"})
        assert client.calls[0]["reported_model"] is None
        assert client.calls[0]["transport"] == "injected"
    finally:
        await client.close()


def test_live_summary_requires_successful_matching_network_model_and_no_fallback():
    call = {"transport": "network", "success": True, "model": "muse-spark-1.3",
            "reported_model": "muse-spark-1.3-2026-10-20", "secret_field": "never project arbitrary fields"}
    report = {"status": "complete", "planner": {"used": "meta"}, "rounds": [{"source": "meta", "hypotheses": []}],
              "meta_calls": [call], "counterexamples": []}
    assert live_api_evidence(report, required=True)["status"] == "complete"
    assert "secret_field" not in live_api_evidence(report, required=True)["calls"][0]
    for updates in ({"transport": "injected"}, {"reported_model": None}, {"reported_model": "muse-wonder-1.0"},
                    {"success": False}):
        changed = {**report, "meta_calls": [{**call, **updates}]}
        assert live_api_evidence(changed, required=True)["status"] == "incomplete"
    for extra in ({**call, "reported_model": None}, {**call, "transport": "injected"}):
        mixed = {**report, "meta_calls": [call, extra]}
        assert live_api_evidence(mixed, required=True)["network_successes"] == 1
        assert live_api_evidence(mixed, required=True)["status"] == "incomplete"
    failed_retry = {**call, "success": False, "reported_model": None}
    assert live_api_evidence({**report, "meta_calls": [failed_retry, call]}, required=True)["status"] == "complete"
    for updates in ({"status": "error"}, {"planner": {"used": "meta", "fallback_reason": "error"}},
                    {"planner": {"used": "recorded"}}):
        assert live_api_evidence({**report, **updates}, required=True)["status"] == "incomplete"
    assert live_api_evidence(report, required=False)["status"] == "not_requested"


def test_cli_forwards_require_live(monkeypatch, capsys):
    from faultline.cli import main
    captured = {}
    class StubHunt:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            raise ValueError("Missing Meta key")
    monkeypatch.setattr(orchestration, "Hunt", StubHunt)
    with pytest.raises(SystemExit) as error:
        main(["hunt", "http://localhost:8080", "--require-live"])
    assert error.value.code == 2 and captured["require_live"] is True
    assert "Missing Meta key" in capsys.readouterr().err


@pytest.mark.asyncio
@pytest.mark.parametrize("reported", ["muse-spark-1.3-private-test-key", "muse-spark-1.3-" + "x" * 201,
                                    "muse-spark-1.3-2026\n10"])
async def test_untrusted_response_model_cannot_expose_credentials_or_control_characters(tmp_path, reported):
    client = MetaClient(settings(tmp_path), transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        "model": reported, "choices": [{"message": {"content": '{"ok": true}'}}]})))
    try:
        with pytest.raises(MetaError, match="unsafe model identifier") as error:
            await client.json_call(purpose="test", system="Return JSON", user="synthetic", schema_name="test",
                                   schema={"type": "object"})
        assert len(client.calls) == 1 and client.calls[0]["success"] is False
        assert client.calls[0]["reported_model"] is None
        assert "private-test-key" not in json.dumps(client.calls) + str(error.value)
        assert reported not in json.dumps(client.calls)
    finally:
        await client.close()
