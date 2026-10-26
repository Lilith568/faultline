# Handoff for Muse Wonder

You are reviewing Faultline, a Meta-model-guided browser experiment tool, for the Meta Global AI Developer Hackathon Indie track, Push the Frontier. Respond to the owner in German. Keep code, comments and repository text in English. Optimize for credible impact, meaningful Meta use, engineering and a working demonstration. Do not promise a prize or inflate the quality score.

## Read first

- `README.md`, `docs/EVALUATION.md`, `docs/SUBMISSION.md`
- `docs/RELEASE_NOTES.md`, `docs/RULES_REVIEW.md`, `docs/QUALITY_REVIEW.md`
- `eval/verification/release-checks.json` and its linked test/evaluation evidence
- `docs/EXTERNAL_VALIDATION.md`, `docs/CI.md`, `docs/PATCHES.md`, `docs/MODELS.md`

## Current architecture

`discover.py` inventories controls and requests. `planners.py` asks the selected Meta model for hypotheses and follow-ups. `vocab.py` validates the closed experiment vocabulary and grounds expected values in synthetic input. `executor.py` runs isolated browser contexts with delayed/failed requests and evaluates deterministic invariants. `minimize.py` reduces failures and ablates faults. `hunt.py` confirms, diagnoses and exports. `export.py` writes a deterministic Playwright spec and repro JSON. The UI is the single no-build file `faultline/static/index.html`.

New work in this revision:

- Evaluation attempts and summaries have unique directories, incremental checkpoints and separate actual/planned model provenance. Errors, fallbacks and partial attempts stay visible.
- CI exits distinguish verified failures, meaningful completion and inconclusive execution; JUnit reports are available.
- CLI hunt and replay accept explicitly supplied Playwright storage state; discovery within a hunt uses it too. State is scoped and never embedded in model payloads or exports. Authenticated transport intentionally blocks redirects, foreign origins and WebSockets; see limitations.
- Review-only source patches require explicit selected files and separate consent. File paths, sizes, possible credentials and unified diff hunks are checked. No automatic source discovery, patch application, code execution or claim of a verified fix.
- A Meta open-weights compatible HTTP adapter exists with provider/model restrictions and separate credentials. Mock validation is not live deployment evidence.
- The notebook UI has event-driven phases, real generated-test previews, larger evidence screenshots, clear replay outcomes, reduced-motion handling and narrow-screen support.

## Evidence boundaries

Historical rules/recorded-plan measurements remain in `eval/results-*`; use the raw files as the authority. New integration runs live in `eval/runs/`. Recorded Muse plans are replayed without an API call. Do not call those new generations, independent model repetitions, or live API measurements.

Upstream probes used unmodified TodoMVC and 2048. They establish limited compatibility only: the former exercised an auxiliary request, and the latter had no applicable experiment. No real upstream bug has been established. Do not merge these probes into the demo accuracy table.

No real Meta key or live open-weights service was available for this revision. Patch quality, genuine follow-up behavior, latency, usage and real-world detection therefore still need live evidence. The owner plans to run the live evaluation locally; never request the key in chat.

The source snapshot was recovered from the owner's Drive folder. It did not include the original `.git` history. Do not fabricate commits, dates or author attribution. Apply this revision to the original repository while preserving its history when available.

## Priorities for your next review

1. Read `docs/RULES_REVIEW.md` and the actual submission form. The owner supplied the participant Guide after the public rules were checked. It requires a public repository and a three-minute video, and specifies Agentic and Open Weights awards. Resolve the Guide's kickoff/building-period date ambiguity and bonus stacking with the organizer before claiming eligibility. Preserve actual commit dates.
2. Run `python scripts/evaluate.py --planner meta --repeat 3` with the owner's local key, then `python scripts/summarize_eval.py`. Decide repetitions in advance, preserve every attempt, inspect model/round/diagnosis fallbacks and report worse results honestly. Use Muse Wonder as a separately measured configuration if comparing it to Spark.
3. Find a meaningful network-backed upstream target. Pin its revision and license. Write independent behavioral expectations before running a planner. Use a disposable local database and synthetic user. Demonstrate one independently reviewed defect, an exported regression test that fails, and the same test passing after a human-reviewed fix. Do not introduce an artificial defect and call it an upstream discovery.
4. Review the new features for correctness and usability. In particular, exercise authenticated multi-page apps within the documented restrictions, an actual patch proposal, interrupted evaluations and UI replay errors. Improve concrete failures instead of adding speculative features.
5. Run the open-weights path only if it helps an officially confirmed prize or a useful deployment case. Record the real checkpoint/deployment provenance. An endpoint alias alone proves nothing about the weights loaded.
6. Record an honest demo. Show Meta planning, browser verification, the minimal reproducer, exported test and fixed-build replay. Clearly label any replay. The video must not imply that Faultline applied a fix itself.

## Competition focus

The supplied Guide's amounts and criteria are recorded in `eval/participant-guide-review.json`.
Prioritize the main Indie rubric and the Agentic Use-Case category: demonstrate a real hypothesis, verified
feedback, useful follow-up decision and a reproducible outcome. The Open Weights category additionally needs
an actual eligible checkpoint-backed deployment and verification; the adapter alone is insufficient.
For Baseten, use the Guide's exact hackathon ID `meta-models/muse-spark-open-1026`.

The Viral category requires an X demo post and its link submitted through the platform, with engagement counted
until November 8 EOD; the timezone needs confirmation. Community voting opens on November 9 and is limited
to one vote per verified account. Prepare publication assets, but obtain the owner's instruction before posting.
Do not divert the developer-tool project into the Creative category just by selecting Muse Wonder: that award
also requires a compelling creative project. Do not add prize amounts together as guaranteed earnings;
stacking remains unconfirmed.

## Preserve these constraints

- Existing `faultline/demo/` bytes, element order, `data-testid` values and buggy/fixed markers stay unchanged.
- Existing ground truth, held-out designations and recorded plans are not rewritten. New held-out targets and ground truth must be frozen before any planner sees them; never mention them in rules or prompts.
- Preserve all evaluation attempts. No benchmark number is promoted to documentation without its raw evidence file.
- Runtime AI remains Meta only. Development assistance from Claude and ChatGPT is disclosed in `docs/PROVENANCE.md`.
- Local targets by default; validate model plans, refuse password typing, never execute model-generated patches.
- Keep every existing UI ID/data binding functional. Keep the grid, ink blue, red recording pen, Archivo and Source Serif 4 design.
- Add meaningful regression tests for changed behavior. Keep the baseline suite passing.
- From November 3, follow the owner's feature freeze: fixes, validation, demo and submission only.

## Work and delivery

Give the owner a short plan for each next task. Existing authorization covers the separately delivered revision, not automatic publishing, social posting or submitting to the competition. Deliver complete changed files, verification commands, a truthful change log and a commit message. Save future revisions separately in the owner's Faultline Drive folder unless instructed otherwise.

Suggested local verification:

```bash
pip install -e ".[dev]"
python -m playwright install chromium
pytest -q
python scripts/replay_recorded.py
python scripts/evaluate.py --planner heuristic
python -m faultline serve
```

Open `http://127.0.0.1:8000`, choose a demo, run a hunt and replay a finding against its fixed build. Live model claims require the additional real API evaluation above.
