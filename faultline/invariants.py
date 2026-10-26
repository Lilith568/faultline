"""Deterministic invariant checks. The model never judges its own experiments."""
from __future__ import annotations

from .vocab import endpoint_matches

PASS, FAIL, NA = "pass", "fail", "inapplicable"


def _focus_guard(exp: dict, probes: list[dict], final_dialogs: int, ref: str) -> bool:
    """focus_returns only applies if clicking `ref` opened a dialog that is closed at the end."""
    for index, step in enumerate(exp["steps"]):
        if step["action"] in ("click", "dblclick") and step.get("ref") == ref:
            if index + 1 < len(probes):
                opened = probes[index + 1]["dialogs"] > probes[index]["dialogs"]
                if opened and final_dialogs < probes[index + 1]["dialogs"]:
                    return True
    return False


def _describe_active(active: dict | None) -> str:
    if not active:
        return "nothing (focus fell back to the page body)"
    label = active.get("name") or active.get("testid") or active.get("id") or active.get("tag")
    return f'{active.get("tag", "element")} "{label}"'


def evaluate(exp: dict, observed: dict, probes: list[dict], network: list[dict],
             page_errors: list[str]) -> list[dict]:
    results = []
    for inv in exp["invariants"]:
        kind = inv["kind"]
        result = {"kind": kind, "ref": inv.get("ref"), "endpoint": inv.get("endpoint"),
                  "expected": None, "actual": None, "status": NA, "note": ""}
        if kind == "value_equals":
            actual = observed["values"].get(inv["ref"])
            result["expected"] = inv["value"]
            if actual is None:
                result["note"] = "field is not present at the end of the run"
            else:
                result["actual"] = actual
                result["status"] = PASS if actual == inv["value"] else FAIL
        elif kind == "text_contains":
            actual = observed["texts"].get(inv["ref"])
            result["expected"] = f'contains "{inv["value"]}"'
            if actual is None:
                result["note"] = "element is not present at the end of the run"
            else:
                result["actual"] = actual[:200]
                result["status"] = PASS if inv["value"] in actual else FAIL
        elif kind == "focus_returns":
            result["expected"] = "focus on the control that opened the dialog"
            if not _focus_guard(exp, probes, observed["dialogs"], inv["ref"]):
                result["note"] = "no dialog opened by this control was closed during the run"
            else:
                focused = observed["focus"].get(inv["ref"], False)
                result["actual"] = "focus restored" if focused else _describe_active(observed.get("active"))
                result["status"] = PASS if focused else FAIL
        elif kind == "max_requests":
            count = sum(1 for r in network if endpoint_matches(inv["endpoint"], r["method"], r["path"]))
            result["expected"] = f"at most {inv['max']}"
            result["actual"] = f"{count} request(s)"
            result["status"] = PASS if count <= inv["max"] else FAIL
        elif kind == "no_page_errors":
            result["expected"] = "no uncaught errors"
            result["actual"] = page_errors[0][:200] if page_errors else "none"
            result["status"] = FAIL if page_errors else PASS
        results.append(result)
    return results


def signature(results: list[dict]) -> list[str]:
    return sorted(f"{r['kind']}:{r.get('ref') or r.get('endpoint') or ''}"
                  for r in results if r["status"] == FAIL)


def overall_status(results: list[dict], error: str | None) -> str:
    if error:
        return "error"
    statuses = {r["status"] for r in results}
    if FAIL in statuses:
        return "failed"
    if PASS in statuses:
        return "passed"
    return "inapplicable"
