# Provenance

## Built during the hackathon

The original author declares that the initial code, demos, prompts, tests, evaluation scripts and documents were
created during the Meta Global AI Developer Hackathon, starting after kickoff, with no earlier project code reused.
The separate development revision was recovered from the owner's Google Drive source snapshot. That snapshot did
not contain the original Git history; this revision does not independently certify the original commit dates.
Preserve the original repository history when integrating these files.

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
`muse-spark-1.3` by default, `muse-wonder-1.0` optional. All runtime model backends are restricted to Meta models.
An optional compatible endpoint adapter is restricted to the configured Meta open-weights model names;
it has not been validated against a live checkpoint in this revision. See `docs/MODELS.md` for configuration
and the distinction between an endpoint alias and verified checkpoint provenance.

## Development assistance

The original code and documents were written with assistance from Anthropic Claude. ChatGPT (OpenAI) assisted with
this separate revision: evaluation preservation, CI/JUnit, saved-session support, model-backend safeguards,
review-only source patches, the notebook UI, regression tests, verification and documentation. The owner directed
the project and requested this work. These are development tools; the application does not call OpenAI or Anthropic.
Third-party help is disclosed so reviewers can distinguish the owner's project, dependencies and development assistance.
Only actual executed checks are reported in the associated evidence files.

## Third-party components

Playwright (Apache-2.0), FastAPI (MIT), Uvicorn (BSD-3-Clause), httpx (BSD-3-Clause), pytest (MIT), each used under
its own licence as a dependency. The UI loads the Archivo and Source Serif 4 fonts from Google Fonts (SIL Open Font
License). No third-party datasets, images or copyrighted content are bundled. The names in the search demo are
public historical figures used as sample data.

## External validation sources

Unmodified TodoMVC and 2048 checkouts were used for local compatibility probes; their MIT licenses and pinned revisions
are recorded in `docs/EXTERNAL_VALIDATION.md` and `eval/external/`. Their source code is not bundled in this release.
The public rule review and the subsequently supplied participant Guide are assessed in `docs/RULES_REVIEW.md`.
The Guide names an October 26 kickoff and an October 27 start to the building period; obtain organizer clarification
before treating the original author's October 26 start as independently established compliance. Do not rewrite dates.
