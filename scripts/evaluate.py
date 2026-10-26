"""Evaluate Faultline on the bundled demo apps (buggy and fixed builds).

Usage:
    python scripts/evaluate.py --planner heuristic
    python scripts/evaluate.py --planner meta          # needs MODEL_API_KEY

Ground truth was written together with the demo apps, before any planner was run.
`composer` and `newsletter` are held out: they were never used while writing
prompts or heuristics. Results are reported as counts (x/y), not accuracies.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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


async def run_eval(base: str, planner: str, apps: list[str]) -> dict:
    settings = get_settings()
    rows = []
    for app in apps:
        for mode in ("buggy", "fixed"):
            url = f"{base}/demo/{app}.html?mode={mode}"
            started = time.monotonic()
            report = await Hunt(url, planner=planner, settings=settings).run()
            confirmed = [cx for cx in report["counterexamples"] if cx["confirmation"]["confirmed"]]
            matched = {}
            unexpected = []
            for cx in confirmed:
                bug = match(cx, GROUND_TRUTH[app]) if mode == "buggy" else None
                if bug:
                    matched.setdefault(bug, cx["id"])
                else:
                    unexpected.append({"id": cx["id"], "title": cx["title"], "signature": cx["signature"]})
            rows.append({
                "app": app, "mode": mode, "held_out": app in HELD_OUT, "hunt_id": report["id"],
                "planner_used": report["planner"]["used"], "fallback": report["planner"]["fallback_reason"],
                "expected_bugs": [b["id"] for b in GROUND_TRUTH[app]] if mode == "buggy" else [],
                "found": sorted(matched), "unexpected": unexpected,
                "flaky": [cx["id"] for cx in report["counterexamples"] if not cx["confirmation"]["confirmed"]],
                "minimized_steps": {cx["id"]: len(cx["experiment"]["steps"]) for cx in confirmed},
                "experiments": report["stats"]["experiments"], "browser_runs": report["stats"]["browser_runs"],
                "meta_calls": report["stats"]["meta_calls"], "input_tokens": report["stats"]["input_tokens"],
                "output_tokens": report["stats"]["output_tokens"],
                "seconds": round(time.monotonic() - started, 1),
            })
            print(f"{planner:9} {app:10} {mode:5} found={rows[-1]['found']} unexpected={len(unexpected)} "
                  f"runs={rows[-1]['browser_runs']} {rows[-1]['seconds']}s", flush=True)

    def tally(held: bool) -> dict:
        subset = [r for r in rows if r["held_out"] == held]
        expected = sum(len(r["expected_bugs"]) for r in subset)
        found = sum(len(r["found"]) for r in subset)
        return {"found": found, "expected": expected,
                "false_positives_on_fixed_builds": sum(len(r["unexpected"]) for r in subset if r["mode"] == "fixed"),
                "unexpected_on_buggy_builds": sum(len(r["unexpected"]) for r in subset if r["mode"] == "buggy")}

    return {"planner": planner, "model": settings.model if planner != "heuristic" else None,
            "date": datetime.now(timezone.utc).isoformat(), "dev_apps": tally(False), "held_out_apps": tally(True),
            "browser_runs": sum(r["browser_runs"] for r in rows),
            "meta_calls": sum(r["meta_calls"] for r in rows),
            "tokens": {"input": sum(r["input_tokens"] for r in rows), "output": sum(r["output_tokens"] for r in rows)},
            "seconds": round(sum(r["seconds"] for r in rows), 1), "rows": rows}


def to_markdown(result: dict) -> str:
    d, h = result["dev_apps"], result["held_out_apps"]
    lines = [f"### Planner: {result['planner']}" + (f" ({result['model']})" if result["model"] else ""),
             f"Run: {result['date']}", "",
             "| Set | Bugs found | False positives on fixed builds | Unexpected findings on buggy builds |",
             "|---|---|---|---|",
             f"| Dev apps (profile, search, checkout, settings) | {d['found']}/{d['expected']} | "
             f"{d['false_positives_on_fixed_builds']} | {d['unexpected_on_buggy_builds']} |",
             f"| Held-out apps (composer, newsletter) | {h['found']}/{h['expected']} | "
             f"{h['false_positives_on_fixed_builds']} | {h['unexpected_on_buggy_builds']} |", "",
             f"Browser runs: {result['browser_runs']} · Meta calls: {result['meta_calls']} · "
             f"Tokens in/out: {result['tokens']['input']}/{result['tokens']['output']} · Wall time: {result['seconds']} s", "",
             "| App | Build | Found | Missed | Unexpected | Browser runs |", "|---|---|---|---|---|---|"]
    for r in result["rows"]:
        missed = sorted(set(r["expected_bugs"]) - set(r["found"]))
        lines.append(f"| {r['app']}{' (held-out)' if r['held_out'] else ''} | {r['mode']} | "
                     f"{', '.join(r['found']) or '-'} | {', '.join(missed) or '-'} | "
                     f"{', '.join(u['title'] for u in r['unexpected']) or '-'} | {r['browser_runs']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--planner", choices=["heuristic", "meta"], default="heuristic")
    parser.add_argument("--apps", default=",".join(GROUND_TRUTH))
    args = parser.parse_args()
    if args.planner == "meta" and not get_settings().meta_configured:
        sys.exit("MODEL_API_KEY is not set (put it into .env)")
    port = _free_port()
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "faultline.server:app", "--host", "127.0.0.1",
                               "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=os.environ.copy())
    try:
        _wait(f"http://127.0.0.1:{port}/api/config")
        result = asyncio.run(run_eval(f"http://127.0.0.1:{port}", args.planner, args.apps.split(",")))
    finally:
        server.terminate()
    out = ROOT / "eval"
    out.mkdir(exist_ok=True)
    (out / f"results-{args.planner}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out / f"results-{args.planner}.md").write_text(to_markdown(result), encoding="utf-8")
    print(to_markdown(result))


if __name__ == "__main__":
    main()
