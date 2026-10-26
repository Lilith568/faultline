"""End-to-end tests in a real browser against the bundled demo apps.

The Meta path is exercised with a fake OpenAI-compatible endpoint (httpx.MockTransport)
so the full pipeline (plan -> validate -> run -> follow-up -> minimize -> diagnose -> export)
runs in CI without a key. Real Muse runs are recorded separately (see docs/EVALUATION.md).
"""
import json

import httpx
import pytest

from faultline.config import Settings
from faultline.hunt import Hunt, replay


def settings(tmp_path, key=None):
    return Settings(api_key=key, base_url="https://api.meta.test/v1", model="muse-spark-1.3",
                    reasoning_effort="medium", allow_remote=False, artifacts=tmp_path)


@pytest.mark.asyncio
async def test_heuristic_hunt_finds_double_submit_and_fixed_build_is_clean(server_url, tmp_path):
    report = await Hunt(f"{server_url}/demo/checkout.html?mode=buggy", planner="heuristic",
                        settings=settings(tmp_path)).run()
    assert report["planner"]["used"] == "heuristic"
    signatures = [cx["signature"] for cx in report["counterexamples"] if cx["confirmation"]["confirmed"]]
    assert "max_requests:POST *" in signatures
    cx = report["counterexamples"][0]
    assert cx["spec_file"].endswith(".spec.ts")

    fixed = await Hunt(f"{server_url}/demo/checkout.html?mode=fixed", planner="heuristic",
                       settings=settings(tmp_path)).run()
    assert fixed["counterexamples"] == []

    repro = json.loads(open(cx["repro_file"], encoding="utf-8").read())
    assert (await replay(repro, f"{server_url}/demo/checkout.html?mode=fixed",
                         settings(tmp_path)))["status"] == "passed"
    assert (await replay(repro, f"{server_url}/demo/checkout.html?mode=buggy",
                         settings(tmp_path)))["status"] == "failed"


def fake_muse(calls):
    """A stand-in for the Meta Model API that answers like Muse would (structured JSON)."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        schema = body["response_format"]["json_schema"]["name"]
        user = body["messages"][1]["content"]
        user = json.loads(user if isinstance(user, str) else user[0]["text"])
        if schema == "faultline_diagnosis":
            content = {"title": "Draft lost on tab switch", "root_cause": "showWrite() re-creates the textarea",
                       "user_impact": "Writers lose their notes", "fix": "Keep notes in state and restore them",
                       "code_reference": "showWrite()", "confidence": "high"}
        else:
            refs = {e.get("testid"): e["ref"] for e in user["page"]["elements"]}
            follow_up = "previous_round" in user
            hyps = [] if follow_up else [
                {"id": "tab-draft", "claim": "Switching to Preview and back discards the draft",
                 "fault_class": "draft_loss", "rationale": "tabs re-mount the editor",
                 "steps": [{"action": "fill", "ref": refs["notes-input"], "value": "Fixed login bug", "key": "", "ms": 0},
                           {"action": "click", "ref": refs["tab-preview"], "value": "", "key": "", "ms": 0},
                           {"action": "click", "ref": refs["tab-write"], "value": "", "key": "", "ms": 0}],
                 "perturbations": [],
                 "invariants": [{"kind": "value_equals", "ref": refs["notes-input"], "value": "Fixed login bug",
                                 "endpoint": "", "max": 0}]},
                {"id": "invented", "claim": "uses an element that does not exist", "fault_class": "other",
                 "rationale": "", "steps": [{"action": "click", "ref": "e99", "value": "", "key": "", "ms": 0}],
                 "perturbations": [], "invariants": [{"kind": "no_page_errors", "ref": "", "value": "",
                                                      "endpoint": "", "max": 0}]},
            ]
            content = {"hypotheses": hyps}
        return httpx.Response(200, json={"model": body["model"], "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
                                         "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}}]})
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_meta_path_end_to_end_with_fake_endpoint(server_url, tmp_path):
    calls = []
    report = await Hunt(f"{server_url}/demo/composer.html?mode=buggy", planner="meta",
                        settings=settings(tmp_path, key="test-key"), meta_transport=fake_muse(calls)).run()
    assert report["planner"]["used"] == "meta"
    assert [r["id"] for r in report["rounds"][0]["rejected"]] == ["invented"], "validator must reject invented refs"
    cx = report["counterexamples"][0]
    assert cx["fault_class"] == "draft_loss" and cx["confirmation"]["confirmed"]
    assert cx["diagnosis"]["source"] == "meta" and cx["diagnosis"]["code_reference"] == "showWrite()"
    request = calls[0]
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["model"] == "muse-spark-1.3" and request["reasoning_effort"] == "medium"
    assert report["stats"]["meta_calls"] == len(calls) == 3  # plan, follow-up, diagnosis


@pytest.mark.asyncio
async def test_meta_errors_fall_back_to_heuristic(server_url, tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={"error": "bad key"}))
    report = await Hunt(f"{server_url}/demo/search.html?mode=buggy", planner="meta",
                        settings=settings(tmp_path, key="wrong"), meta_transport=transport).run()
    assert report["planner"]["used"] == "heuristic"
    assert "HTTP 401" in report["planner"]["fallback_reason"]
    assert report["counterexamples"] and report["counterexamples"][0]["fault_class"] == "out_of_order_response"


@pytest.mark.asyncio
async def test_remote_targets_are_refused(tmp_path):
    with pytest.raises(ValueError, match="local"):
        Hunt("https://example.com/", settings=settings(tmp_path))
