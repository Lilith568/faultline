# Faultline

**Faultline breaks your web app on purpose, then hands you the failing test.**

Built for the Meta Global AI Developer Hackathon 2026, Indie track, problem statement *Push the Frontier*.

Your happy-path tests pass. Then a real user on a slow train types into a form while the profile request is still in flight,
and the late response silently replaces their text. Or a search shows results for "ca" although they typed "cat". Or a
double-click places two orders. These bugs depend on timing, so they rarely show up on `localhost` and almost never in
a test suite.

Faultline hunts for exactly these failures in an app you are building:

1. **Explore.** It opens your local app in Playwright, records every control (including hidden dialogs) and every API
   call the page makes, and clicks "opener" controls to learn what they reveal.
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
   of the failing state and, if you allow it, the page's own source. Faultline exports a ready-to-run
   **Playwright Test spec** that fails while the bug exists and passes once it is fixed. One click re-tests the exact
   counterexample against your fixed build.

```
 your app ──► discover ──► Muse: hypotheses ──► validator ──► Playwright + injected faults ──► invariants
                               ▲                                                                  │
                               └────────── Muse: follow-up round ◄──── verified results ◄──────────┘
                                                                                                  │
               regression test (.spec.ts) ◄── Muse: diagnosis ◄── 3× confirmation ◄── minimizer ◄─┘
```

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

All numbers below come from runs in this repository. Raw reports are in `eval/`.

**Rules-only baseline** (`python scripts/evaluate.py --planner heuristic`): 6 demo apps, each served as a buggy and a
fixed build. Ground truth was written together with the apps; `composer` and `newsletter` are held out.

| Set | Bugs found | False alarms on fixed builds |
|---|---|---|
| Dev apps (profile, search, checkout, settings) | 6/6 | 0 |
| Held-out apps (composer, newsletter) | 3/4 | 0 |

The baseline misses the held-out "draft is lost when switching tabs" bug because no rule describes it.

**Muse plans for the two held-out apps** (`eval/recorded/`): real `muse-spark-1.3` responses from the Meta
playground (one call per app, about 15 s and 1.1K input tokens each), replayed through Faultline with
`python -m faultline hunt URL --plan eval/recorded/<app>-muse-spark-1.3.json`:

| App | Build | Muse hypotheses | Known bugs verified | False alarms |
|---|---|---|---|---|
| composer | buggy | 4 | 2/2 (draft lost on tab switch, double publish) | 0 |
| composer | fixed | 4 | - | 0 |
| newsletter | buggy | 4 | 2/2 (focus lost after closing, failed signup clears the form) | 0 |
| newsletter | fixed | 4 | - | 0 |

Held-out total: Muse plans 4/4, rules-only baseline 3/4, no false alarms for either.

Muse's composer hypothesis was "switch to Preview and back to Write"; the minimizer then proved a sharper version:
clicking the already-active Write tab is enough to wipe the draft.

A full Muse evaluation over all apps calls the API directly: `python scripts/evaluate.py --planner meta`
(writes `eval/results-meta.md`). It has not been run in this repository yet, so no numbers are claimed for it.

These are small, purpose-built apps. They show that the pipeline works end to end and that the checks are falsifiable
(every bug has a fixed twin that must pass); they are not a benchmark of real-world accuracy.

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
pytest -q                      # 22 tests: unit, browser end-to-end, and the Meta path against a fake endpoint
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
(`minimal` … `xhigh`). The "send page source to Muse" option only sends inline scripts of the page under test, to help
the diagnosis point at the right code.

## Safety and scope

- Local targets only by default; page content is treated as untrusted data in every prompt.
- The model emits plans in a closed vocabulary; generated code is never executed.
- Password fields are never typed into. Typed values are short synthetic strings.
- Faultline proves that specific invariants fail under specific conditions. It does not prove that an app is correct,
  and it is not an accessibility audit.

## What was built during the hackathon

Everything in this repository was written during the event (from the kickoff on 26 October 2026), visible in the
git history: discovery, the validator and vocabulary, the Meta client, both planners, the executor with fault
injection, invariants, the minimizer and ablation, export, the web UI, the six demo apps, tests and evaluation.
Third-party components: Playwright, FastAPI, Uvicorn, httpx (their own licences). AI assistance: the code and docs were
written with the help of an AI coding assistant (Anthropic Claude); Meta Muse models do all reasoning at runtime.
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
