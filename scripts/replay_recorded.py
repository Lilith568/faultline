"""Replay recorded Muse plans (eval/recorded/*.json) against the buggy and fixed builds.

Usage:
    python scripts/replay_recorded.py

The plans were produced by a Meta model; this script needs no API key. It writes
eval/results-recorded.json and eval/results-recorded.md so the README numbers can be checked.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate import GROUND_TRUTH, _free_port, _wait, match  # noqa: E402
from faultline.config import get_settings  # noqa: E402
from faultline.hunt import Hunt  # noqa: E402


async def run(base: str) -> dict:
    settings = get_settings()
    rows = []
    for path in sorted((ROOT / "eval" / "recorded").glob("*.json")):
        recorded = json.loads(path.read_text(encoding="utf-8"))
        app = path.name.split("-", 1)[0]
        for mode in ("buggy", "fixed"):
            report = await Hunt(f"{base}/demo/{app}.html?mode={mode}", planner="heuristic", settings=settings,
                                recorded_plan=recorded).run()
            found, unexpected = {}, []
            for cx in report["counterexamples"]:
                bug = match(cx, GROUND_TRUTH[app]) if mode == "buggy" else None
                if bug:
                    found.setdefault(bug, cx["id"])
                else:
                    unexpected.append(cx["title"])
            rows.append({
                "app": app, "mode": mode, "plan": f"eval/recorded/{path.name}",
                "model": recorded["provenance"]["model"], "recorded_at": recorded["provenance"]["when"],
                "hypotheses": len(report["rounds"][0]["hypotheses"]),
                "rejected_by_validator": len(report["rounds"][0]["rejected"]),
                "results": {h["claim"]: h["result"]["status"] for h in report["rounds"][0]["hypotheses"]},
                "expected_bugs": [b["id"] for b in GROUND_TRUTH[app]] if mode == "buggy" else [],
                "found": sorted(found), "unexpected": unexpected,
                "unconfirmed": [u["title"] for u in report.get("unconfirmed", [])],
                "browser_runs": report["stats"]["browser_runs"],
            })
            print(f"{app:10} {mode:5} found={rows[-1]['found']} unexpected={unexpected}", flush=True)
    return {"date": datetime.now(timezone.utc).isoformat(), "rows": rows}


def to_markdown(result: dict) -> str:
    lines = ["### Recorded Muse plans replayed through Faultline", f"Run: {result['date']}", "",
             "| App | Build | Plan | Hypotheses (rejected) | Known bugs verified | Missed | False alarms or unexpected |",
             "|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        missed = sorted(set(r["expected_bugs"]) - set(r["found"]))
        lines.append(f"| {r['app']} | {r['mode']} | {r['model']}, {r['recorded_at']} | {r['hypotheses']} "
                     f"({r['rejected_by_validator']}) | {', '.join(r['found']) or '-'} | {', '.join(missed) or '-'} | "
                     f"{', '.join(r['unexpected']) or '0'} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    port = _free_port()
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "faultline.server:app", "--host", "127.0.0.1",
                               "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=os.environ.copy())
    try:
        _wait(f"http://127.0.0.1:{port}/api/config")
        result = asyncio.run(run(f"http://127.0.0.1:{port}"))
    finally:
        server.terminate()
    (ROOT / "eval" / "results-recorded.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / "eval" / "results-recorded.md").write_text(to_markdown(result), encoding="utf-8")
    print(to_markdown(result))


if __name__ == "__main__":
    main()
