# Evaluation protocol

## Targets

Six small demo apps, each served in two builds from the same file: `?mode=buggy` and `?mode=fixed`. The server strips
the inactive code path, so each build contains only its own code, like two real deployments.

| App | Known bugs in the buggy build | Held out |
|---|---|---|
| profile | late profile response overwrites typed text; focus not returned after the dialog closes | no |
| search | a late response for an older query replaces newer results | no |
| checkout | double-click places two orders | no |
| settings | failed save reverts the user's edits; slow initial load overwrites early edits | no |
| composer | switching tabs discards the draft; double-click publishes twice | yes |
| newsletter | focus lost after closing the dialog; failed signup clears the form | yes |

Ground truth is in `scripts/evaluate.py` and was written together with the apps, before any planner was run.
`composer` and `newsletter` are held out: no rule and no prompt line may refer to them.

An independent review on 26 October found two violations of that rule, and both were fixed before the numbers below
were measured: the rules-only planner recognised the newsletter's exact button label ("sign me up"), and the planner
prompt's list of fault classes said "drafts lost when panels or tabs are switched", which is close to the composer
bug. The prompt now names fault classes without UI-specific examples ("unsaved input discarded when part of the page
is re-rendered").

## Scoring

A verified failure (reproduced in 3 of 3 runs) counts as finding a known bug when its failing invariant kind, its
target element (by `data-testid`) or endpoint, and the injected fault it needs all match the ground truth entry.
Any verified failure on a fixed build is a false alarm. Verified failures on buggy builds that match no known bug are
listed as unexpected and reviewed by hand.

## Planners compared

1. Rules-only baseline: hand-written rules for well-known patterns, same browser, same fault injection, same
   validator, same minimizer. It is a strong baseline on purpose: it isolates what the model adds.
2. Muse: `muse-spark-1.3` through the Meta Model API with the strict JSON schema, two rounds.

## Results

| Planner | Dev apps | Held-out apps | False alarms on fixed builds | Raw results |
|---|---|---|---|---|
| Rules only | 6/6 | 2/4 | 0 | `eval/results-heuristic.md` |
| Muse (`muse-spark-1.3`, recorded plans) | not measured | 4/4 | 0 | `eval/results-recorded.md`, `eval/recorded/` |

The Muse plans were produced in the Meta playground with the shipped planner prompt (one call per app) and replayed
with `python scripts/replay_recorded.py`. Plans recorded with the earlier prompt are in `eval/recorded/superseded/`
and are not counted. `python scripts/evaluate.py --planner meta` runs the same comparison through the API on all six
apps; it needs a key and has not been run yet.

## Known limitations

- Small, purpose-built apps; results show the method works end to end, not real-world accuracy.
- The planner prompt still names generic fault classes (for example "unsaved input discarded when part of the page is
  re-rendered"). The comparison shows that the model turns such a generic description into a working experiment for
  an unseen UI; it does not show that the model invented the class.
- Two held-out apps with four bugs are a small sample; one recorded plan per app means run-to-run variation of the
  model is not measured.
- Experiments use human-like pacing (120 ms between actions) so that races appear only when Faultline injects them.


## Preserving live evaluation attempts

The historical `eval/results-heuristic.*`, `eval/results-recorded.*` and all recorded
plans remain unchanged. New evaluations never write to those paths.

Run the live Meta evaluation from the repository root, with `MODEL_API_KEY` in your
local `.env` or environment:

```bash
python scripts/evaluate.py --planner meta --repeat 3
python scripts/summarize_eval.py
```

`--repeat` is the number of independent complete evaluation attempts, not the number
of confirmation runs for one finding. Each attempt gets a uniquely reserved directory
under `eval/runs/`, containing `result.json`, a derived `result.md`, and hunt artifacts.
The JSON checkpoint is replaced atomically after each target. Earlier attempts are
never overwritten. If the process is interrupted, completed targets remain available;
unfinished targets remain explicitly untested. A process killed without cleanup may
leave a `running` checkpoint, which is never counted as a completed evaluation.

The evaluator records the requested and actual planner separately. A rules fallback,
a failed follow-up request, a template diagnosis after a model failure, or an incomplete
target prevents a live Meta attempt from being labelled complete. The command returns
a nonzero exit code for these outcomes, even when a fallback found bugs. Such findings
remain in the evidence instead of disappearing from the report. An API failure is not
a clean fixed-build result.

For a shorter operational check, explicitly select a subset:

```bash
python scripts/evaluate.py --planner heuristic --apps checkout
python scripts/replay_recorded.py
```

Subset reports name the selected apps and denominators. A recorded replay is labelled
`recorded` and cannot substitute for a live API run. Replays also receive independent
run directories and never overwrite the historical recorded results.

## Reproducibility and aggregation

Each manifest records model configuration, dependency and Python versions, source and
ground-truth SHA-256 hashes, and Git commit/dirty status when the project itself contains
Git metadata. A downloaded source snapshot without `.git` records that history is
unavailable; it does not invent a commit or borrow an ancestor repository's identity.
The original demo bytes and ground truth remain the basis of the comparison.

The summary command reads every `result.json` below the chosen run directory, shows
completed, degraded, interrupted and failed attempts, and separates different source,
model, app-selection or dependency fingerprints. Within a comparable group, it lists
all complete-run detection counts and their mean/range. Per-bug and fixed-build tables
also expose coverage from partial and fallback attempts, clearly separated from pure
complete-model scores. Invalid result files and duplicate run identifiers are reported
as input problems rather than silently discarded. Summary files receive their own
unique directory under `eval/summaries/`.

Do not run repeatedly and publish only the highest score. Decide the repetition count
before starting, retain failures, and report the number of complete and incomplete
attempts with every result. Repetitions on these same small apps measure run-to-run
variation; they do not establish accuracy on real projects or create new held-out apps.
API usage totals contain only usage returned by the provider and are not billing
estimates. No API key, Authorization header or complete environment is recorded in
evaluation metadata. Review artifacts before sharing them, especially when extending
the evaluator beyond the bundled synthetic apps.

Only promote measured results from these saved files into README or submission claims.
The commands above are instructions, not evidence that a live Meta run has succeeded.


## Coverage and a stable source snapshot

A target report now records experiment outcomes, invariant outcomes, applicable
experiment and invariant counts, and whether execution completed without an experiment
error. A target with only inapplicable checks or no usable checks cannot supply a clean
fixed-build verdict. Execution errors and absent coverage degrade the attempt while
retaining confirmed findings, all planned targets, and their denominators. This applies
to the baseline and recorded replay as well as the live Meta path.

The evaluator hashes runtime, fixture and evaluation-tool sources again at the end of
each attempt. A changed, added or removed source file degrades the attempt and is listed
in its manifest. UI-only changes are recorded in the initial metadata but excluded from
this detection comparison. The summary keeps all attempts visible, but complete-run
ranges require applicable coverage and a successful unchanged-source check. Older
integration manifests without an end-of-run hash remain available as source-unverified
evidence; they are not silently upgraded into final comparable runs.
