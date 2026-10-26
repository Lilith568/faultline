"""Run an explicitly labelled, rules-only compatibility probe on a local upstream app.

This is not the known-bug benchmark. A zero-finding result with no applicable
experiments is recorded as no coverage, never as a pass or proof of correctness.
Upstream source files are not modified or sent to any model.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from faultline.config import check_target, get_settings
from faultline.hunt import Hunt


def coverage(report: dict) -> dict:
    hypotheses = [h for r in report.get("rounds", []) for h in r.get("hypotheses", [])]
    statuses = Counter(h.get("result", {}).get("status", "missing") for h in hypotheses)
    invariants = Counter(
        i.get("status", "missing")
        for h in hypotheses for i in h.get("result", {}).get("invariants", [])
    )
    meaningful = statuses["passed"] + statuses["failed"]
    return {
        "controls_discovered": len(report.get("inventory", {}).get("elements", [])),
        "api_endpoints_observed": len(report.get("inventory", {}).get("endpoints", [])),
        "experiments_planned": len(hypotheses),
        "experiment_statuses": dict(statuses),
        "invariant_statuses": dict(invariants),
        "applicable_experiments": meaningful,
        "verified_counterexamples": len(report.get("counterexamples", [])),
        "unconfirmed_counterexamples": len(report.get("unconfirmed", [])),
        "coverage_status": "some_experiments_executed" if meaningful else "no_applicable_experiments",
        "interpretation": (
            "Exploratory evidence only; upstream bugs require independent review."
            if meaningful else "No verdict about upstream correctness: no applicable experiments ran."
        ),
    }


def fingerprint() -> dict:
    files = sorted((ROOT / "faultline").glob("*.py")) + [Path(__file__)]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"sha256": digest, "files": hashes}


async def probe(args: argparse.Namespace) -> tuple[Path, dict]:
    # Deliberately prevent API calls even if the operator has an API key configured.
    settings = replace(get_settings(), api_key=None, allow_remote=False)
    check_target(args.url, settings)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:8]
    output = Path(args.output_root).resolve() / run_id
    output.mkdir(parents=True, exist_ok=False)
    settings = replace(settings, artifacts=output / "artifacts")
    result = {
        "schema_version": 1,
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "application": args.application,
        "target_url": args.url,
        "scope": "exploratory_upstream_compatibility",
        "planner": "heuristic",
        "meta_api_called": False,
        "upstream": {
            "repository": args.repository,
            "commit": args.commit,
            "license": args.license,
            "license_url": args.license_url,
            "archive_sha256": args.archive_sha256,
            "source_modified": False,
        },
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
        "faultline_source": fingerprint(),
        "status": "running",
    }
    result_path = output / "result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    try:
        report = await Hunt(args.url, goal=args.goal, planner="heuristic", settings=settings).run()
        result.update(coverage(report))
        result["status"] = "completed"
        result["report_file"] = f"artifacts/{report['id']}/report.json"
        result["browser_runs"] = report.get("stats", {}).get("browser_runs")
        result["duration_s"] = report.get("stats", {}).get("duration_s")
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    result["source_unchanged_during_run"] = fingerprint() == result["faultline_source"]
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result_path, result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Local, disposable development build only")
    parser.add_argument("--application", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--license", default="MIT")
    parser.add_argument("--license-url", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--goal", default="Users must not lose unsaved input or see stale state.")
    parser.add_argument("--output-root", default=str(ROOT / "eval" / "external"))
    args = parser.parse_args()
    path, result = asyncio.run(probe(args))
    print(path)
    print(json.dumps({k: result.get(k) for k in (
        "status", "coverage_status", "experiments_planned", "applicable_experiments", "verified_counterexamples"
    )}, indent=2))
    # Inconclusive coverage is deliberately nonzero, matching a conservative CI gate.
    if (result["status"] != "completed" or not result.get("applicable_experiments")
            or not result.get("source_unchanged_during_run")):
        return 2
    return 1 if result.get("verified_counterexamples") else 0


if __name__ == "__main__":
    raise SystemExit(main())
