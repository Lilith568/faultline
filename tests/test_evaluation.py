"""Preserved evaluation evidence, strict Meta provenance and honest aggregation."""
from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

import pytest
from faultline.config import Settings

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import evaluate as evaluation
import summarize_eval


def settings(tmp_path, key="private-test-key"):
    return Settings(api_key=key, base_url="https://api.meta.test/v1", model="muse-spark-1.3",
                    reasoning_effort="medium", allow_remote=False, artifacts=tmp_path / "unused")


def report(mode, source="meta"):
    cx = {"id": "cx1", "title": "Duplicate order", "signature": "max_requests:POST /demo-api/orders",
          "elements": {}, "experiment": {"steps": [{"action": "dblclick"}], "perturbations": []},
          "confirmation": {"confirmed": True, "runs": 3, "failures": 3}, "diagnosis": {"source": source}}
    return {"id": "fake-" + mode, "planner": {"used": source, "fallback_reason": None},
            "counterexamples": [cx] if mode == "buggy" else [], "unconfirmed": [],
            "rounds": [{"hypotheses": [{"result": {"status": "failed" if mode == "buggy" else "passed",
                "invariants": [{"status": "fail" if mode == "buggy" else "pass"}]}}], "source": source}], "meta_calls": [],
            "stats": {"experiments": 1, "browser_runs": 2, "meta_calls": 1,
                      "input_tokens": 10, "output_tokens": 2}}


class FakeHunt:
    def __init__(self, url, planner, settings, emit):
        self.mode = parse_qs(urlsplit(url).query)["mode"][0]
        self.emit = emit

    async def run(self):
        return report(self.mode)


@pytest.mark.asyncio
async def test_each_run_is_preserved_and_meta_run_is_complete(tmp_path):
    directories = []
    for _ in range(2):
        directory = evaluation.unique_directory(tmp_path, "meta")
        directories.append(directory)
        result = await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout"],
                                          settings=settings(tmp_path), run_dir=directory, hunt_factory=FakeHunt)
        assert result["status"] == "completed"
        assert result["coverage"]["meta_complete_targets"] == 2
        assert result["dev_apps"]["found"] == 1
        assert result["dev_apps"]["false_positives_on_fixed_builds"] == 0
        assert json.loads((directory / "result.json").read_text())["status"] == "completed"
    assert directories[0] != directories[1]
    assert all((p / "result.json").exists() for p in directories)
    assert not (tmp_path / "results-meta.json").exists()


@pytest.mark.asyncio
async def test_fallback_is_visible_and_not_a_complete_meta_evaluation(tmp_path):
    class Fallback(FakeHunt):
        async def run(self):
            r = report(self.mode, "heuristic")
            r["planner"]["fallback_reason"] = "HTTP 401 private-test-key"
            return r
    directory = evaluation.unique_directory(tmp_path, "meta")
    result = await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout"],
                                      settings=settings(tmp_path), run_dir=directory, hunt_factory=Fallback)
    assert result["status"] == "degraded"
    assert result["coverage"]["meta_complete_targets"] == 0
    text = (directory / "result.md").read_text()
    assert "heuristic" in text and "HTTP 401" in text and "degraded" in text
    assert "private-test-key" not in (directory / "result.json").read_text()
    assert "private-test-key" not in text


@pytest.mark.asyncio
async def test_failed_target_keeps_prior_evidence_and_remaining_targets(tmp_path):
    class Failure(FakeHunt):
        async def run(self):
            if self.mode == "fixed":
                raise RuntimeError("browser failed")
            return report(self.mode)
    directory = evaluation.unique_directory(tmp_path, "meta")
    result = await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout", "search"],
                                      settings=settings(tmp_path), run_dir=directory, hunt_factory=Failure)
    assert result["status"] == "incomplete"
    assert result["coverage"] == {"planned": 4, "completed": 2, "errors": 2,
                                  "not_completed": 2, "meta_complete_targets": 2,
                                  "targets_with_applicable_checks": 2, "execution_complete_targets": 2}
    assert len(result["rows"]) == 4
    text = (directory / "result.md").read_text()
    assert "not evaluated" in text and "browser failed" in text
    assert result["dev_apps"]["fixed_builds_completed"] == 0
    assert result["dev_apps"]["fixed_builds_planned"] == 2


@pytest.mark.asyncio
async def test_interruption_leaves_a_readable_checkpoint(tmp_path):
    class Interrupted(FakeHunt):
        async def run(self):
            if self.mode == "fixed":
                raise asyncio.CancelledError()
            return report(self.mode)
    directory = evaluation.unique_directory(tmp_path, "meta")
    with pytest.raises(asyncio.CancelledError):
        await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout"],
                                  settings=settings(tmp_path), run_dir=directory, hunt_factory=Interrupted)
    saved = json.loads((directory / "result.json").read_text())
    assert saved["status"] == "interrupted"
    assert saved["rows"][0]["found"] == ["checkout-double"]
    assert saved["coverage"]["completed"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("warning", ["Follow-up round skipped: unavailable", "Diagnosis fell back to a template"])
async def test_degraded_later_model_stages_are_not_silently_counted(tmp_path, warning):
    class Warns(FakeHunt):
        async def run(self):
            self.emit("warning", warning)
            return report(self.mode)
    directory = evaluation.unique_directory(tmp_path, "meta")
    result = await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout"],
                                      settings=settings(tmp_path), run_dir=directory, hunt_factory=Warns)
    assert result["status"] == "degraded"
    assert warning in (directory / "result.md").read_text()


def test_missing_key_is_saved_and_returns_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "get_settings", lambda: settings(tmp_path, None))
    monkeypatch.setattr(sys, "argv", ["evaluate.py", "--planner", "meta", "--output-dir", str(tmp_path)])
    assert evaluation.main() == 2
    results = list(tmp_path.glob("*/result.json"))
    assert len(results) == 1
    saved = json.loads(results[0].read_text())
    assert saved["status"] == "error" and "MODEL_API_KEY" in saved["errors"][0]
    assert saved["coverage"]["completed"] == 0


def test_atomic_failure_preserves_previous_checkpoint(tmp_path, monkeypatch):
    path = tmp_path / "result.json"
    evaluation.atomic_json(path, {"old": True})
    def fails(*args):
        raise OSError("disk replacement failed")
    monkeypatch.setattr(evaluation.os, "replace", fails)
    with pytest.raises(OSError):
        evaluation.atomic_json(path, {"new": True})
    assert json.loads(path.read_text()) == {"old": True}
    assert not list(tmp_path.glob("*.tmp-*"))


def test_concurrent_runs_never_reuse_a_directory(tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda _: evaluation.unique_directory(tmp_path, "meta"), range(12)))
    assert len(set(paths)) == 12


def test_subset_validation_and_configuration_redaction(tmp_path):
    assert evaluation.parse_apps("checkout, search") == ["checkout", "search"]
    for value in ("", "checkout,checkout", "unknown"):
        with pytest.raises(argparse.ArgumentTypeError):
            evaluation.parse_apps(value)
    value = evaluation.redact({"input_tokens": 4, "api_key": "private-test-key",
                              "error": "Bearer abc https://name:pass@localhost:9000/v1?key=secret#fragment"},
                             "private-test-key")
    assert value["input_tokens"] == 4
    assert "private-test-key" not in json.dumps(value)
    assert "name:pass" not in value["error"] and "?key=" not in value["error"]
    assert "Bearer [redacted]" in value["error"]
    meta = evaluation.evidence_metadata(settings(tmp_path), ["checkout"], "meta")
    assert "faultline/planners.py" in meta["source_sha256"]
    assert len(meta["comparison_fingerprint"]) == 64
    assert "private-test-key" not in json.dumps(meta)


@pytest.mark.asyncio
async def test_summary_keeps_all_attempts_and_splits_changed_configuration(tmp_path):
    for source in ("meta", "heuristic"):
        class Source(FakeHunt):
            async def run(self):
                r = report(self.mode, source)
                if source == "heuristic":
                    r["planner"]["fallback_reason"] = "Meta unavailable"
                return r
        directory = evaluation.unique_directory(tmp_path, "meta")
        await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout"],
                                  settings=settings(tmp_path), run_dir=directory, hunt_factory=Source)
    summary = summarize_eval.summarize(tmp_path)
    assert summary["attempts_counted"] == 2
    group = summary["groups"][0]
    assert group["status_counts"] == {"completed": 1, "degraded": 1}
    assert group["metrics"]["complete_evaluations"] == 1
    assert group["bugs"]["checkout-double"]["found_in_completed_targets"] == 2
    assert group["bugs"]["checkout-double"]["found_in_complete_evaluations"] == 1
    directory = evaluation.unique_directory(tmp_path, "meta")
    await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["search"],
                              settings=settings(tmp_path), run_dir=directory, hunt_factory=FakeHunt)
    assert len(summarize_eval.summarize(tmp_path)["groups"]) == 2
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "result.json").write_text("not JSON")
    assert len(summarize_eval.summarize(tmp_path)["input_errors"]) == 1


def test_model_options_change_comparison_fingerprint(tmp_path):
    from dataclasses import replace
    base = settings(tmp_path)
    fingerprints = {evaluation.evidence_metadata(s, ["checkout"], "meta")["comparison_fingerprint"] for s in (
        base, replace(base, backend="open_weights"), replace(base, supports_vision=False),
        replace(base, json_mode="json_object"))}
    assert len(fingerprints) == 4


def test_malformed_v2_evidence_is_reported_without_crashing(tmp_path):
    directory = evaluation.unique_directory(tmp_path, "meta")
    result = evaluation.new_result("meta", ["checkout"], settings(tmp_path), directory)
    evaluation.checkpoint(directory, result)
    result["rows"] = "corrupted"
    evaluation.atomic_json(directory / "result.json", result)
    summary = summarize_eval.summarize(tmp_path)
    assert summary["attempts_counted"] == 0
    assert len(summary["input_errors"]) == 1
    assert "rows must list every planned target" in summary["input_errors"][0]["error"]


@pytest.mark.parametrize("status", ["degraded", "incomplete"])
def test_non_complete_meta_exit_code_is_nonzero(tmp_path, monkeypatch, status):
    from unittest.mock import Mock
    monkeypatch.setattr(evaluation, "get_settings", lambda: settings(tmp_path))
    metadata = evaluation.evidence_metadata(settings(tmp_path), list(evaluation.GROUND_TRUTH), "meta")
    monkeypatch.setattr(evaluation, "evidence_metadata", lambda *args: metadata)
    monkeypatch.setattr(evaluation.subprocess, "Popen", lambda *args, **kwargs: Mock())
    monkeypatch.setattr(evaluation, "_wait", lambda url: None)
    async def finished(base, planner, apps, *, settings, run_dir, result):
        result["status"] = status
        return result
    monkeypatch.setattr(evaluation, "run_eval", finished)
    monkeypatch.setattr(sys, "argv", ["evaluate.py", "--planner", "meta", "--output-dir", str(tmp_path)])
    assert evaluation.main() == 2
    assert json.loads(next(tmp_path.glob("*/result.json")).read_text())["status"] == status


@pytest.mark.asyncio
async def test_experiment_error_degrades_meta_and_preserves_confirmed_findings(tmp_path):
    class PartialError(FakeHunt):
        async def run(self):
            r = report(self.mode)
            r["rounds"][0]["hypotheses"].append({"result": {"status": "error", "invariants": []}})
            return r
    directory = evaluation.unique_directory(tmp_path, "meta")
    result = await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout"],
                                      settings=settings(tmp_path), run_dir=directory, hunt_factory=PartialError)
    assert result["status"] == "degraded"
    row = result["rows"][0]
    assert row["found"] == ["checkout-double"]
    assert row["experiment_outcomes"] == {"failed": 1, "error": 1}
    assert row["applicable_invariants"] == 1
    assert not row["meta_complete"] and not row["execution_complete"]
    assert result["dev_apps"]["expected"] == result["dev_apps"]["planned_expected"] == 1
    assert result["coverage"]["completed"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["inapplicable", "empty", "no_invariants"])
async def test_no_applicable_checks_cannot_be_a_complete_meta_evaluation(tmp_path, kind):
    class NoCoverage(FakeHunt):
        async def run(self):
            r = report(self.mode)
            r["counterexamples"] = []
            hypotheses = [] if kind == "empty" else [{"result": {
                "status": "inapplicable" if kind == "inapplicable" else "passed",
                "invariants": [{"status": "inapplicable"}] if kind == "inapplicable" else []}}]
            r["rounds"][0]["hypotheses"] = hypotheses
            return r
    directory = evaluation.unique_directory(tmp_path, "meta")
    result = await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout"],
                                      settings=settings(tmp_path), run_dir=directory, hunt_factory=NoCoverage)
    assert result["status"] == "degraded"
    assert result["coverage"]["targets_with_applicable_checks"] == 0
    assert result["coverage"]["meta_complete_targets"] == 0
    assert result["dev_apps"]["expected"] == 1
    assert result["dev_apps"]["fixed_builds_completed"] == 1
    assert result["dev_apps"]["fixed_builds_with_coverage"] == 0
    assert "No applicable invariant coverage" in (directory / "result.md").read_text()


@pytest.mark.asyncio
async def test_runtime_change_degrades_run_and_excludes_comparable_score(tmp_path, monkeypatch):
    calls = []
    def changes():
        calls.append(True)
        return {"faultline/hunt.py": "before" if len(calls) == 1 else "after"}
    monkeypatch.setattr(evaluation, "source_hashes", changes)
    directory = evaluation.unique_directory(tmp_path, "meta")
    result = await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout"],
                                      settings=settings(tmp_path), run_dir=directory, hunt_factory=FakeHunt)
    assert result["status"] == "degraded"
    assert result["source_unchanged_during_run"] is False
    assert result["source_changes_during_run"] == ["faultline/hunt.py"]
    assert result["rows"][0]["found"] == ["checkout-double"]
    group = summarize_eval.summarize(tmp_path)["groups"][0]
    assert group["metrics"]["complete_evaluations"] == 0
    assert group["source_stability_counts"] == {"changed_or_unverifiable": 1}


@pytest.mark.asyncio
async def test_old_manifest_without_final_hash_is_visible_but_not_comparable(tmp_path):
    directory = evaluation.unique_directory(tmp_path, "meta")
    result = await evaluation.run_eval("http://127.0.0.1:8000", "meta", ["checkout"],
                                      settings=settings(tmp_path), run_dir=directory, hunt_factory=FakeHunt)
    assert result["source_unchanged_during_run"] is True
    result.pop("source_unchanged_during_run")
    evaluation.checkpoint(directory, result)
    group = summarize_eval.summarize(tmp_path)["groups"][0]
    assert group["status_counts"] == {"completed": 1}
    assert group["source_stability_counts"] == {"not_recorded": 1}
    assert group["metrics"]["complete_evaluations"] == 0
