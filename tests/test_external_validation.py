"""External compatibility reports must not confuse absent coverage with success."""
import importlib.util
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    "faultline_external_evaluation", Path(__file__).resolve().parents[1] / "scripts" / "evaluate_external.py"
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
coverage = _module.coverage


def test_empty_upstream_probe_has_no_verdict():
    result = coverage({"rounds": [], "inventory": {"elements": [{"ref": "e1"}], "endpoints": []}})
    assert result["controls_discovered"] == 1
    assert result["applicable_experiments"] == 0
    assert result["coverage_status"] == "no_applicable_experiments"
    assert "No verdict" in result["interpretation"]


def test_inapplicable_and_error_experiments_are_not_passes():
    result = coverage({"rounds": [{"hypotheses": [
        {"result": {"status": "inapplicable", "invariants": [{"status": "inapplicable"}]}},
        {"result": {"status": "error", "invariants": []}},
    ]}]})
    assert result["experiments_planned"] == 2
    assert result["applicable_experiments"] == 0
    assert result["experiment_statuses"] == {"inapplicable": 1, "error": 1}
    assert result["invariant_statuses"] == {"inapplicable": 1}


def test_unconfirmed_failures_are_separate_from_verified():
    result = coverage({"rounds": [{"hypotheses": [
        {"result": {"status": "failed", "invariants": [{"status": "fail"}]}},
    ]}], "unconfirmed": [{"title": "intermittent"}], "counterexamples": []})
    assert result["applicable_experiments"] == 1
    assert result["verified_counterexamples"] == 0
    assert result["unconfirmed_counterexamples"] == 1
