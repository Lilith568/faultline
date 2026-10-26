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
