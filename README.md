# Faultline

**Faultline breaks your web app on purpose, then hands you the failing test.**

Built for the Meta Global AI Developer Hackathon 2026, Indie track, problem statement *Push the Frontier*.

Your happy-path tests pass. Then a real user on a slow train types into a form while the profile request is still in flight,
and the late response silently replaces their text. Or a search shows results for "ca" although they typed "cat". Or a
double-click places two orders. These bugs depend on timing, so they rarely show up on `localhost` and almost never in
a test suite.

Faultline hunts for exactly these failures in an app you are building:

1. **Explore.** It opens your local app in Playwright, inventories supported, uniquely addressable controls
   (including hidden dialogs), records observed same-origin fetch/XHR requests, and tries bounded "opener" actions.
2. **Hypothesize (Muse).** A Meta Muse model reads that inventory and your goal ("users must never lose what they typed")
   and proposes competing, falsifiable hypotheses, each with one experiment: steps, a network fault to inject
   (hold the 1st `GET /api/profile` for 1.5 s, answer the next `POST` with HTTP 500) and invariants to check.
3. **Verify (Playwright).** Every plan passes a strict validator, then runs in a fresh browser with the injected faults.
   Playwright, not the model, decides whether an invariant failed.
4. **Follow up (Muse).** Muse sees the verified results and designs follow-up experiments: repairing experiments that
   did not apply, probing parts of the page that are still untested.
5. **Minimize, confirm, attribute.** Failing experiments are shrunk step by step (without ever removing the step an
   invariant depends on), re-run three times, and each injected fault is ablated to show whether the bug is
   timing-dependent, an error-path bug or deterministic.
6. **Diagnose and export (Muse).** Muse explains the root cause from the evidence: steps, request timeline, a screenshot
   of the failing state and, only if you tick the box, the page's own inline scripts. Faultline exports a ready-to-run
   **Playwright Test spec** that fails while the bug exists and passes once it is fixed. One click re-tests the exact
   counterexample against your fixed build.

```
 your app ──► discover ──► Muse: hypotheses ──► validator ──► Playwright + injected faults ──► invariants
                               ▲                                                                  │
                               └────────── Muse: follow-up round ◄──── verified results ◄──────────┘
                                                                                                  │
               regression test (.spec.ts) ◄── Muse: diagnosis ◄── 3× confirmation ◄── minimizer ◄─┘
```

## This development revision

Faultline now supports [CI gates and JUnit reports](docs/CI.md), explicitly supplied
Playwright login state, [review-only source patches](docs/PATCHES.md), and an optional
[Meta open-weights endpoint](docs/MODELS.md). The notebook UI shows the actual hunt
phase, the generated test and distinct fixed-build replay outcomes. New evaluation
attempts are checkpointed in separate directories and summarized without hiding errors
or fallback planners.

See [release notes](docs/RELEASE_NOTES.md), [validation and readiness](docs/QUALITY_REVIEW.md),
[upstream compatibility probes](docs/EXTERNAL_VALIDATION.md), and the
[Muse Wonder handoff](docs/MUSE_WONDER_HANDOFF.md). Live Meta and open-weights runs still
need the owner's configured endpoint; mocked tests and saved-plan replays are labelled
as such. No real upstream bug has yet been established by the compatibility probes.

## Where Meta's models do the work

| Step | Model | Why a model is needed |
|---|---|---|
| Hypotheses and experiment design | `muse-spark-1.3` (default) or `muse-wonder-1.0` via the Meta Model API, strict JSON schema output | Turning an unfamiliar UI and a plain-language goal into concrete, discriminating experiments. A rule set only covers the patterns someone coded in advance. |
| Follow-up round | same | Adapting to verified evidence: fixing experiments that did not apply, covering what is still untested. |
| Diagnosis | same, multimodal (screenshot + request timeline + optional page source) | Explaining *why* the verified failure happens and how to fix it, pointing at the responsible code. |

The model never grades itself. Its output can only reference elements discovery found, can only type short synthetic
strings into non-password fields, can only perturb same-origin requests that were observed (or method wildcards such as
`POST *`), and every expected value must be grounded in text the experiment itself typed. Anything else is rejected
and shown as "rejected by the validator". If the API is not configured or fails, Faultline falls back to a rules-only
planner and says so in the report.

## Evidence so far

All numbers below come from runs in this repository; the raw results are committed in `eval/`.

Six demo apps, each served as a buggy and a fixed build of the same file. Ground truth was written together with the
apps. `composer` and `newsletter` are held out: no rule and no prompt line may refer to them. An independent review on
26 October found two leaks (a rule matched the newsletter's button label; the prompt's list of fault classes mentioned
"tabs"); both were removed and everything below was measured again afterwards.

| Planner | Dev apps (6 known bugs) | Held-out apps (4 known bugs) | False alarms on fixed builds |
|---|---|---|---|
| Rules only (`eval/results-heuristic.md`) | 6/6 | 2/4 | 0 |
| Muse plans, `muse-spark-1.3` (`eval/results-recorded.md`) | not measured yet | **4/4** | 0 |

The rules miss the held-out "draft is lost when switching tabs" and "failed signup clears the form" bugs;
the retained Muse plans found both using the page inventory. The copied responses do not establish a complete
generation-attempt history or an independently measured first-attempt success rate.

How the Muse numbers were produced: the planner prompt was sent to `muse-spark-1.3` in the Meta playground, once per
held-out app (about 20 s and 1.2K input tokens per call; latency and tokens are in each file's `provenance`). The
answers are stored in `eval/recorded/` and replayed through the full pipeline with
`python scripts/replay_recorded.py`, which needs no key. Plans recorded with the first, leaky prompt are kept in
`eval/recorded/superseded/` for transparency and are not counted.

Muse's composer hypothesis was "switch to Preview and back to Write"; the minimizer then proved a sharper version:
clicking the already-active Write tab is enough to wipe the draft.

A full Muse run over all six apps through the API (`python scripts/evaluate.py --planner meta`, writes a unique
`eval/runs/<run-id>/result.json` and derived Markdown report) needs a key and has not been run in this repository yet, so no numbers are claimed for it.

These are small, purpose-built apps. They show that the pipeline works end to end and that every check is falsifiable
(each bug has a fixed twin that must pass); they are not a benchmark of real-world accuracy. A failure is only reported
as verified if it reproduces in all three confirmation runs; anything less is listed separately as "not reproducible
every time".

## Quick start

Requirements: Python 3.10+, about 300 MB for Playwright's Chromium.

```bash
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS / Linux:       source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
copy .env.example .env        # macOS / Linux: cp .env.example .env
# put your Meta Model API key into .env (MODEL_API_KEY=...)
python -m faultline serve
```

Open <http://127.0.0.1:8000>, pick a demo app, keep "Buggy build" and "Muse plans", and start a hunt. Then switch a
finding's re-test field to the fixed build and press "Re-test this build".

Command line:

```bash
python -m faultline hunt "http://127.0.0.1:8000/demo/search.html?mode=buggy"
python -m faultline hunt "http://localhost:5173/settings" --goal "Edits must survive a failed save"
python -m faultline replay artifacts/<hunt>/cx1/repro.json --url "http://127.0.0.1:8000/demo/search.html?mode=fixed"
pytest -q                      # unit, browser end-to-end, CI/auth, model and UI regression tests
```

Exported tests run with Playwright Test:

```bash
npm i -D @playwright/test && npx playwright install chromium
FAULTLINE_TARGET="http://localhost:5173/profile" npx playwright test faultline-*.spec.ts
```

## Using it on your own app

Start your dev server and point Faultline at a page. By default only `localhost`, `127.0.0.1`, `*.localhost` and
`*.test` are accepted. Discovery works best with accessible names or `data-testid` attributes, the same things that
make an app testable for anyone.

Settings in `.env`: `META_MODEL` (`muse-spark-1.3` or `muse-wonder-1.0`), `META_REASONING_EFFORT`
(`minimal` … `xhigh`). Page source is never sent by default. Tick "Let Muse read this page's own scripts" in the UI (or
pass `--send-source` on the command line) to include the inline scripts of the page under test in the diagnosis.

## Safety and scope

- Initial test targets must be local by default (no user-info or backslash tricks in the URL). Browser navigation
  to another origin and all HTTP navigation redirects are blocked before their destination is contacted; use the
  final local page URL directly. Ordinary unsigned-in contexts may still load external resources or make external
  API requests: this is not a complete network sandbox. Authenticated runs apply the stricter limits in
  [CI and authenticated apps](docs/CI.md). Page content is treated as untrusted data in every prompt.
- The model emits plans in a closed vocabulary and every plan is validated before execution. Model-written patches
  are never applied or executed by Faultline. The deterministic exporter produces Playwright tests from validated
  experiments; developers can run those tests themselves. Model-written comment text is reduced to single-line,
  control-character-free strings before it reaches an exported test.
- Password fields are never typed into. Typed values are short synthetic strings.
- Faultline proves that specific invariants fail under specific conditions. It does not prove that an app is correct,
  and it is not an accessibility audit.

## What was built during the hackathon

The original author states that the initial project was written during the event, starting after the kickoff on 26 October 2026.
The provided Drive snapshot did not include its Git history, so that timing was not independently audited.
The original implementation includes:
discovery, the validator and vocabulary, the Meta client, both planners, the executor with fault
injection, invariants, the minimizer and ablation, export, the web UI, the six demo apps, tests and evaluation.
Third-party components: Playwright, FastAPI, Uvicorn, httpx (their own licences). AI assistance: the code and docs were
written with Anthropic Claude for the original version and ChatGPT (OpenAI) for this development revision.
Only Meta models are used for AI reasoning at runtime.
See `docs/PROVENANCE.md`.

## Layout

```
faultline/
  discover.py    inventory of controls, hidden dialogs and API calls
  vocab.py       experiment vocabulary, validator, JSON schemas, descriptions
  planners.py    Muse planner, follow-up and diagnosis prompts, rules-only baseline
  meta.py        Meta Model API client (Chat Completions, structured output)
  executor.py    Playwright runner with delay/fail fault injection
  invariants.py  deterministic checks
  minimize.py    grounded delta debugging and fault ablation
  export.py      Playwright Test spec and repro.json
  hunt.py        orchestration
  server.py      UI, API and demo apps
  demo/          six demo apps, each with a buggy and a fixed build
scripts/evaluate.py   evaluation with ground truth
eval/                 results and recorded model plans
```
