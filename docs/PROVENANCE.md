# Provenance

## Built during the hackathon

All code, demo apps, prompts, tests, evaluation scripts and documents in this repository were created during the
Meta Global AI Developer Hackathon, starting after the kickoff on 26 October 2026. The repository and all of its
commits date from the event. No code from earlier projects was reused.

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
| Tests and evaluation | `tests/`, `scripts/evaluate.py`, `eval/` |

## Runtime models

Meta Muse models via the Meta Model API (`https://api.meta.ai/v1`, Chat Completions with structured output):
`muse-spark-1.3` by default, `muse-wonder-1.0` optional. No other AI model is called by the application.

## Development assistance

The code and documents were written with the help of an AI coding assistant (Anthropic Claude). The author directed
the work, chose the project and owns the result. This is disclosed here because the event rules ask that original
contributions be clearly identifiable.

## Third-party components

Playwright (Apache-2.0), FastAPI (MIT), Uvicorn (BSD-3-Clause), httpx (BSD-3-Clause), pytest (MIT), each used under
its own licence as a dependency. The UI loads the Archivo and Source Serif 4 fonts from Google Fonts (SIL Open Font
License). No third-party datasets, images or copyrighted content are bundled. The names in the search demo are
public historical figures used as sample data.
