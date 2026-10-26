"""Counterexample minimisation and cause attribution.

A step is removed only if the remaining experiment is still *grounded* (the
validator accepts it) and still fails with the same signature. Perturbations are
then ablated one by one: if the failure survives without a perturbation, that
perturbation was not needed. This is what turns "something failed" into
"these 3 steps plus this 1 delayed request break your form".
"""
from __future__ import annotations

from typing import Awaitable, Callable

from .vocab import PlanError, normalize_experiment, without_perturbation, without_step

RunFn = Callable[[dict], Awaitable[dict]]


def _same_failure(result: dict, target: str) -> bool:
    return result["status"] == "failed" and target in result["signature"]


async def minimize(run: RunFn, exp: dict, target: str, inventory: dict, *, budget: int = 20) -> dict:
    current = {k: exp[k] for k in ("steps", "perturbations", "invariants")}
    attempts = 0
    progress = True
    while progress and attempts < budget:
        progress = False
        for index in range(len(current["steps"]) - 1, -1, -1):
            if len(current["steps"]) == 1:
                break
            candidate = without_step(current, index)
            try:
                candidate = normalize_experiment(candidate, inventory)
            except PlanError:
                continue  # removing this step would make an invariant ungrounded
            attempts += 1
            if _same_failure(await run(candidate), target):
                current = candidate
                progress = True
                break
            if attempts >= budget:
                break

    # Shorten waits: try halving each wait once.
    for index, step in enumerate(current["steps"]):
        if step["action"] == "wait" and step["ms"] >= 400 and attempts < budget + 6:
            candidate = {**current, "steps": [dict(s) for s in current["steps"]]}
            candidate["steps"][index]["ms"] = step["ms"] // 2
            attempts += 1
            if _same_failure(await run(candidate), target):
                current = candidate

    # Ablate perturbations: which ones are actually required?
    required = list(current["perturbations"])
    controls_log = []
    index = 0
    while index < len(required):
        candidate = without_perturbation({**current, "perturbations": required}, index)
        controls = [await run(candidate) for _ in range(2)]
        attempts += 2
        still_failing = sum(_same_failure(r, target) for r in controls)
        if still_failing == len(controls):
            required = candidate["perturbations"]
        else:
            controls_log.append({"perturbation": required[index], "runs": len(controls),
                                 "failures_without_it": still_failing})
            index += 1
    current = {**current, "perturbations": required}
    return {"experiment": current, "attempts": attempts, "controls": controls_log}


def attribution(required: list[dict], controls: list[dict] | None = None) -> str:
    if not required:
        return "deterministic: reproduces without any network perturbation"
    controls = controls or []
    evidence = "; ".join(f"without it {c['failures_without_it']}/{c['runs']} control runs failed" for c in controls)
    kinds = {p["kind"] for p in required}
    if kinds == {"delay"}:
        label = "timing-dependent: needs the slowed request"
    elif kinds == {"fail"}:
        label = "error-path bug: needs the failing request"
    else:
        label = "needs both a slowed and a failing request"
    return f"{label} ({evidence})" if evidence else label
