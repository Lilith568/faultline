"""Command line: `faultline serve`, `faultline hunt URL`, `faultline replay repro.json`."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


def _print_report(report: dict) -> None:
    planner = report["planner"]
    print(f"\nPlanner: {planner['used']}" + (f" ({planner['model']})" if planner["used"] == "meta" else "")
          + (f"  [{planner['fallback_reason']}]" if planner["fallback_reason"] else ""))
    for rnd in report["rounds"]:
        for hyp in rnd["hypotheses"]:
            print(f"  round {rnd['round']}  {hyp['result']['status']:12}  {hyp['claim']}")
        for rej in rnd["rejected"]:
            print(f"  round {rnd['round']}  rejected      {rej['claim'] or rej['id']}: {rej['reason']}")
    for item in report.get("unconfirmed", []):
        conf = item["confirmation"]
        print(f"  not reproducible every time ({conf['failures']}/{conf['runs']}), not reported: {item['title']}")
    print(f"\n{len(report['counterexamples'])} verified failure(s):")
    for cx in report["counterexamples"]:
        conf = cx["confirmation"]
        print(f"\n  [{cx['id']}] {cx['title']}  (reproduced {conf['failures']}/{conf['runs']})")
        for i, step in enumerate(cx["text"]["steps"], 1):
            print(f"      {i}. {step}")
        for p in cx["text"]["perturbations"]:
            print(f"      network: {p}")
        print(f"      expected {cx['failure']['expected']!r}, got {cx['failure']['actual']!r}")
        print(f"      {cx['attribution']}")
        print(f"      test: {cx['spec_file']}")
    stats = report["stats"]
    print(f"\n{stats['experiments']} experiments, {stats['browser_runs']} browser runs, "
          f"{stats['meta_calls']} Meta calls, {stats['duration_s']} s. Report: artifacts/{report['id']}/report.json")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="faultline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="start the web UI and the bundled demo apps")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--host", default="127.0.0.1")
    hunt = sub.add_parser("hunt", help="hunt for counterexamples on a local URL")
    hunt.add_argument("url")
    hunt.add_argument("--goal", default="")
    hunt.add_argument("--planner", choices=["auto", "meta", "heuristic"], default="auto")
    hunt.add_argument("--rounds", type=int, default=2)
    hunt.add_argument("--plan", help="replay a recorded model plan (JSON) instead of calling the API")
    hunt.add_argument("--send-source", action="store_true",
                      help="let Muse read the page's inline scripts for a code-level diagnosis")
    hunt.add_argument("--ci", action="store_true",
                      help="exit 1 for confirmed bugs, 2 for incomplete checks, otherwise 0")
    hunt.add_argument("--junit", metavar="PATH", help="write a JUnit XML report (also on run errors)")
    hunt.add_argument("--send-signed-in-pages", action="store_true",
                      help="with --storage-state: also let the Meta model see the signed-in pages (inventory, "
                           "screenshots). Off by default; without it signed-in hunts use the rules-only planner")
    hunt.add_argument("--storage-state", metavar="PATH",
                      help="load saved Playwright cookies/localStorage for the target only")
    replay = sub.add_parser("replay", help="re-run a saved repro.json, e.g. against the fixed build")
    replay.add_argument("repro")
    replay.add_argument("--url")
    replay.add_argument("--storage-state", metavar="PATH",
                        help="load saved Playwright cookies/localStorage for the target only")
    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn
        print(f"Faultline running at http://{args.host}:{args.port}  (demo apps under /demo/...)")
        uvicorn.run("faultline.server:app", host=args.host, port=args.port, log_level="warning")
    elif args.command == "hunt":
        from .hunt import Hunt

        def emit(kind: str, message: str, data=None) -> None:
            if kind in ("phase", "plan", "counterexample", "warning", "error"):
                print(f"- {message}", flush=True)

        from .reports import ci_exit_code, ci_issues, write_error_junit, write_junit
        try:
            recorded = json.loads(Path(args.plan).read_text(encoding="utf-8")) if args.plan else None
            report = asyncio.run(Hunt(args.url, goal=args.goal, planner=args.planner, rounds=args.rounds, emit=emit,
                                      recorded_plan=recorded, include_source=args.send_source,
                                      storage_state=args.storage_state,
                                      share_signed_in_pages=args.send_signed_in_pages).run())
            _print_report(report)
            if args.junit:
                write_junit(report, args.junit)
            if args.ci:
                for issue in ci_issues(report):
                    print(f"CI incomplete: {issue}", file=sys.stderr)
                raise SystemExit(ci_exit_code(report))
        except (Exception, KeyboardInterrupt) as exc:
            message = "Hunt interrupted" if isinstance(exc, KeyboardInterrupt) else f"{type(exc).__name__}: {exc}"
            print(message, file=sys.stderr)
            if args.junit:
                try:
                    write_error_junit(args.junit, message)
                except OSError:
                    print("Could not write the JUnit report", file=sys.stderr)
            raise SystemExit(2) from None
    elif args.command == "replay":
        from .hunt import replay as replay_fn
        repro = json.loads(Path(args.repro).read_text(encoding="utf-8"))
        result = asyncio.run(replay_fn(repro, args.url, storage_state=args.storage_state))
        print(json.dumps({k: result[k] for k in ("status", "error", "invariants", "duration_ms")}, indent=2))
        sys.exit(0 if result["status"] == "passed" else 1 if result["status"] == "failed" else 2)


if __name__ == "__main__":
    main()
