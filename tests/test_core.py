"""Fast unit tests: vocabulary, grounding, invariants, minimizer logic, demo variants."""
import pytest

from faultline.config import is_local_url
from faultline.invariants import evaluate, overall_status, signature
from faultline.minimize import attribution, minimize
from faultline.server import render_variant
from faultline.vocab import PlanError, describe_experiment, normalize_experiment, normalize_plan

INV = {
    "elements": [
        {"ref": "e1", "role": "button", "name": "Edit profile", "editable": False, "password": False},
        {"ref": "e2", "role": "textbox", "name": "Display name", "editable": True, "password": False},
        {"ref": "e3", "role": "textbox", "name": "Password", "editable": False, "password": True},
        {"ref": "e4", "role": "status", "name": "", "editable": False, "password": False},
    ],
    "endpoints": ["GET /api/profile"],
}


def step(action, ref="", value="", key="", ms=0):
    return {"action": action, "ref": ref, "value": value, "key": key, "ms": ms}


def exp(steps, perts=(), invs=()):
    return {"steps": list(steps), "perturbations": list(perts), "invariants": list(invs)}


def test_grounded_value_invariant_is_accepted():
    e = normalize_experiment(exp([step("click", "e1"), step("fill", "e2", "Ada")], invs=[
        {"kind": "value_equals", "ref": "e2", "value": "Ada"}]), INV)
    assert e["invariants"][0]["value"] == "Ada"


def test_ungrounded_value_invariant_is_rejected():
    with pytest.raises(PlanError, match="not grounded"):
        normalize_experiment(exp([step("click", "e1")], invs=[{"kind": "value_equals", "ref": "e2", "value": "Ada"}]), INV)


def test_password_fields_are_never_typed_into():
    with pytest.raises(PlanError, match="non-password"):
        normalize_experiment(exp([step("fill", "e3", "hunter2")], invs=[{"kind": "no_page_errors"}]), INV)


def test_unknown_refs_and_raw_selectors_are_rejected():
    with pytest.raises(PlanError, match="unknown element"):
        normalize_experiment(exp([step("click", "#edit")], invs=[{"kind": "no_page_errors"}]), INV)


def test_focus_invariant_requires_a_click_on_the_opener():
    with pytest.raises(PlanError, match="clicked"):
        normalize_experiment(exp([step("press", key="Escape")], invs=[{"kind": "focus_returns", "ref": "e1"}]), INV)


def test_perturbations_only_on_observed_endpoints_or_method_wildcards():
    ok = exp([step("click", "e1")], [{"kind": "delay", "endpoint": "GET /api/profile", "ms": 900, "nth": 1}],
             [{"kind": "no_page_errors"}])
    normalize_experiment(ok, INV)
    wildcard = exp([step("click", "e1")], [{"kind": "fail", "endpoint": "POST *", "status": 500, "nth": 1}],
                   [{"kind": "no_page_errors"}])
    normalize_experiment(wildcard, INV)
    with pytest.raises(PlanError, match="not observed"):
        normalize_experiment(exp([step("click", "e1")], [{"kind": "delay", "endpoint": "GET /admin", "ms": 900, "nth": 1}],
                                 [{"kind": "no_page_errors"}]), INV)
    with pytest.raises(PlanError):
        normalize_experiment(exp([step("click", "e1")], [{"kind": "delay", "endpoint": "* *", "ms": 900, "nth": 1}],
                                 [{"kind": "no_page_errors"}]), INV)


def test_normalize_plan_keeps_valid_and_explains_rejections():
    accepted, rejected = normalize_plan({"hypotheses": [
        {"id": "good", "claim": "c", "fault_class": "focus_loss",
         "steps": [step("click", "e1"), step("press", key="Escape")], "perturbations": [],
         "invariants": [{"kind": "focus_returns", "ref": "e1"}]},
        {"id": "bad", "claim": "invented", "fault_class": "nonsense",
         "steps": [step("click", "e9")], "perturbations": [], "invariants": [{"kind": "no_page_errors"}]},
    ]}, INV)
    assert [h["id"] for h in accepted] == ["good"]
    assert rejected[0]["id"] == "bad" and "unknown element" in rejected[0]["reason"]


def test_descriptions_are_readable():
    text = describe_experiment(exp([step("click", "e1"), step("fill", "e2", "Ada")],
                                   [{"kind": "delay", "endpoint": "GET /api/profile", "ms": 1500, "nth": 1}],
                                   [{"kind": "value_equals", "ref": "e2", "value": "Ada"}]), INV)
    assert text["steps"] == ['Click "Edit profile"', 'Enter "Ada" into "Display name"']
    assert text["perturbations"] == ["Hold the 1st GET /api/profile request for 1500 ms"]


def _probe(dialogs):
    return {"dialogs": dialogs, "active": None}


def test_focus_guard_makes_invariant_inapplicable_when_no_dialog_opened():
    e = exp([step("click", "e1"), step("press", key="Escape")], invs=[{"kind": "focus_returns", "ref": "e1"}])
    observed = {"dialogs": 0, "active": None, "values": {}, "texts": {}, "focus": {"e1": False}}
    no_dialog = evaluate(e, observed, [_probe(0), _probe(0), _probe(0)], [], [])
    assert no_dialog[0]["status"] == "inapplicable"
    opened = evaluate(e, observed, [_probe(0), _probe(1), _probe(0)], [], [])
    assert opened[0]["status"] == "fail" and overall_status(opened, None) == "failed"
    assert signature(opened) == ["focus_returns:e1"]


def test_max_requests_counts_matching_requests():
    e = exp([step("click", "e1")], invs=[{"kind": "max_requests", "endpoint": "POST *", "max": 1}])
    observed = {"dialogs": 0, "active": None, "values": {}, "texts": {}, "focus": {}}
    net = [{"method": "POST", "path": "/api/orders"}, {"method": "POST", "path": "/api/orders"},
           {"method": "GET", "path": "/api/profile"}]
    result = evaluate(e, observed, [_probe(0)], net, [])
    assert result[0]["status"] == "fail" and result[0]["actual"] == "2 request(s)"


@pytest.mark.asyncio
async def test_minimizer_never_removes_the_step_an_invariant_is_grounded_in():
    """Regression test for the v0 bug where every repro collapsed to 'open page, read state'."""
    original = exp([step("click", "e1"), step("fill", "e2", "Ada"), step("press", key="Escape"),
                    step("click", "e1"), step("wait", ms=600)],
                   [{"kind": "delay", "endpoint": "GET /api/profile", "ms": 1500, "nth": 1}],
                   [{"kind": "value_equals", "ref": "e2", "value": "Ada"}])
    original = normalize_experiment(original, INV)
    seen = []

    async def fake_run(candidate):
        seen.append(candidate)
        actions = [s["action"] for s in candidate["steps"]]
        breaks = "fill" in actions and actions.count("click") >= 1 and bool(candidate["perturbations"])
        return {"status": "failed" if breaks else "passed",
                "signature": ["value_equals:e2"] if breaks else []}

    reduced = await minimize(fake_run, original, "value_equals:e2", INV)
    steps = reduced["experiment"]["steps"]
    assert any(s["action"] == "fill" for s in steps), "the grounded fill must survive"
    assert len(steps) < len(original["steps"])
    assert reduced["experiment"]["perturbations"], "the delay is required and must be kept"
    assert attribution(reduced["experiment"]["perturbations"], reduced["controls"]).startswith("timing-dependent")


def test_demo_variants_ship_only_one_code_path():
    html = "a\n//<buggy>\nBUG\n//</buggy>\n//<fixed>\nFIX\n//</fixed>\nz\n"
    assert render_variant(html, "buggy") == "a\nBUG\nz\n"
    assert render_variant(html, "fixed") == "a\nFIX\nz\n"


@pytest.mark.parametrize("url,ok", [("http://localhost:3000/x", True), ("http://127.0.0.1:8000", True),
                                     ("http://app.test/", True), ("https://example.com", False),
                                     ("http://192.168.1.4", False), ("file:///etc/passwd", False)])
def test_only_local_targets_by_default(url, ok):
    assert is_local_url(url) is ok
