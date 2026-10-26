"""CI must distinguish verified failures from incomplete work and protect auth state."""
import copy
import json
import threading
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.async_api import async_playwright

from faultline.auth import MAX_STATE_BYTES, canonical_origin, load_storage_state
from faultline.discover import discover
from faultline.executor import run_experiment
from faultline.reports import ci_exit_code, write_junit


def completed_report():
    return {"finished_at": "2026-10-27T00:00:00Z", "stats": {"duration_s": 1.2},
            "planner": {"requested": "heuristic", "used": "heuristic", "fallback_reason": None},
            "rounds": [{"round": 1, "source": "heuristic", "hypotheses": [
                {"id": "h1", "claim": "Input survives", "result": {"status": "passed", "duration_ms": 12,
                 "invariants": [{"kind": "value_equals", "status": "pass"}]}}]}],
            "counterexamples": [], "unconfirmed": []}


def test_ci_never_passes_inapplicable_error_or_fallback_runs():
    report = completed_report()
    assert ci_exit_code(report) == 0
    for status in ("inapplicable", "error"):
        other = copy.deepcopy(report)
        other["rounds"][0]["hypotheses"][0]["result"] = {"status": status, "invariants": []}
        assert ci_exit_code(other) == 2
    no_tests = copy.deepcopy(report)
    no_tests["rounds"] = []
    assert ci_exit_code(no_tests) == 2
    report["planner"] = {"requested": "meta", "used": "heuristic", "fallback_reason": "Missing key"}
    assert ci_exit_code(report) == 2
    report["planner"] = {"requested": "meta", "used": "meta"}
    report["rounds"][0]["source"] = "meta"
    report["warnings"] = ["Follow-up round skipped: MetaError: HTTP 503"]
    assert ci_exit_code(report) == 2
    report["warnings"] = []
    assert ci_exit_code(report) == 0
    report["planner"] = {"requested": "heuristic", "used": "heuristic"}
    report["unconfirmed"] = [{"title": "Intermittent"}]
    assert ci_exit_code(report) == 2


def test_junit_only_marks_confirmed_findings_as_failures(tmp_path):
    report = completed_report()
    report["rounds"][0]["hypotheses"].extend([
        {"id": "candidate", "claim": "Candidate < &", "result": {"status": "failed", "invariants": [{"status": "fail"}]}},
        {"id": "broken", "claim": "Navigation", "result": {"status": "error", "error": "No server\x01<"}},
    ])
    report["counterexamples"] = [{"id": "cx1", "title": "Confirmed < &", "confirmation": {
        "confirmed": True, "runs": 3, "failures": 3}, "failure": {"expected": "saved", "actual": "lost"}}]
    assert ci_exit_code(report) == 1
    path = tmp_path / "nested" / "junit.xml"
    write_junit(report, path)
    root = ET.parse(path).getroot()
    assert root.attrib["failures"] == "1"
    assert int(root.attrib["errors"]) >= 1
    assert root.find(".//failure").attrib["message"] == "Confirmed < &"
    assert root.find(".//testcase[@name='Candidate < &']/skipped") is not None
    report["counterexamples"][0]["confirmation"]["runs"] = 1
    report["counterexamples"][0]["confirmation"]["failures"] = 1
    assert ci_exit_code(report) == 2


def test_storage_state_is_bounded_and_scoped_without_echoing_secrets(tmp_path):
    target = "http://localhost:8000/settings"
    secret = "never-echo-this-session"
    state = {"cookies": [
        {"name": "session", "value": secret, "domain": ".localhost", "path": "/", "expires": -1},
        {"name": "other", "value": "foreign", "domain": "other.test", "path": "/"},
    ], "origins": [
        {"origin": "http://localhost:8000", "localStorage": [{"name": "token", "value": secret}]},
        {"origin": "http://localhost:9000", "localStorage": [{"name": "token", "value": "foreign"}]},
    ]}
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state))
    scoped = load_storage_state(path, target)
    assert scoped["cookies"] == [{"name": "session", "value": secret, "domain": "localhost", "path": "/",
                                  "expires": -1, "httpOnly": False, "secure": False, "sameSite": "Lax"}]
    assert scoped["origins"] == [state["origins"][0]]
    assert canonical_origin("HTTP://LOCALHOST:80/path") == "http://localhost"
    assert load_storage_state(None, target) is None
    path.write_text("{" + secret)
    with pytest.raises(ValueError) as error:
        load_storage_state(path, target)
    assert secret not in str(error.value)
    path.write_bytes(b" " * (MAX_STATE_BYTES + 1))
    with pytest.raises(ValueError, match="size limit"):
        load_storage_state(path, target)
    with pytest.raises(ValueError, match="no cookies"):
        load_storage_state({"cookies": [], "origins": []}, target)


def test_cli_writes_junit_on_start_failure(tmp_path, monkeypatch):
    from faultline.cli import main
    import faultline.hunt

    class BrokenHunt:
        def __init__(self, *args, **kwargs):
            raise ValueError("Target refused")

    monkeypatch.setattr(faultline.hunt, "Hunt", BrokenHunt)
    report = tmp_path / "junit.xml"
    with pytest.raises(SystemExit) as error:
        main(["hunt", "http://localhost:8000", "--ci", "--junit", str(report)])
    assert error.value.code == 2
    assert ET.parse(report).getroot().attrib["errors"] == "1"


@pytest.fixture
def authenticated_target():
    paths = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/redirect-destination")
                self.end_headers()
                return
            if "session=test-session" in self.headers.get("Cookie", ""):
                body = b'''<!doctype html><title>Private editor</title>
                <input aria-label="Draft" data-testid="draft"><button data-testid="switch"
                onclick="document.querySelector('input').type='password'">Protect field</button>
                <script>if(localStorage.getItem('token')!=='test-storage')document.body.innerHTML='Sign in';</script>'''
            else:
                body = b"<!doctype html><title>Sign in</title><p>Sign in first</p>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield {"url": f"http://127.0.0.1:{server.server_port}", "paths": paths}
    server.shutdown()
    worker.join(timeout=2)
    server.server_close()


@pytest.mark.asyncio
async def test_saved_state_reaches_discovery_and_fresh_experiments_without_trace(authenticated_target, tmp_path):
    url = authenticated_target["url"]
    state = load_storage_state({"cookies": [{"name": "session", "value": "test-session", "domain": "127.0.0.1",
                                             "path": "/", "expires": -1}],
                                "origins": [{"origin": url, "localStorage": [{"name": "token", "value": "test-storage"}]}]}, url)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            inventory = await discover(browser, url, storage_state=state, max_openers=0, max_inputs=0)
            refs = {e["testid"]: e["ref"] for e in inventory["elements"]}
            assert "draft" in refs
            exp = {"steps": [{"action": "fill", "ref": refs["draft"], "value": "Synthetic draft"}],
                   "perturbations": [], "invariants": [{"kind": "value_equals", "ref": refs["draft"], "value": "Synthetic draft"}]}
            trace = tmp_path / "authenticated-trace.zip"
            result = await run_experiment(browser, url, exp, inventory, storage_state=state, trace=trace)
            assert result["status"] == "passed"
            assert result["trace"] is None and not trace.exists()
            assert "test-session" not in json.dumps(result)
            assert "test-storage" not in json.dumps(result)
            protected = copy.deepcopy(exp)
            protected["steps"].insert(0, {"action": "click", "ref": refs["switch"]})
            result = await run_experiment(browser, url, protected, inventory, storage_state=state)
            assert result["status"] == "error"
            assert "Refusing to type into a password field" in result["error"]
            with pytest.raises(Exception, match="net::ERR_"):
                await discover(browser, url + "/redirect", storage_state=state, max_openers=0, max_inputs=0)
            assert "/redirect" in authenticated_target["paths"]
            assert "/redirect-destination" not in authenticated_target["paths"]
        finally:
            await browser.close()
