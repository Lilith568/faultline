"""Summarize every preserved evaluation attempt without selecting the best run."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import ROOT, GROUND_TRUTH, HELD_OUT, atomic_json, cell, refresh_totals, unique_directory, utc_now  # noqa: E402



def validate_result(result) -> None:
    """Reject malformed evidence and derive all totals again from checked rows."""
    if not isinstance(result, dict) or result.get("schema_version") != 2:
        raise ValueError("unsupported evaluation schema")
    if not isinstance(result.get("run_id"), str) or not result["run_id"]:
        raise ValueError("missing run_id")
    if result.get("status") not in {"running", "completed", "degraded", "error", "incomplete", "interrupted"}:
        raise ValueError("unknown run status")
    if result.get("planner") not in {"meta", "heuristic", "recorded"}:
        raise ValueError("unknown planner")
    apps = result.get("requested_apps")
    if (not isinstance(apps, list) or not apps or any(not isinstance(a, str) or a not in GROUND_TRUTH for a in apps)
            or len(set(apps)) != len(apps)):
        raise ValueError("invalid requested apps")
    rows = result.get("rows")
    if not isinstance(rows, list) or len(rows) != len(apps) * 2 or result.get("planned_targets") != len(rows):
        raise ValueError("rows must list every planned target")
    pairs = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("app") not in apps or row.get("mode") not in {"buggy", "fixed"}:
            raise ValueError("invalid target row")
        pair = (row["app"], row["mode"])
        if pair in pairs:
            raise ValueError("duplicate target row")
        pairs.add(pair)
        if row.get("status") not in {"pending", "running", "completed", "error"}:
            raise ValueError("invalid target status")
        expected = [b["id"] for b in GROUND_TRUTH[row["app"]]] if row["mode"] == "buggy" else []
        if row.get("expected_bugs") != expected or row.get("held_out") != (row["app"] in HELD_OUT):
            raise ValueError("target ground truth does not match this evaluation protocol")
        if (not isinstance(row.get("found"), list) or any(not isinstance(b, str) or b not in expected for b in row["found"])
                or len(set(row["found"])) != len(row["found"]) or not isinstance(row.get("unexpected"), list)):
            raise ValueError("invalid finding counts")
        for key in ("browser_runs", "meta_calls", "input_tokens", "output_tokens", "seconds"):
            if not isinstance(row.get(key, 0), (int, float)) or not math.isfinite(row.get(key, 0)) or row.get(key, 0) < 0:
                raise ValueError("invalid numeric target statistic")
        if "execution_complete" in row and not isinstance(row["execution_complete"], bool):
            raise ValueError("invalid execution completion flag")
        if not isinstance(row.get("meta_complete", False), bool):
            raise ValueError("invalid Meta completion flag")
    metadata = result.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("comparison_fingerprint"), str):
        raise ValueError("missing comparison fingerprint")
    config = metadata.get("configuration")
    if not isinstance(config, dict) or config.get("planner") != result["planner"] or config.get("apps") != apps:
        raise ValueError("configuration does not match run")
    refresh_totals(result)
    if result["status"] == "completed" and (result["coverage"]["completed"] != result["planned_targets"]
            or (result["planner"] == "meta" and not all(r["meta_complete"] for r in rows))):
        raise ValueError("completed status contradicts target evidence")


def summarize(root: Path) -> dict:
    groups: dict[str, dict] = {}
    errors = []
    seen = set()
    files = sorted(root.rglob("result.json"))
    for path in files:
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            validate_result(result)
            run_id = result["run_id"]
            if run_id in seen:
                raise ValueError("duplicate run_id; not counted twice: " + run_id)
            fingerprint = result["metadata"]["comparison_fingerprint"]
            group = groups.setdefault(fingerprint, {
                "comparison_fingerprint": fingerprint, "configuration": result["metadata"]["configuration"],
                "runs": [], "status_counts": {}, "metrics": {}, "bugs": {}, "fixed_builds": {}})
            seen.add(run_id)
            group["runs"].append({"run_id": run_id, "status": result["status"],
                                  "path": str(path.resolve()), "result": result})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"path": str(path.resolve()), "error": f"{type(exc).__name__}: {exc}"})
    for group in groups.values():
        runs = group["runs"]
        group["status_counts"] = dict(Counter(r["status"] for r in runs))
        group["source_stability_counts"] = dict(Counter(
            "unchanged" if r["result"].get("source_unchanged_during_run") is True else
            "changed_or_unverifiable" if r["result"].get("source_unchanged_during_run") is False else
            "not_recorded" for r in runs))
        eligible = [r["result"] for r in runs if r["status"] == "completed"
                    and r["result"].get("coverage", {}).get("completed") == r["result"].get("planned_targets")
                    and r["result"].get("source_unchanged_during_run") is True
                    and all(row.get("execution_complete", False) for row in r["result"]["rows"])]
        group["metrics"]["complete_evaluations"] = len(eligible)
        group["metrics"]["total_attempts"] = len(runs)
        for key in ("dev_apps", "held_out_apps"):
            counts = [r[key]["found"] for r in eligible]
            totals = [r[key]["expected"] for r in eligible]
            group["metrics"][key] = {
                "runs": len(counts), "found_each_run": counts, "expected_each_run": totals,
                "found_mean": mean(counts) if counts else None,
                "found_min": min(counts) if counts else None,
                "found_max": max(counts) if counts else None,
                "false_alarms_each_run": [r[key]["false_positives_on_fixed_builds"] for r in eligible],
            }
        for entry in runs:
            result = entry.pop("result")
            for row in result["rows"]:
                for bug in row["expected_bugs"]:
                    counts = group["bugs"].setdefault(bug, {"targets_listed": 0, "completed_targets": 0,
                                                           "found_in_completed_targets": 0,
                                                           "found_in_complete_evaluations": 0})
                    counts["targets_listed"] += 1
                    counts["completed_targets"] += row["status"] == "completed"
                    counts["found_in_completed_targets"] += row["status"] == "completed" and bug in row["found"]
                    counts["found_in_complete_evaluations"] += result in eligible and bug in row["found"]
                if row["mode"] == "fixed":
                    counts = group["fixed_builds"].setdefault(row["app"], {"targets_listed": 0,
                        "completed_targets": 0, "false_alarms_on_completed_targets": 0})
                    counts["targets_listed"] += 1
                    counts["completed_targets"] += row["status"] == "completed"
                    if row["status"] == "completed":
                        counts["false_alarms_on_completed_targets"] += len(row["unexpected"])
    return {"schema_version": 1, "created_at": utc_now(), "source_directory": str(root.resolve()),
            "result_files_seen": len(files), "attempts_counted": len(seen),
            "groups": list(groups.values()), "input_errors": errors,
            "interpretation": "Groups match code/configuration/dependency fingerprints. All attempt statuses are shown. "
                              "Detection ranges require complete evaluations with applicable checks and unchanged runtime hashes; "
                              "partial, fallback and source-unverified runs remain visible. "
                              "Repeated runs on the same small apps do not measure real-world accuracy."}


def to_markdown(summary: dict) -> str:
    lines = ["# Evaluation summary", "", f"Created: {summary['created_at']}",
             f"Result files seen: {summary['result_files_seen']}; attempts counted: {summary['attempts_counted']}.",
             "", summary["interpretation"], ""]
    for i, group in enumerate(summary["groups"], 1):
        cfg, metrics = group["configuration"], group["metrics"]
        lines += [f"## Comparable group {i}", "", f"Fingerprint: `{group['comparison_fingerprint']}`",
                  f"Planner: {cfg['planner']}; model: {cfg.get('model') or 'none'}; apps: {', '.join(cfg['apps'])}.",
                  "Attempts: " + ", ".join(f"{k}={v}" for k, v in sorted(group["status_counts"].items())) + ".",
                  "Runtime hash checks: " + ", ".join(f"{k}={v}" for k, v in sorted(group["source_stability_counts"].items())) + ".",
                  f"Complete evaluations used for detection ranges: {metrics['complete_evaluations']} of {metrics['total_attempts']} attempts.", "",
                  "| Set | Found per complete run | Known bugs per run | Mean found | Range | False alarms per complete run |",
                  "|---|---|---|---|---|---|"]
        for label, key in (("Dev", "dev_apps"), ("Held out", "held_out_apps")):
            m = metrics[key]
            interval = f"{m['found_min']}–{m['found_max']}" if m["runs"] else "not measured"
            lines.append(f"| {label} | {cell(m['found_each_run'])} | {cell(m['expected_each_run'])} | "
                         f"{m['found_mean'] if m['runs'] else 'not measured'} | {interval} | {cell(m['false_alarms_each_run'])} |")
        lines += ["", "All targets below include fallback and partial runs. They are coverage evidence, not pure model scores.", "",
                  "| Known bug | Targets completed / listed | Found in completed targets | Found in complete evaluations |",
                  "|---|---|---|---|"]
        for bug, m in sorted(group["bugs"].items()):
            lines.append(f"| {cell(bug)} | {m['completed_targets']}/{m['targets_listed']} | "
                         f"{m['found_in_completed_targets']} | {m['found_in_complete_evaluations']} |")
        lines += ["", "| Fixed build | Targets completed / listed | False alarms on completed targets |",
                  "|---|---|---|"]
        for app, m in sorted(group["fixed_builds"].items()):
            lines.append(f"| {cell(app)} | {m['completed_targets']}/{m['targets_listed']} | "
                         f"{m['false_alarms_on_completed_targets']} |")
        lines += ["", "| Attempt | Status |", "|---|---|"]
        lines.extend(f"| {cell(r['run_id'])} | {cell(r['status'])} |" for r in group["runs"])
        lines.append("")
    if summary["input_errors"]:
        lines += ["## Input problems", "", "These files were not silently discarded:", ""]
        lines.extend(f"- {cell(e['path'])}: {cell(e['error'])}" for e in summary["input_errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=ROOT / "eval" / "runs")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "eval" / "summaries")
    args = parser.parse_args()
    result = summarize(args.runs)
    directory = unique_directory(args.output_dir, "summary")
    atomic_json(directory / "summary.json", result)
    (directory / "summary.md").write_text(to_markdown(result), encoding="utf-8")
    print(f"Saved {directory / 'summary.md'}")
    return 2 if result["input_errors"] or not result["attempts_counted"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
