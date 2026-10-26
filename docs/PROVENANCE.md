# Provenance

## Built during the hackathon

All code, demo apps, prompts, tests, evaluation scripts and documents in this repository were created during the
Meta Global AI Developer Hackathon, starting after the kickoff on 26 October 2026 (12:00 ET). No code from earlier
projects was reused. The Git history records every step with its original date.

| Part | Files |
|---|---|
| Page discovery and exploration | `faultline/discover.py` |
| Experiment vocabulary, validator, JSON schemas | `faultline/vocab.py` |
| Meta Model API client | `faultline/meta.py` |
| Muse planner, follow-up and diagnosis prompts; rules-only baseline | `faultline/planners.py` |
| Fault-injecting Playwright executor | `faultline/executor.py` |
| Invariants | `faultline/invariants.py` |
| Minimizer and fault ablation | `faultline/minimize.py` |
| Playwright Test export | `faultline/export.py` |
| Orchestration, CLI, server, UI | `faultline/hunt.py`, `cli.py`, `server.py`, `static/index.html` |
| Six demo apps with buggy and fixed builds | `faultline/demo/` |
| CI exit codes and JUnit reports | `faultline/reports.py`, `cli.py`, `.github/workflows/` |
| Saved login state for authenticated local apps | `faultline/auth.py` |
| Review-only fix proposals | `faultline/patches.py` |
| Recorded Muse plan replay in the UI | `faultline/server.py`, `static/index.html` |
| Tests and evaluation | `tests/`, `scripts/`, `eval/` |

## Runtime models

Meta Muse models via the Meta Model API (`https://api.meta.ai/v1`, Chat Completions with structured output):
`muse-spark-1.3` by default, `muse-wonder-1.0` optional. All runtime model backends are restricted to Meta models.
An optional compatible endpoint adapter is restricted to the configured Meta open-weights model names;
it has been tested against mocked endpoints, not yet against a live checkpoint. See `docs/MODELS.md` for configuration
and the distinction between an endpoint alias and verified checkpoint provenance.

## Development assistance

The author directed the work, chose the project and owns the result. AI coding assistants helped write code and
documents: Anthropic Claude (versions 0.1 and 0.3) and ChatGPT by OpenAI (version 0.2: evaluation preservation,
CI/JUnit, saved-session support, model-backend safeguards, review-only patches, the notebook UI and regression tests).
These are development tools only; the application never calls OpenAI or Anthropic. This is disclosed because the
event rules ask that contributions be clearly identifiable.

## Third-party components

Playwright (Apache-2.0), FastAPI (MIT), Uvicorn (BSD-3-Clause), httpx (BSD-3-Clause), pytest (MIT), each used under
its own licence as a dependency. The UI loads the Archivo and Source Serif 4 fonts from Google Fonts (SIL Open Font
License). No third-party datasets, images or copyrighted content are bundled. The names in the search demo are
public historical figures used as sample data.

## External validation sources

Unmodified TodoMVC and 2048 checkouts were used for local compatibility probes; their MIT licenses and pinned revisions
are recorded in `docs/EXTERNAL_VALIDATION.md` and `eval/external/`. Their source code is not bundled in this release.
