"""Experiment vocabulary, validation and human-readable descriptions.

Every plan - whether it comes from the Meta model or from the heuristic
planner - passes through ``normalize_plan``.  The validator is the safety
boundary: the model can only reference elements that discovery found, can only
type short synthetic strings into non-password fields, can only perturb
same-origin API calls that were observed (or method wildcards) and can only
assert invariants that are *grounded* in the experiment itself.
"""
from __future__ import annotations

import copy
import re
from typing import Any

ACTIONS = ("click", "dblclick", "fill", "type", "press", "wait", "reload")
KEYS = ("Escape", "Enter", "Tab", "Shift+Tab", "ArrowDown", "ArrowUp")
PERTURBATIONS = ("delay", "fail")
INVARIANTS = ("value_equals", "text_contains", "focus_returns", "max_requests", "no_page_errors")
FAULT_CLASSES = (
    "stale_response_overwrite",
    "out_of_order_response",
    "double_submit",
    "focus_loss",
    "draft_loss",
    "data_loss_on_error",
    "crash",
    "other",
)
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "*")

MAX_STEPS = 14
MAX_WAIT_TOTAL_MS = 15000
MAX_VALUE_LEN = 80
MAX_HYPOTHESES = 6

_PRINTABLE = re.compile(r"^[^\x00-\x1f\x7f]+$")


class PlanError(ValueError):
    """Raised when an experiment violates the vocabulary or grounding rules."""


# --------------------------------------------------------------------------- endpoints

def parse_endpoint(text: str) -> tuple[str, str]:
    parts = str(text or "").strip().split()
    if len(parts) != 2:
        raise PlanError(f"endpoint must look like 'METHOD /path', got {text!r}")
    method, path = parts[0].upper(), parts[1]
    if method not in METHODS:
        raise PlanError(f"unsupported method in endpoint {text!r}")
    if path != "*" and not path.startswith("/"):
        raise PlanError(f"endpoint path must start with '/' or be '*': {text!r}")
    return method, path


def endpoint_matches(endpoint: str, method: str, path: str) -> bool:
    want_method, want_path = parse_endpoint(endpoint)
    if want_method != "*" and want_method != method.upper():
        return False
    return want_path == "*" or want_path == path


def _endpoint_allowed(endpoint: str, observed: list[str]) -> bool:
    method, path = parse_endpoint(endpoint)
    if path == "*":
        return True  # method wildcard such as "POST *" is always allowed (same-origin only)
    return any(endpoint_matches(endpoint, *parse_endpoint(o)) for o in observed)


# --------------------------------------------------------------------------- grounding

def cumulative_values(steps: list[dict]) -> dict[str, str]:
    """Final text the experiment itself put into each field."""
    values: dict[str, str] = {}
    for step in steps:
        action = step["action"]
        if action == "fill":
            values[step["ref"]] = step["value"]
        elif action == "type":
            values[step["ref"]] = values.get(step["ref"], "") + step["value"]
        elif action == "reload":
            values = {}
    return values


def clicked_refs(steps: list[dict]) -> set[str]:
    return {s["ref"] for s in steps if s["action"] in ("click", "dblclick")}


# --------------------------------------------------------------------------- normalisation

def _clean_value(value: Any) -> str:
    value = str(value or "")
    if not value or len(value) > MAX_VALUE_LEN or not _PRINTABLE.match(value):
        raise PlanError("typed values must be 1-80 printable characters")
    return value


def _int(value: Any, lo: int, hi: int, name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise PlanError(f"{name} must be an integer") from exc
    if not lo <= number <= hi:
        raise PlanError(f"{name} must be between {lo} and {hi}")
    return number


def normalize_experiment(raw: dict, inventory: dict, endpoints: list[str] | None = None) -> dict:
    """Return a clean copy of an experiment or raise PlanError."""
    elements = {e["ref"]: e for e in inventory["elements"]}
    endpoints = list(endpoints if endpoints is not None else inventory.get("endpoints", []))

    raw_steps = raw.get("steps") or []
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_STEPS:
        raise PlanError(f"an experiment needs 1-{MAX_STEPS} steps")

    steps: list[dict] = []
    total_wait = 0
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            raise PlanError("each step must be an object")
        action = raw_step.get("action")
        if action not in ACTIONS:
            raise PlanError(f"unsupported action {action!r}")
        step: dict[str, Any] = {"action": action}
        if action in ("click", "dblclick", "fill", "type"):
            ref = raw_step.get("ref")
            if ref not in elements:
                raise PlanError(f"unknown element ref {ref!r}")
            step["ref"] = ref
            if action in ("fill", "type"):
                element = elements[ref]
                if not element.get("editable") or element.get("password"):
                    raise PlanError(f"{ref} is not an editable, non-password text field")
                step["value"] = _clean_value(raw_step.get("value"))
        elif action == "press":
            key = raw_step.get("key")
            if key not in KEYS:
                raise PlanError(f"unsupported key {key!r}")
            step["key"] = key
        elif action == "wait":
            step["ms"] = _int(raw_step.get("ms"), 0, 8000, "wait.ms")
            total_wait += step["ms"]
        steps.append(step)
    if total_wait > MAX_WAIT_TOTAL_MS:
        raise PlanError("total waiting time is too long")

    perturbations: list[dict] = []
    for raw_p in raw.get("perturbations") or []:
        kind = raw_p.get("kind")
        if kind not in PERTURBATIONS:
            raise PlanError(f"unsupported perturbation {kind!r}")
        endpoint = str(raw_p.get("endpoint", "")).strip()
        method, path = parse_endpoint(endpoint)
        endpoint = f"{method} {path}"
        if method == "*" and path == "*":
            raise PlanError("perturbations need at least a method or a path")
        if not _endpoint_allowed(endpoint, endpoints):
            raise PlanError(f"endpoint {endpoint!r} was not observed on this page")
        p: dict[str, Any] = {"kind": kind, "endpoint": endpoint,
                             "nth": _int(raw_p.get("nth", 0), 0, 10, "nth")}
        if kind == "delay":
            p["ms"] = _int(raw_p.get("ms"), 50, 5000, "delay.ms")
        else:
            p["status"] = _int(raw_p.get("status") or 500, 400, 599, "fail.status")
        perturbations.append(p)
    if len(perturbations) > 3:
        raise PlanError("at most 3 perturbations per experiment")

    values = cumulative_values(steps)
    clicked = clicked_refs(steps)
    invariants: list[dict] = []
    for raw_i in raw.get("invariants") or []:
        kind = raw_i.get("kind")
        if kind not in INVARIANTS:
            raise PlanError(f"unsupported invariant {kind!r}")
        inv: dict[str, Any] = {"kind": kind}
        if kind == "value_equals":
            ref = raw_i.get("ref")
            if ref not in elements:
                raise PlanError(f"unknown element ref {ref!r}")
            value = str(raw_i.get("value", ""))
            if values.get(ref) != value:
                raise PlanError(f"value_equals on {ref} is not grounded in a fill/type step")
            inv.update(ref=ref, value=value)
        elif kind == "text_contains":
            ref = raw_i.get("ref") or "page"
            if ref != "page" and ref not in elements:
                raise PlanError(f"unknown element ref {ref!r}")
            value = str(raw_i.get("value", ""))
            if not value or value not in values.values():
                raise PlanError("text_contains value must be text typed during the experiment")
            inv.update(ref=ref, value=value)
        elif kind == "focus_returns":
            ref = raw_i.get("ref")
            if ref not in elements or ref not in clicked:
                raise PlanError("focus_returns must name an element the experiment clicked")
            inv.update(ref=ref)
        elif kind == "max_requests":
            endpoint = str(raw_i.get("endpoint", "")).strip()
            method, path = parse_endpoint(endpoint)
            endpoint = f"{method} {path}"
            if not _endpoint_allowed(endpoint, endpoints):
                raise PlanError(f"endpoint {endpoint!r} was not observed on this page")
            inv.update(endpoint=endpoint, max=_int(raw_i.get("max", 1), 0, 5, "max"))
        invariants.append(inv)
    if not 1 <= len(invariants) <= 4:
        raise PlanError("an experiment needs 1-4 invariants")

    return {"steps": steps, "perturbations": perturbations, "invariants": invariants}


def _slug(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(text or "").lower()).strip("-")[:40]
    return slug or fallback


def normalize_plan(raw_plan: Any, inventory: dict, *, id_prefix: str = "h",
                   max_hypotheses: int = MAX_HYPOTHESES) -> tuple[list[dict], list[dict]]:
    """Validate a whole plan. Returns (accepted hypotheses, rejected with reasons)."""
    if isinstance(raw_plan, dict):
        raw_list = raw_plan.get("hypotheses", [])
    else:
        raw_list = raw_plan
    if not isinstance(raw_list, list):
        raise PlanError("plan must contain a list of hypotheses")

    accepted: list[dict] = []
    rejected: list[dict] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_list[: max_hypotheses * 2]):
        hid = _slug(raw.get("id") if isinstance(raw, dict) else "", f"{id_prefix}{index + 1}")
        if hid in seen_ids:
            hid = f"{hid}-{index + 1}"
        seen_ids.add(hid)
        try:
            if not isinstance(raw, dict):
                raise PlanError("hypothesis must be an object")
            experiment = normalize_experiment(raw, inventory)
        except PlanError as exc:
            rejected.append({"id": hid, "claim": str((raw or {}).get("claim", ""))[:200]
                             if isinstance(raw, dict) else "", "reason": str(exc)})
            continue
        fault_class = raw.get("fault_class")
        accepted.append({
            "id": hid,
            "claim": str(raw.get("claim", "")).strip()[:240] or "Unnamed hypothesis",
            "fault_class": fault_class if fault_class in FAULT_CLASSES else "other",
            "rationale": str(raw.get("rationale", "")).strip()[:400],
            **experiment,
        })
        if len(accepted) >= max_hypotheses:
            break
    return accepted, rejected


# --------------------------------------------------------------------------- descriptions

def element_label(ref: str, inventory: dict) -> str:
    if ref == "page":
        return "the page"
    for element in inventory["elements"]:
        if element["ref"] == ref:
            name = element.get("name") or element.get("testid") or element.get("role") or ref
            return f'"{name}"'
    return ref


def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


def describe_step(step: dict, inventory: dict) -> str:
    action = step["action"]
    if action in ("click", "dblclick"):
        verb = "Click" if action == "click" else "Double-click"
        return f"{verb} {element_label(step['ref'], inventory)}"
    if action == "fill":
        return f'Enter "{step["value"]}" into {element_label(step["ref"], inventory)}'
    if action == "type":
        return f'Type "{step["value"]}" into {element_label(step["ref"], inventory)} key by key'
    if action == "press":
        return f"Press {step['key']}"
    if action == "wait":
        return f"Wait {step['ms']} ms"
    if action == "reload":
        return "Reload the page"
    return action


def describe_perturbation(p: dict) -> str:
    which = "every" if p["nth"] == 0 else f"the {_ordinal(p['nth'])}"
    if p["kind"] == "delay":
        return f"Hold {which} {p['endpoint']} request for {p['ms']} ms"
    return f"Answer {which} {p['endpoint']} request with HTTP {p['status']}"


def describe_invariant(inv: dict, inventory: dict) -> str:
    kind = inv["kind"]
    if kind == "value_equals":
        return f'{element_label(inv["ref"], inventory)} still holds "{inv["value"]}"'
    if kind == "text_contains":
        return f'{element_label(inv["ref"], inventory)} reflects "{inv["value"]}"'
    if kind == "focus_returns":
        return f"Focus returns to {element_label(inv['ref'], inventory)} after the dialog closes"
    if kind == "max_requests":
        return f"At most {inv['max']} {inv['endpoint']} request(s) are sent"
    if kind == "no_page_errors":
        return "No uncaught JavaScript errors"
    return kind


def describe_experiment(exp: dict, inventory: dict) -> dict:
    return {
        "steps": [describe_step(s, inventory) for s in exp["steps"]],
        "perturbations": [describe_perturbation(p) for p in exp["perturbations"]],
        "invariants": [describe_invariant(i, inventory) for i in exp["invariants"]],
    }


def without_step(exp: dict, index: int) -> dict:
    clone = copy.deepcopy(exp)
    del clone["steps"][index]
    return clone


def without_perturbation(exp: dict, index: int) -> dict:
    clone = copy.deepcopy(exp)
    del clone["perturbations"][index]
    return clone


# --------------------------------------------------------------------------- JSON schema (structured output)

def _strict_object(properties: dict) -> dict:
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


STEP_SCHEMA = _strict_object({
    "action": {"type": "string", "enum": list(ACTIONS)},
    "ref": {"type": "string", "description": "element ref such as e3; empty for press/wait/reload"},
    "value": {"type": "string", "description": "text for fill/type; empty otherwise"},
    "key": {"type": "string", "description": "key for press; empty otherwise"},
    "ms": {"type": "integer", "description": "milliseconds for wait; 0 otherwise"},
})
PERTURBATION_SCHEMA = _strict_object({
    "kind": {"type": "string", "enum": list(PERTURBATIONS)},
    "endpoint": {"type": "string", "description": "'METHOD /path' from the observed endpoints, or 'POST *'"},
    "ms": {"type": "integer", "description": "delay in ms for kind=delay; 0 otherwise"},
    "nth": {"type": "integer", "description": "1-based matching request to affect; 0 = all"},
    "status": {"type": "integer", "description": "HTTP status for kind=fail; 0 otherwise"},
})
INVARIANT_SCHEMA = _strict_object({
    "kind": {"type": "string", "enum": list(INVARIANTS)},
    "ref": {"type": "string", "description": "element ref, 'page' for text_contains on the whole page, empty otherwise"},
    "value": {"type": "string", "description": "grounded expected text; empty when unused"},
    "endpoint": {"type": "string", "description": "for max_requests; empty otherwise"},
    "max": {"type": "integer", "description": "for max_requests; 0 otherwise"},
})
HYPOTHESIS_SCHEMA = _strict_object({
    "id": {"type": "string"},
    "claim": {"type": "string", "description": "falsifiable statement of how the UI might fail"},
    "fault_class": {"type": "string", "enum": list(FAULT_CLASSES)},
    "rationale": {"type": "string", "description": "why this experiment discriminates this hypothesis"},
    "steps": {"type": "array", "items": STEP_SCHEMA},
    "perturbations": {"type": "array", "items": PERTURBATION_SCHEMA},
    "invariants": {"type": "array", "items": INVARIANT_SCHEMA},
})
PLAN_SCHEMA = _strict_object({"hypotheses": {"type": "array", "items": HYPOTHESIS_SCHEMA}})
DIAGNOSIS_SCHEMA = _strict_object({
    "title": {"type": "string"},
    "root_cause": {"type": "string"},
    "user_impact": {"type": "string"},
    "fix": {"type": "string"},
    "code_reference": {"type": "string", "description": "function or line in the provided source, or empty"},
    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
})
