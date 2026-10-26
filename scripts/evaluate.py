"""Evaluate local demo builds and preserve every attempt in a separate run directory.

The original ground truth is unchanged. Live Meta, fallback and recorded evidence
must never be combined into a single model score.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys
import time
from typing import Callable
import urllib.request
from urllib.parse import urlsplit, urlunsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from faultline.config import get_settings  # noqa: E402
from faultline.hunt import Hunt  # noqa: E402

GROUND_TRUTH = {
    "profile": [
        {"id": "profile-overwrite", "bug": "server response overwrites text the user typed in the editor",
         "kinds": ["value_equals", "text_contains"], "targets": ["display-name", "bio"], "requires": None},
        {"id": "profile-focus", "bug": "focus is not returned to 'Edit profile' after the dialog closes",
         "kinds": ["focus_returns"], "targets": ["edit-profile"], "requires": None},
    ],
    "search": [
        {"id": "search-order", "bug": "a late response for an older query replaces newer results",
         "kinds": ["text_contains"], "targets": ["search-summary", "search-results", "page"], "requires": "delay"},
    ],
    "checkout": [
        {"id": "checkout-double", "bug": "double-click places two orders",
         "kinds": ["max_requests"], "targets": ["/demo-api/orders", "*"], "requires": None},
    ],
    "settings": [
        {"id": "settings-errorloss", "bug": "a failed save reverts the user's edits",
         "kinds": ["value_equals"], "targets": ["alert-email", "digest-time"], "requires": "fail"},
        {"id": "settings-stale-load", "bug": "a slow initial load overwrites early edits",
         "kinds": ["value_equals"], "targets": ["alert-email", "digest-time"], "requires": "delay"},
    ],
    "composer": [
        {"id": "composer-draft", "bug": "switching to Preview and back discards the draft",
         "kinds": ["value_equals", "text_contains"], "targets": ["notes-input", "notes-preview", "editor-panel", "page"],
         "requires": None},
        {"id": "composer-double", "bug": "double-click publishes twice",
         "kinds": ["max_requests"], "targets": ["/demo-api/notes", "*"], "requires": None},
    ],
    "newsletter": [
        {"id": "newsletter-focus", "bug": "focus is lost after closing the signup dialog",
         "kinds": ["focus_returns"], "targets": ["open-signup"], "requires": None},
        {"id": "newsletter-errorloss", "bug": "a failed signup clears the form",
         "kinds": ["value_equals"], "targets": ["signup-email", "signup-name"], "requires": "fail"},
    ],
}
HELD_OUT = {"composer", "newsletter"}


def _cx_facts(cx: dict) -> tuple[str, str, set[str]]:
    kind, _, target = cx["signature"].partition(":")
    if kind in ("max_requests",):
        target = target.split(" ", 1)[1] if " " in target else target
    elif target in cx["elements"]:
        target = cx["elements"][target].get("testid") or cx["elements"][target].get("name")
    required = {p["kind"] for p in cx["experiment"]["perturbations"]}
    return kind, target, required


def match(cx: dict, bugs: list[dict]) -> str | None:
    kind, target, required = _cx_facts(cx)
    for bug in bugs:
        if kind in bug["kinds"] and target in bug["targets"] and (bug["requires"] is None or bug["requires"] in required):
            return bug["id"]
    return None



def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url: str) -> None:
    for _ in range(80):
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("server did not start")


def stop_server(server) -> None:
    if server is None:
        return
    server.terminate()
    try:
        server.wait(timeout=8)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


def unique_directory(parent: Path, label: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + label + "-" + uuid.uuid4().hex[:8]
        path = parent / name
        try:
            path.mkdir()
            return path
        except FileExistsError:
            continue
    raise RuntimeError("Could not reserve an unused run directory")


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def redact(value, secret: str | None = None):
    """Keep evidence useful without saving an API key or URL credentials."""
    if isinstance(value, dict):
        return {k: "[redacted]" if re.search(r"api[_-]?key|authorization|password|cookie|token$", k, re.I)
                else redact(v, secret) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secret) for v in value]
    if not isinstance(value, str):
        return value
    if secret:
        value = value.replace(secret, "[redacted]")
    value = re.sub(r"(?i)Bearer\s+[^\s\"',;]+", "Bearer [redacted]", value)
    value = re.sub(r"(?i)(api[_-]?key|access_token|password)(\s*[:=]\s*)[^\s&\"',;]+",
                   r"\1\2[redacted]", value)
    return re.sub(r"https?://[^\s\"'<>]+", _safe_url_match, value)


def _safe_url_match(match) -> str:
    raw = match.group(0)
    try:
        parts = urlsplit(raw)
        hostname = parts.hostname or ""
        if ":" in hostname:
            hostname = "[" + hostname + "]"
        authority = hostname + (":" + str(parts.port) if parts.port else "")
        return urlunsplit((parts.scheme, authority, parts.path, "", ""))
    except ValueError:
        return "[redacted URL]"


def source_hashes() -> dict[str, str]:
    """Hash runtime, fixtures and evaluation tools without reading secrets or artifacts."""
    paths = sorted(p for folder in (ROOT / "faultline", ROOT / "scripts")
                   for p in folder.rglob("*") if p.is_file() and p.suffix in {".py", ".html", ".css"})
    if (ROOT / "pyproject.toml").exists():
        paths.append(ROOT / "pyproject.toml")
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def final_source_check(result: dict) -> None:
    """Changing executable sources during a run invalidates a final comparison."""
    before = {k: v for k, v in result["metadata"]["source_sha256"].items() if "/static/" not in k}
    try:
        after = {k: v for k, v in source_hashes().items() if "/static/" not in k}
        result["source_sha256_after"] = after
        changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
        result["source_changes_during_run"] = changed
        result["source_unchanged_during_run"] = not changed
    except OSError as exc:
        result["source_unchanged_during_run"] = False
        result["errors"].append(f"Could not verify final runtime source hashes: {type(exc).__name__}")
    if not result["source_unchanged_during_run"] and result["status"] == "completed":
        result["status"] = "degraded"


def evidence_metadata(settings, apps: list[str], planner: str) -> dict:
    hashes = source_hashes()
    versions = {}
    for name in ("playwright", "fastapi", "httpx", "uvicorn"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    git = {"commit": None, "dirty": None, "available": False}
    # A snapshot without .git must not inherit an unrelated ancestor repository.
    if (ROOT / ".git").exists():
        try:
            git = {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)),
                   "available": True}
        except (OSError, subprocess.SubprocessError):
            pass
    config = {"planner": planner, "apps": apps, "model": settings.model if planner == "meta" else None,
              "reasoning_effort": settings.reasoning_effort if planner == "meta" else None,
              "backend": getattr(settings, "backend", "meta"),
              "supports_vision": getattr(settings, "supports_vision", True),
              "json_mode": getattr(settings, "json_mode", "json_schema"), "rounds": 2, "confirmation_runs": 3,
              "endpoint": redact(settings.base_url, settings.api_key) if planner == "meta" else None}
    ground_hash = hashlib.sha256(json.dumps(GROUND_TRUTH, sort_keys=True).encode()).hexdigest()
    # UI changes do not invalidate a detection comparison; runtime/planner changes do.
    detection_hashes = {k: v for k, v in hashes.items() if "/static/" not in k}
    fingerprint = hashlib.sha256(json.dumps({"config": config, "sources": detection_hashes,
                                            "ground_truth": ground_hash, "versions": versions},
                                           sort_keys=True).encode()).hexdigest()
    return {"git": git, "python": platform.python_version(), "platform": platform.platform(),
            "dependencies": versions, "source_sha256": hashes, "ground_truth_sha256": ground_hash,
            "configuration": config, "comparison_fingerprint": fingerprint}


def new_result(planner: str, apps: list[str], settings, run_dir: Path, repeat_index: int = 1) -> dict:
    return {"schema_version": 2, "run_id": run_dir.name, "planner": planner,
            "model": settings.model if planner == "meta" else None, "date": utc_now(),
            "status": "running", "repeat_index": repeat_index,
            "requested_apps": apps, "planned_targets": len(apps) * 2,
            "metadata": evidence_metadata(settings, apps, planner),
            "rows": [target_row(app, mode) for app in apps for mode in ("buggy", "fixed")], "errors": []}


def target_row(app: str, mode: str) -> dict:
    return {"app": app, "mode": mode, "held_out": app in HELD_OUT, "status": "pending",
            "expected_bugs": [b["id"] for b in GROUND_TRUTH[app]] if mode == "buggy" else [],
            "found": [], "unexpected": [], "flaky": [], "warnings": [], "error": None,
            "planner_used": None, "fallback": None, "meta_complete": False,
            "experiment_outcomes": {}, "invariant_outcomes": {}, "applicable_invariants": 0,
            "applicable_experiments": 0, "execution_complete": False,
            "experiments": 0, "browser_runs": 0, "meta_calls": 0,
            "input_tokens": 0, "output_tokens": 0, "seconds": 0}


def refresh_totals(result: dict) -> None:
    rows = result["rows"]
    completed = [r for r in rows if r["status"] == "completed"]
    result["coverage"] = {"planned": result["planned_targets"], "completed": len(completed),
                          "errors": sum(r["status"] == "error" for r in rows),
                          "not_completed": result["planned_targets"] - len(completed),
                          "meta_complete_targets": sum(r.get("meta_complete", False) for r in completed),
                          "targets_with_applicable_checks": sum(r.get("applicable_invariants", 0) > 0 for r in completed),
                          "execution_complete_targets": sum(r.get("execution_complete", False) for r in completed)}
    for key in ("browser_runs", "meta_calls"):
        result[key] = sum(r.get(key, 0) for r in rows)
    result["tokens"] = {"input": sum(r.get("input_tokens", 0) for r in rows),
                        "output": sum(r.get("output_tokens", 0) for r in rows)}
    result["seconds"] = round(sum(r.get("seconds", 0) for r in rows), 1)
    for held, key in ((False, "dev_apps"), (True, "held_out_apps")):
        subset = [r for r in completed if r["held_out"] == held]
        selected = [a for a in result["requested_apps"] if (a in HELD_OUT) == held]
        result[key] = {"apps": selected, "found": sum(len(r["found"]) for r in subset),
                       "expected": sum(len(r["expected_bugs"]) for r in subset),
                       "planned_expected": sum(len(GROUND_TRUTH[a]) for a in selected),
                       "false_positives_on_fixed_builds": sum(len(r["unexpected"]) for r in subset if r["mode"] == "fixed"),
                       "fixed_builds_completed": sum(r["mode"] == "fixed" for r in subset),
                       "fixed_builds_with_coverage": sum(r["mode"] == "fixed" and r.get("applicable_invariants", 0) > 0 for r in subset),
                       "fixed_builds_planned": len(selected),
                       "unexpected_on_buggy_builds": sum(len(r["unexpected"]) for r in subset if r["mode"] == "buggy")}


def cell(value) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ").replace("\r", " ")


def to_markdown(result: dict) -> str:
    refresh_totals(result)
    coverage = result["coverage"]
    lines = ["# Evaluation run", "", f"Run: {result['run_id']}", f"Started: {result['date']}",
             f"Requested planner: {result['planner']}" + (f" ({result['model']})" if result.get("model") else ""),
             f"Status: {result['status']}",
             f"Completed targets: {coverage['completed']}/{coverage['planned']}; errors: {coverage['errors']}",
             f"Complete Meta targets: {coverage['meta_complete_targets']}/{coverage['planned']}",
             f"Targets with applicable checks: {coverage['targets_with_applicable_checks']}/{coverage['planned']}",
             f"Runtime source unchanged during run: {result.get('source_unchanged_during_run', 'not yet checked')}", "",
             "Counts below describe completed targets of the requested pipeline, including any explicitly labelled fallback.",
             "An incomplete or degraded run is not a complete live-model evaluation.", "",
             "| Set | Selected apps | Found / known bugs in completed targets | Planned known bugs | False alarms / fixed targets completed |",
             "|---|---|---|---|---|"]
    for title, key in (("Dev", "dev_apps"), ("Held out", "held_out_apps")):
        t = result[key]
        lines.append(f"| {title} | {', '.join(t['apps']) or '-'} | {t['found']}/{t['expected']} | "
                     f"{t['planned_expected']} | {t['false_positives_on_fixed_builds']} / "
                     f"{t['fixed_builds_completed']} of {t['fixed_builds_planned']} |")
    lines += ["", "| App | Build | State | Actual planner | Found | Missed | False alarms / unexpected | Notes |",
              "|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        missed = sorted(set(r["expected_bugs"]) - set(r["found"])) if r["status"] == "completed" else []
        notes = [r.get("error"), r.get("fallback"), *r.get("warnings", [])]
        lines.append("| " + " | ".join(cell(v) for v in (r["app"], r["mode"], r["status"],
                     r.get("planner_used") or "not completed", ", ".join(r["found"]) or "-",
                     (", ".join(missed) or "-") if r["status"] == "completed" else "not evaluated",
                     len(r["unexpected"]), "; ".join(n for n in notes if n) or "-")) + " |")
    lines += ["", "| App | Build | Experiment outcomes | Applicable experiments | Applicable invariant checks | Execution complete |",
              "|---|---|---|---|---|---|"]
    for row in result["rows"]:
        outcomes = ", ".join(f"{key}={count}" for key, count in sorted(row.get("experiment_outcomes", {}).items())) or "none"
        lines.append(f"| {cell(row['app'])} | {row['mode']} | {cell(outcomes)} | {row.get('applicable_experiments', 0)} | "
                     f"{row.get('applicable_invariants', 0)} | {row.get('execution_complete', False)} |")
    if result.get("source_changes_during_run"):
        lines += ["", "Runtime source changed during this attempt: " + ", ".join(result["source_changes_during_run"])]
    lines += ["", f"Browser runs: {result['browser_runs']}; recorded Meta calls: {result['meta_calls']}.",
              f"Reported usage tokens in/out: {result['tokens']['input']}/{result['tokens']['output']}.",
              "Missing usage and failed requests may not be included in token totals; these are not billing estimates.",
              f"Target processing time: {result['seconds']} s.", ""]
    if result.get("errors"):
        lines += ["Run errors:", *["- " + cell(e) for e in result["errors"]], ""]
    return "\n".join(lines)


def checkpoint(run_dir: Path, result: dict, secret: str | None = None) -> None:
    refresh_totals(result)
    safe = redact(result, secret)
    atomic_json(run_dir / "result.json", safe)
    # JSON is authoritative; Markdown is a derived convenience view.
    markdown = run_dir / "result.md"
    temporary = markdown.with_suffix(".md.tmp")
    temporary.write_text(to_markdown(safe), encoding="utf-8")
    os.replace(temporary, markdown)


def extract_row(report: dict, row: dict) -> None:
    confirmed = [cx for cx in report["counterexamples"] if cx["confirmation"]["confirmed"]]
    matched, unexpected = {}, []
    for cx in confirmed:
        bug = match(cx, GROUND_TRUTH[row["app"]]) if row["mode"] == "buggy" else None
        if bug:
            matched.setdefault(bug, cx["id"])
        else:
            unexpected.append({"id": cx["id"], "title": cx["title"], "signature": cx["signature"]})
    row.update(status="completed", hunt_id=report["id"], planner_used=report["planner"]["used"],
               fallback=report["planner"].get("fallback_reason"), found=sorted(matched), unexpected=unexpected,
               flaky=[u["title"] for u in report.get("unconfirmed", [])],
               minimized_steps={cx["id"]: len(cx["experiment"]["steps"]) for cx in confirmed},
               diagnosis_sources=dict(Counter(cx.get("diagnosis", {}).get("source", "unknown") for cx in confirmed)),
               rounds_completed=len(report["rounds"]))
    for key in ("experiments", "browser_runs", "meta_calls", "input_tokens", "output_tokens"):
        row[key] = report["stats"].get(key, 0) or 0
    hypotheses = [h for round_ in report.get("rounds", []) for h in round_.get("hypotheses", [])]
    outcomes = Counter(h.get("result", {}).get("status", "missing") for h in hypotheses)
    invariants = Counter(i.get("status", "missing") for h in hypotheses
                         for i in h.get("result", {}).get("invariants", []))
    row["experiment_outcomes"] = dict(outcomes)
    row["invariant_outcomes"] = dict(invariants)
    row["applicable_experiments"] = outcomes["passed"] + outcomes["failed"]
    row["applicable_invariants"] = invariants["pass"] + invariants["fail"]
    row["execution_complete"] = (row["applicable_experiments"] > 0 and row["applicable_invariants"] > 0
                                  and not any(n for status, n in outcomes.items()
                                              if status not in {"passed", "failed", "inapplicable"}))
    if not row["applicable_experiments"] or not row["applicable_invariants"]:
        row["warnings"].append("No applicable invariant coverage; no clean-build verdict is available.")
    if any(n for status, n in outcomes.items() if status not in {"passed", "failed", "inapplicable"}):
        row["warnings"].append("Some experiments could not execute; findings are retained but this target is incomplete.")
    degraded_warning = any("follow-up round skipped" in w.lower() or "diagnosis fell back" in w.lower()
                           for w in row["warnings"])
    row["meta_attempt_statuses"] = dict(Counter(c.get("status", "legacy_response") for c in report.get("meta_calls", [])))
    row["reported_models"] = sorted({str(c.get("model")) for c in report.get("meta_calls", []) if c.get("model")})
    row["meta_complete"] = (row["planner_used"] == "meta" and not row["fallback"] and not degraded_warning
                            and row["execution_complete"]
                            and all(cx.get("diagnosis", {}).get("source") == "meta" for cx in confirmed))


async def run_eval(base: str, planner: str, apps: list[str], *, settings=None, run_dir: Path,
                   result: dict | None = None, hunt_factory: Callable = Hunt) -> dict:
    settings = settings or get_settings()
    settings = replace(settings, artifacts=run_dir / "artifacts")
    result = result or new_result(planner, apps, settings, run_dir)
    result["rows"] = [target_row(app, mode) for app in apps for mode in ("buggy", "fixed")]
    checkpoint(run_dir, result, settings.api_key)
    try:
        for row in result["rows"]:
            row["status"] = "running"
            started = time.monotonic()
            checkpoint(run_dir, result, settings.api_key)
            def emit(kind, message, data=None):
                if kind == "warning":
                    row["warnings"].append(redact(str(message), settings.api_key))
            try:
                report = await hunt_factory(f"{base}/demo/{row['app']}.html?mode={row['mode']}",
                                            planner=planner, settings=settings, emit=emit).run()
                extract_row(report, row)
                # Hunt writes a full report. Redact any reflected credential in errors before publication.
                report_path = settings.artifacts / report["id"] / "report.json"
                if report_path.exists():
                    atomic_json(report_path, redact(report, settings.api_key))
            except Exception as exc:
                row.update(status="error", error=redact(f"{type(exc).__name__}: {exc}", settings.api_key))
            finally:
                row["seconds"] = round(time.monotonic() - started, 1)
                checkpoint(run_dir, result, settings.api_key)
            print(f"{planner:9} {row['app']:10} {row['mode']:5} {row['status']:9} "
                  f"actual={row['planner_used']} found={row['found']}", flush=True)
        if any(r["status"] != "completed" for r in result["rows"]):
            result["status"] = "incomplete"
        elif not all(r["execution_complete"] for r in result["rows"]):
            result["status"] = "degraded"
        elif planner == "meta" and not all(r["meta_complete"] for r in result["rows"]):
            result["status"] = "degraded"
        else:
            result["status"] = "completed"
    except BaseException as exc:
        result["status"] = "interrupted"
        result["errors"].append(redact(type(exc).__name__, settings.api_key))
        raise
    finally:
        final_source_check(result)
        result["finished_at"] = utc_now()
        checkpoint(run_dir, result, settings.api_key)
    return result


def parse_apps(value: str) -> list[str]:
    apps = [a.strip() for a in value.split(",") if a.strip()]
    if not apps or len(set(apps)) != len(apps) or any(a not in GROUND_TRUTH for a in apps):
        raise argparse.ArgumentTypeError("Choose distinct known apps: " + ",".join(GROUND_TRUTH))
    return apps


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planner", choices=["heuristic", "meta"], default="heuristic")
    parser.add_argument("--apps", type=parse_apps, default=list(GROUND_TRUTH))
    parser.add_argument("--repeat", type=positive_int, default=1)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "eval" / "runs")
    args = parser.parse_args()
    settings = get_settings()
    outcome = 0
    for attempt in range(1, args.repeat + 1):
        run_dir = unique_directory(args.output_dir, args.planner)
        result = new_result(args.planner, args.apps, settings, run_dir, attempt)
        checkpoint(run_dir, result, settings.api_key)
        server = None
        try:
            if args.planner == "meta" and not settings.meta_configured:
                key_name = "META_OPEN_API_KEY" if settings.backend == "open_weights" else "MODEL_API_KEY"
                raise RuntimeError(f"{key_name} is not set (put it into .env)")
            port = _free_port()
            server = subprocess.Popen([sys.executable, "-m", "uvicorn", "faultline.server:app", "--host", "127.0.0.1",
                                       "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=os.environ.copy())
            _wait(f"http://127.0.0.1:{port}/api/config")
            result = asyncio.run(run_eval(f"http://127.0.0.1:{port}", args.planner, args.apps,
                                          settings=settings, run_dir=run_dir, result=result))
        except KeyboardInterrupt:
            result["status"] = "interrupted"
            outcome = 130
        except Exception as exc:
            result["status"] = "error"
            result["errors"].append(redact(f"{type(exc).__name__}: {exc}", settings.api_key))
            outcome = 2
        finally:
            stop_server(server)
            if "source_unchanged_during_run" not in result:
                final_source_check(result)
            result["finished_at"] = utc_now()
            checkpoint(run_dir, result, settings.api_key)
            print(f"Saved {run_dir / 'result.json'}")
        if result["status"] != "completed":
            outcome = outcome or 2
        if outcome == 130:
            break
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())
