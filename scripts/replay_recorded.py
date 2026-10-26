"""Replay recorded Muse plans without an API key, preserving each replay separately.

This verifies saved plans; it is not a live Meta API evaluation. The original
results-recorded.json/.md files and superseded plans are never overwritten.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate import (GROUND_TRUTH, _free_port, _wait, checkpoint, final_source_check, new_result, redact,
                      run_eval, stop_server, unique_directory, utc_now)  # noqa: E402
from faultline.config import get_settings  # noqa: E402
from faultline.hunt import Hunt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "eval" / "runs")
    args = parser.parse_args()
    records, provenance = {}, {}
    for path in sorted((ROOT / "eval" / "recorded").glob("*.json")):
        app = path.name.split("-", 1)[0]
        if app not in GROUND_TRUTH or app in records:
            parser.error("Recorded plan must identify one distinct known app: " + path.name)
        records[app] = json.loads(path.read_text(encoding="utf-8"))
        provenance[app] = {"path": path.relative_to(ROOT).as_posix(),
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "provenance": records[app].get("provenance", {})}
    if not records:
        parser.error("No recorded plans were found")
    settings = get_settings()
    run_dir = unique_directory(args.output_dir, "recorded")
    result = new_result("recorded", list(records), settings, run_dir)
    result["recorded_plans"] = provenance
    result["metadata"]["configuration"]["recorded_models"] = sorted({
        str(r.get("provenance", {}).get("model", "unknown")) for r in records.values()})
    result["metadata"]["comparison_fingerprint"] = hashlib.sha256(json.dumps({
        "base": result["metadata"]["comparison_fingerprint"], "recorded": provenance}, sort_keys=True).encode()).hexdigest()
    checkpoint(run_dir, result, settings.api_key)

    def factory(url, **kwargs):
        app = Path(urlsplit(url).path).stem
        kwargs["planner"] = "heuristic"
        return Hunt(url, recorded_plan=records[app], **kwargs)

    server = None
    try:
        port = _free_port()
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "faultline.server:app", "--host", "127.0.0.1",
                                   "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=os.environ.copy())
        _wait(f"http://127.0.0.1:{port}/api/config")
        asyncio.run(run_eval(f"http://127.0.0.1:{port}", "recorded", list(records), settings=settings,
                             run_dir=run_dir, result=result, hunt_factory=factory))
    except KeyboardInterrupt:
        result["status"] = "interrupted"
    except Exception as exc:
        result["status"] = "error"
        result["errors"].append(redact(f"{type(exc).__name__}: {exc}", settings.api_key))
    finally:
        stop_server(server)
        if "source_unchanged_during_run" not in result:
            final_source_check(result)
        result["finished_at"] = utc_now()
        checkpoint(run_dir, result, settings.api_key)
        print(f"Saved {run_dir / 'result.json'}")
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
