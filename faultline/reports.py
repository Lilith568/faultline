"""Conservative CI exit codes and JUnit reports for verified findings."""
from __future__ import annotations

import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

_XML_INVALID = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def _text(value) -> str:
    return _XML_INVALID.sub("", str(value or ""))


def verified_findings(report: dict) -> list[dict]:
    return [cx for cx in report.get("counterexamples", [])
            if cx.get("confirmation", {}).get("confirmed") is True
            and cx["confirmation"].get("runs", 0) >= 3
            and cx["confirmation"].get("failures") == cx["confirmation"].get("runs")]


def _hypotheses(report: dict):
    for rnd in report.get("rounds", []):
        for hyp in rnd.get("hypotheses", []):
            yield rnd.get("round", "?"), hyp


def ci_issues(report: dict) -> list[str]:
    """An inconclusive hunt must never become a green CI check."""
    issues = []
    rows = list(_hypotheses(report))
    if not report.get("finished_at"):
        issues.append("The hunt did not finish")
    if not any(h.get("result", {}).get("status") in ("passed", "failed")
               and any(i.get("status") in ("pass", "fail") for i in h["result"].get("invariants", []))
               for _, h in rows):
        issues.append("No applicable invariant was checked")
    if any(h.get("result", {}).get("status") == "error" for _, h in rows):
        issues.append("An experiment could not run")
    if report.get("unconfirmed"):
        issues.append("A candidate failure did not reproduce consistently")
    if len(verified_findings(report)) != len(report.get("counterexamples", [])):
        issues.append("A finding did not meet the three-run confirmation requirement")
    planner = report.get("planner", {})
    if planner.get("requested") == "meta":
        if any(str(w).startswith("Follow-up round skipped:") for w in report.get("warnings", [])):
            issues.append("A requested Meta follow-up round did not complete")
        if planner.get("used") != "meta" or planner.get("fallback_reason"):
            issues.append("The requested Meta planner was not used successfully")
        elif any(r.get("source") != "meta" for r in report.get("rounds", [])):
            issues.append("A requested Meta round fell back to another planner")
        elif any(cx.get("diagnosis", {}).get("source") != "meta" for cx in report.get("counterexamples", [])):
            issues.append("A requested Meta diagnosis fell back to a template")
    return issues


def ci_exit_code(report: dict) -> int:
    """1: verified bug(s); 2: incomplete/inconclusive; 0: completed checks held up."""
    if verified_findings(report):
        return 1
    return 2 if ci_issues(report) else 0


def _write(root: ET.Element, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cases = list(root.findall("testcase"))
    root.set("tests", str(len(cases)))
    for name in ("failure", "error", "skipped"):
        root.set("failures" if name == "failure" else "errors" if name == "error" else "skipped",
                 str(sum(c.find(name) is not None for c in cases)))
    fd, temporary = tempfile.mkstemp(prefix=".faultline-junit-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            ET.ElementTree(root).write(handle, encoding="utf-8", xml_declaration=True)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_junit(report: dict, path: str | Path) -> None:
    """Export verified bugs as failures; execution problems remain distinct errors."""
    suite = ET.Element("testsuite", name="Faultline", time=str(report.get("stats", {}).get("duration_s", 0)))
    for rnd, hyp in _hypotheses(report):
        result = hyp.get("result", {})
        case = ET.SubElement(suite, "testcase", classname=f"faultline.round{rnd}",
                             name=_text(hyp.get("claim") or hyp.get("id")),
                             time=str(result.get("duration_ms", 0) / 1000))
        status = result.get("status")
        if status == "error":
            ET.SubElement(case, "error", type="ExecutionError", message=_text(result.get("error") or "Experiment could not run"))
        elif status != "passed":
            message = "Candidate failure; see confirmed findings" if status == "failed" else "No applicable check"
            ET.SubElement(case, "skipped", message=message)
    for cx in verified_findings(report):
        case = ET.SubElement(suite, "testcase", classname="faultline.confirmed", name=_text(cx.get("title") or cx.get("id")))
        failure = ET.SubElement(case, "failure", type="VerifiedFailure", message=_text(cx.get("title")))
        evidence = cx.get("failure", {})
        failure.text = _text(f"Expected: {evidence.get('expected')}\nObserved: {evidence.get('actual')}\n"
                             f"Confirmed: {cx['confirmation']['failures']}/{cx['confirmation']['runs']}\n"
                             f"Test: {cx.get('spec_file', '')}")
    for issue in ci_issues(report):
        case = ET.SubElement(suite, "testcase", classname="faultline.completeness", name=issue)
        ET.SubElement(case, "error", type="IncompleteHunt", message=issue)
    _write(suite, path)


def write_error_junit(path: str | Path, message: str) -> None:
    suite = ET.Element("testsuite", name="Faultline", time="0")
    case = ET.SubElement(suite, "testcase", classname="faultline.infrastructure", name="Run hunt")
    ET.SubElement(case, "error", type="InfrastructureError", message=_text(message))
    _write(suite, path)
