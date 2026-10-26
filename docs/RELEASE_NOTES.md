# Faultline 0.2.0

This is a separate development revision of the owner's Drive snapshot. The prior Drive version is unchanged. It is not a competition submission or a claim of production readiness.

## Changes

- Preserve each evaluation and replay in a unique directory; checkpoint each completed target and distinguish requested model, actual planner, errors and fallbacks. Summaries keep incompatible configurations separate.
- Add conservative CI exit codes, JUnit output and a manually triggered GitHub Actions example.
- Support explicitly supplied saved login state through the CLI, with scoped state and fresh browser contexts. Authenticated requests have documented restrictions; state is not part of the deliverable.
- Offer source-based patch proposals only after explicit selection and consent. Validate unified diffs against the selected text without writing or executing them.
- Add an optional Meta open-weights HTTP backend, credential separation and attempted-request accounting.
- Rework the single-file notebook interface: truthful phase states, clearer expected/observed evidence, larger screenshots, actual exported test previews, distinct re-test outcomes and an explicit no-coverage state.
- Add protection against foreign-origin API requests, unrecognized API hosts and password fields that change after discovery. Generated specs also reject password typing and block service workers.
- Document actual upstream compatibility probes, rule verification gaps, development provenance and the Muse Wonder handoff.

## What stays comparable

Bundled demo bytes, existing ground truth, planner prompts/rules and recorded plans remain unchanged. The runtime did change, so historical results retain their historical identity and new evaluation attempts record source fingerprints. Do not relabel old measurements as results of this revision.

## Validation and remaining work

See `eval/verification/release-checks.json` for executed checks and `docs/QUALITY_REVIEW.md` for the independent readiness assessment. Hosted Meta and open-weights live behavior still require the owner's configured endpoint. No real upstream defect or complete end-to-end live model benchmark is claimed.

## Apply to the original Git repository

The Drive snapshot did not contain the original Git history. Copy the supplied source files into the original repository or apply the included source patch and copy the new `eval/` evidence alongside it. Inspect `git diff` and retain the original `.git` directory. Never replace the original history with a newly invented history. Keep existing evaluation results and private `.env`/`.auth` files local.

Suggested commit message:

```text
feat: preserve evaluation evidence and add CI, saved sessions and review-only fixes
```

## Local check

```bash
pip install -e ".[dev]"
python -m playwright install chromium
pytest -q
python -m faultline serve
```

Open `http://127.0.0.1:8000`, choose a demo and click **Start hunt**. If there is no Meta key, select **Rules only**; this does not establish Meta quality. At a finding, use the corresponding `?mode=fixed` URL and **Re-test this build**. Confirm that the exact test preview matches the downloaded `.spec.ts`.

Then run the separately preserved evaluations described in `docs/EVALUATION.md`. For a real Meta evaluation, put the key into your local environment or `.env`, never into a report or chat.
