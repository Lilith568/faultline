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
`composer` and `newsletter` were not used while writing the prompts or the rules-only planner.

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

See `eval/results-heuristic.md` for the latest rules-only run and `eval/recorded/` for model plans captured from the
Meta playground and replayed with `faultline hunt URL --plan FILE`. Run `python scripts/evaluate.py --planner meta`
with a key to produce `eval/results-meta.md`.

## Known limitations

- Small, purpose-built apps; results show the method works end to end, not real-world accuracy.
- The planner prompt lists common fault classes (including drafts lost when switching tabs). The rules-only planner
  has no rule for that class. The comparison therefore shows that the model turns a one-line description into a
  working experiment for an unseen UI; it does not show that the model invented the class.
- Experiments use human-like pacing (120 ms between actions) so that races appear only when Faultline injects them.
