# Release notes

## 0.4.0

- **Strict live Meta mode.** The UI's Live Muse API option and CLI `--require-live` stop on model errors,
  rejected initial plans and failed diagnoses rather than substituting rules or explanation templates.
- **API-call evidence.** Network and injected test transports are distinguished, with UTC call timestamps,
  endpoint host, response model when actually provided, timings, HTTP status and token counts.
  The UI exposes the record and a report download; failed strict runs retain partial evidence.
- **Windows recording setup.** `scripts/Start-LiveDemo.ps1` uses an existing local key or hidden input,
  selects the hosted Meta endpoint and restores its process environment after the server stops.
  `docs/LIVE_DEMO.md` explains how to record a fresh three-minute live run.
- The original YouTube demo and recorded-plan results remain labelled as replay. This release adds
  and tests the live-mode controls; it does not claim a successful real Meta API run from the build environment.

## 0.3.0

- **Recorded Muse plan in the UI.** On the held-out demo apps the UI can replay the plan Muse wrote in the Meta
  playground, so anyone can see the Muse-planned path without an API key. The run is labelled as a replay, names the
  recording file and date, and calls no model.
- **Spark or Wonder per hunt.** With a Meta key, the UI offers a switch between `muse-spark-1.3` and
  `muse-wonder-1.0`; the API only accepts those two hosted Muse models.
- **Same-origin redirects work again.** Page navigations follow same-origin redirect chains (for example `/` to
  `/app`, or a form's post-redirect-get) and still block any hop to another origin before it is contacted. Signed-in
  runs keep blocking all redirects.
- **Signed-in pages stay private by default.** With saved login state, the Meta model only sees the signed-in pages
  after the separate `--send-signed-in-pages` opt-in; otherwise the rules-only planner is used and the report says so.
- **Model identity.** A dated snapshot of the requested model (for example `muse-spark-1.3-2026-10-20`) is accepted;
  an answer from another model fails after one call instead of three billable retries.
- **Robust fallback.** Invalid model settings fall back to the rules-only planner with a clear reason instead of
  ending the hunt.
- **Bounded password check.** The pre-typing password check now uses the action timeout instead of Playwright's
  30-second default, which slowed down minimization.
- Git history restored (0.2.0 had been prepared from a copy without it), documentation rewritten for reviewers,
  `FAULTLINE_UI_HOSTS` documented, 15 new regression tests.

## 0.2.0

- Every evaluation and replay attempt is preserved in its own directory with checkpoints, separating the requested
  model, the actual planner, errors and fallbacks. Summaries keep incompatible configurations apart.
- CI exit codes, JUnit output and a manually triggered GitHub Actions example.
- Saved Playwright login state for authenticated local apps, scoped to the target and kept out of every output.
- Review-only fix proposals from explicitly selected source files after consent. Diffs are validated against the
  selected text and never written or executed.
- Optional Meta open-weights endpoint adapter with separate credentials and call accounting.
- Notebook UI: hunt phases, expected and observed evidence, larger screenshots, the exact exported test, distinct
  re-test outcomes and an explicit no-coverage state.
- Protection against cross-origin navigation, unrecognised API hosts and password fields that change after
  discovery. Exported specs refuse password typing and block service workers.
- Compatibility probes on unmodified TodoMVC and 2048 (see `docs/EXTERNAL_VALIDATION.md`).

Bundled demo files, ground truth, planner prompts and rules, and the recorded plans are unchanged since 0.1, so the
results in `eval/` stay comparable. Each new evaluation attempt records source fingerprints.

## 0.1.0

The hypothesis-driven hunt: discovery, the closed experiment vocabulary and validator, Muse planning with a
follow-up round, fault-injecting Playwright executor, invariants, minimizer and fault ablation, three-run
confirmation, Muse diagnosis, Playwright Test export, the web UI and six demo apps with buggy and fixed builds.

## Local check

```bash
pip install -e ".[dev]"
python -m playwright install chromium
pytest -q
python scripts/replay_recorded.py
python scripts/evaluate.py --planner heuristic
python -m faultline serve
```

