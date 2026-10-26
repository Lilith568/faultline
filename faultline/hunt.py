"""Orchestration: discover -> plan -> run -> follow-up -> minimize -> confirm -> diagnose -> export."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from playwright.async_api import Browser, async_playwright

from .config import Settings, check_target, get_settings
from .auth import load_storage_state, scope_storage_state
from .discover import discover
from .executor import run_experiment
from .export import spec_filename, to_playwright_spec, to_repro
from .meta import MetaClient, MetaError
from .vocab import PlanError
from .minimize import attribution, minimize
from .planners import heuristic_plan, meta_diagnosis, meta_plan, template_diagnosis
from .vocab import describe_experiment, describe_invariant, normalize_plan

Emit = Callable[[str, str, dict | None], None]


def _noop(kind: str, message: str, data: dict | None = None) -> None:
    pass


def _invariant_text(exp: dict, failing: dict, inventory: dict) -> str:
    for inv in exp["invariants"]:
        if inv["kind"] == failing["kind"] and inv.get("ref") == failing.get("ref") \
                and inv.get("endpoint") == failing.get("endpoint"):
            return describe_invariant(inv, inventory)
    return failing["kind"]


class Hunt:
    def __init__(self, url: str, goal: str = "", planner: str = "auto", rounds: int = 2,
                 confirm_runs: int = 3, include_source: bool = False, settings: Settings | None = None,
                 emit: Emit = _noop, meta_transport=None, hunt_id: str | None = None,
                 recorded_plan: dict | None = None, storage_state: str | Path | dict | None = None):
        self.settings = settings or get_settings()
        check_target(url, self.settings)
        self.url = url
        self.goal = goal.strip()[:600]
        self.planner = planner
        self.rounds = max(1, min(rounds, 3))
        self.confirm_runs = max(1, min(confirm_runs, 5))
        self.include_source = include_source
        self._emit_callback = emit
        self.warnings: list[str] = []
        self.emit = self._emit
        self.storage_state = (scope_storage_state(storage_state, url) if isinstance(storage_state, dict)
                              else load_storage_state(storage_state, url))
        self.meta_transport = meta_transport
        self.id = hunt_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.dir = Path(self.settings.artifacts) / self.id
        self.browser_runs = 0
        self.recorded_plan = recorded_plan  # replay a saved model plan without calling the API

    # ------------------------------------------------------------------ helpers
    def _emit(self, kind: str, message: str, data: dict | None = None) -> None:
        if kind == "warning":
            self.warnings.append(message)
        self._emit_callback(kind, message, data)

    def _phase(self, phase: str, message: str, **data) -> None:
        self.emit("phase", message, {"phase": phase, "phase_status": "active", **data})

    async def _run(self, browser: Browser, exp: dict, inventory: dict, **kwargs) -> dict:
        self.browser_runs += 1
        self.emit("metrics", "Browser run started", {"browser_runs": self.browser_runs})
        return await run_experiment(browser, self.url, exp, inventory, storage_state=self.storage_state, **kwargs)

    async def _run_round(self, browser: Browser, hypotheses: list[dict], inventory: dict, round_no: int) -> None:
        semaphore = asyncio.Semaphore(3)

        async def one(hyp: dict) -> None:
            async with semaphore:
                self.emit("experiment", f"Testing: {hyp['claim']}", {"id": hyp["id"], "round": round_no})
                hyp["result"] = await self._run(browser, hyp, inventory)
                self.emit("result", f"{hyp['id']}: {hyp['result']['status']}",
                          {"id": hyp["id"], "status": hyp["result"]["status"], "round": round_no})

        await asyncio.gather(*(one(h) for h in hypotheses))

    # ------------------------------------------------------------------ main
    async def run(self) -> dict[str, Any]:
        started = time.monotonic()
        self.dir.mkdir(parents=True, exist_ok=True)
        report: dict[str, Any] = {
            "id": self.id, "url": self.url, "goal": self.goal,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "planner": {"requested": self.planner, "used": None, "model": None, "fallback_reason": None,
                        "backend": getattr(self.settings, "backend", "meta")},
            "rounds": [], "counterexamples": [], "unconfirmed": [], "meta_calls": [],
            "warnings": self.warnings, "authenticated": bool(self.storage_state),
        }
        client = None
        use_meta = self.planner in ("auto", "meta") and self.settings.meta_configured
        if self.planner == "meta" and not self.settings.meta_configured:
            report["planner"]["fallback_reason"] = "MODEL_API_KEY is not set"
        if use_meta:
            client = MetaClient(self.settings, transport=self.meta_transport)
            report["planner"]["model"] = self.settings.model

        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                self._phase("explore", "Exploring the page")
                inventory = await discover(browser, self.url, storage_state=self.storage_state)
                report["inventory"] = {k: inventory[k] for k in ("title", "elements", "endpoints", "notes")}
                self.emit("inventory", f"Found {len(inventory['elements'])} controls and "
                          f"{len(inventory['endpoints'])} API endpoints", {"endpoints": inventory["endpoints"]})

                # Round 1
                self._phase("hypotheses", "Preparing hypotheses")
                hypotheses, rejected, source = [], [], "heuristic"
                if self.recorded_plan:
                    hypotheses, rejected = normalize_plan(self.recorded_plan["plan"], inventory)
                    source = "recorded"
                    report["planner"]["model"] = self.recorded_plan.get("provenance", {}).get("model")
                elif client:
                    self._phase("hypotheses", f"Asking {self.settings.model} for hypotheses")
                    try:
                        hypotheses, rejected = await meta_plan(client, inventory, self.goal)
                        source = "meta"
                    except (MetaError, PlanError, ValueError, KeyError, TypeError) as exc:
                        report["planner"]["fallback_reason"] = f"Meta planner failed: {type(exc).__name__}: {exc}"[:300]
                        self.emit("warning", report["planner"]["fallback_reason"], None)
                    if source == "meta" and not hypotheses:
                        report["planner"]["fallback_reason"] = "Meta plan had no valid experiments"
                        source = "heuristic"
                if source == "heuristic":
                    hypotheses = heuristic_plan(inventory)
                report["planner"]["used"] = source
                self.emit("plan", f"{len(hypotheses)} hypotheses ({source})",
                          {"hypotheses": [{"id": h["id"], "claim": h["claim"], "fault_class": h["fault_class"]}
                                          for h in hypotheses], "rejected": rejected})
                self._phase("verify", "Testing the hypotheses", round=1)
                await self._run_round(browser, hypotheses, inventory, 1)
                report["rounds"].append({"round": 1, "source": source, "hypotheses": hypotheses,
                                         "rejected": rejected})

                # Follow-up rounds (Meta only): the model sees verified results and adapts.
                all_hyps = list(hypotheses)
                for round_no in range(2, self.rounds + 1):
                    if source != "meta":
                        break
                    self._phase("followup", f"Round {round_no}: Muse reviews the verified results", round=round_no)
                    try:
                        follow, rejected2 = await meta_plan(client, inventory, self.goal, previous=all_hyps,
                                                            id_prefix=f"r{round_no}-")
                    except (MetaError, PlanError, ValueError, KeyError, TypeError) as exc:
                        self.emit("warning", f"Follow-up round skipped: {type(exc).__name__}: {exc}"[:300], None)
                        break
                    existing = {h["id"] for h in all_hyps}
                    for hyp in follow:
                        if hyp["id"] in existing:
                            hyp["id"] = f"r{round_no}-{hyp['id']}"
                    if not follow:
                        if rejected2:
                            report["rounds"].append({"round": round_no, "source": "meta", "hypotheses": [],
                                                     "rejected": rejected2})
                            self.emit("warning", "Follow-up round skipped: no valid experiments", None)
                        break
                    self.emit("plan", f"{len(follow)} follow-up experiments",
                              {"hypotheses": [{"id": h["id"], "claim": h["claim"], "fault_class": h["fault_class"]}
                                              for h in follow], "rejected": rejected2, "round": round_no})
                    self._phase("verify", "Testing the follow-up hypotheses", round=round_no)
                    await self._run_round(browser, follow, inventory, round_no)
                    report["rounds"].append({"round": round_no, "source": "meta", "hypotheses": follow,
                                             "rejected": rejected2})
                    all_hyps.extend(follow)

                # Counterexamples: group failing experiments by (first failing invariant, fault class)
                groups: dict[tuple[str, str], list[dict]] = {}
                for hyp in all_hyps:
                    result = hyp.get("result") or {}
                    if result.get("status") == "failed":
                        key = (result["signature"][0], hyp["fault_class"])
                        groups.setdefault(key, []).append(hyp)

                for (target, fault_class), members in groups.items():
                    members.sort(key=lambda h: (len(h["steps"]), len(h["perturbations"])))
                    primary = members[0]
                    self._phase("minimize", f"Minimizing: {primary['claim']}", id=primary["id"])
                    runner = lambda exp: self._run(browser, exp, inventory)  # noqa: E731
                    reduced = await minimize(runner, primary, target, inventory)
                    minimal = reduced["experiment"]
                    cx_index = len(report["counterexamples"]) + len(report["unconfirmed"]) + 1
                    shots = self.dir / f"cx{cx_index}"
                    confirmations = []
                    for attempt in range(self.confirm_runs):
                        kwargs = {}
                        if attempt == 0:
                            kwargs = {"screenshot": shots / "failing-state.png", "trace": shots / "trace.zip"}
                        confirmations.append(await self._run(browser, minimal, inventory, **kwargs))
                    failures = sum(1 for c in confirmations if c["status"] == "failed" and target in c["signature"])
                    if failures < len(confirmations):
                        # Not reproducible every time: report it, but never as a verified failure.
                        report["unconfirmed"].append({
                            "title": primary["claim"], "fault_class": fault_class, "signature": target,
                            "hypothesis_ids": [h["id"] for h in members],
                            "confirmation": {"runs": len(confirmations), "failures": failures},
                            "steps": describe_experiment(minimal, inventory)["steps"],
                        })
                        self.emit("warning", f"Not reproducible every time ({failures}/{len(confirmations)}), "
                                  f"not reported as verified: {primary['claim']}", None)
                        continue
                    first = confirmations[0]
                    failing = next((r for r in first["invariants"] if r["status"] == "fail"), None) or \
                        next(r for r in primary["result"]["invariants"] if r["status"] == "fail")
                    refs = {s["ref"] for s in minimal["steps"] if s.get("ref")} | \
                           {i["ref"] for i in minimal["invariants"] if i.get("ref") and i["ref"] != "page"}
                    elements = {e["ref"]: e for e in inventory["elements"] if e["ref"] in refs}
                    text = describe_experiment(minimal, inventory)
                    cx = {
                        "id": f"cx{cx_index}",
                        "title": primary["claim"],
                        "claim": primary["claim"],
                        "fault_class": fault_class,
                        "hypothesis_ids": [h["id"] for h in members],
                        "signature": target,
                        "original_steps": len(primary["steps"]),
                        "experiment": minimal,
                        "elements": elements,
                        "text": text,
                        "failure": {"invariant": _invariant_text(minimal, failing, inventory),
                                    "expected": failing["expected"], "actual": failing["actual"]},
                        "attribution": attribution(minimal["perturbations"], reduced.get("controls")),
                        "controls": reduced.get("controls", []),
                        "minimization_attempts": reduced["attempts"],
                        "confirmation": {"runs": len(confirmations), "failures": failures,
                                         "confirmed": failures == len(confirmations)},
                        "network": first["network"],
                        "screenshot": first.get("screenshot"),
                        "trace": first.get("trace"),
                    }
                    # Diagnosis
                    self._phase("diagnose", f"Explaining {cx['id']}", id=cx["id"])
                    diagnosis = None
                    if client:
                        self._phase("diagnose", f"Asking {self.settings.model} to diagnose {cx['id']}", id=cx["id"])
                        try:
                            png = Path(cx["screenshot"]).read_bytes() if cx.get("screenshot") else None
                            diagnosis = await meta_diagnosis(client, cx, inventory, self.include_source, png)
                        except (MetaError, OSError, ValueError, KeyError, TypeError) as exc:
                            self.emit("warning", f"Diagnosis fell back to a template: {type(exc).__name__}: {exc}"[:300],
                                      None)
                    cx["diagnosis"] = diagnosis or template_diagnosis(fault_class, {"title": cx["title"]})
                    # Exports
                    self._phase("export", f"Exporting the test for {cx['id']}", id=cx["id"])
                    spec = to_playwright_spec(cx, self.url)
                    (shots / spec_filename(cx)).write_text(spec, encoding="utf-8")
                    (shots / "repro.json").write_text(json.dumps(to_repro(cx, self.url), indent=2), encoding="utf-8")
                    cx["spec_file"] = str(shots / spec_filename(cx))
                    cx["repro_file"] = str(shots / "repro.json")
                    report["counterexamples"].append(cx)
                    self.emit("counterexample", f"{cx['id']} confirmed {failures}/{len(confirmations)}: {cx['title']}",
                              {"id": cx["id"]})
            finally:
                await browser.close()
                if client:
                    report["meta_calls"] = client.calls
                    await client.close()

        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["stats"] = {
            "experiments": sum(len(r["hypotheses"]) for r in report["rounds"]),
            "browser_runs": self.browser_runs,
            "duration_s": round(time.monotonic() - started, 1),
            "meta_calls": len(report["meta_calls"]),
            "input_tokens": sum(c.get("input_tokens") or 0 for c in report["meta_calls"]),
            "output_tokens": sum(c.get("output_tokens") or 0 for c in report["meta_calls"]),
        }
        (self.dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        self.emit("done", f"Done: {len(report['counterexamples'])} verified counterexample(s)", None)
        return report


async def replay(repro: dict, url: str | None = None, settings: Settings | None = None, *,
                 storage_state: str | Path | dict | None = None) -> dict:
    """Re-run a saved minimized counterexample (e.g. against the fixed build)."""
    settings = settings or get_settings()
    target = url or repro["url"]
    check_target(target, settings)
    state = (scope_storage_state(storage_state, target) if isinstance(storage_state, dict)
             else load_storage_state(storage_state, target))
    inventory = {"elements": list(repro["elements"].values())}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            result = await run_experiment(browser, target, repro["experiment"], inventory, storage_state=state)
        finally:
            await browser.close()
    return result
