# Evaluation run

Run: 20261026T231428.030908Z-heuristic-3ae17dba
Started: 2026-10-26T23:14:28.031479+00:00
Requested planner: heuristic
Status: completed
Completed targets: 12/12; errors: 0
Complete Meta targets: 0/12
Targets with applicable checks: 12/12
Runtime source unchanged during run: True

Counts below describe completed targets of the requested pipeline, including any explicitly labelled fallback.
An incomplete or degraded run is not a complete live-model evaluation.

| Set | Selected apps | Found / known bugs in completed targets | Planned known bugs | False alarms / fixed targets completed |
|---|---|---|---|---|
| Dev | profile, search, checkout, settings | 6/6 | 6 | 0 / 4 of 4 |
| Held out | composer, newsletter | 2/4 | 4 | 0 / 2 of 2 |

| App | Build | State | Actual planner | Found | Missed | False alarms / unexpected | Notes |
|---|---|---|---|---|---|---|---|
| profile | buggy | completed | heuristic | profile-focus, profile-overwrite | - | 0 | - |
| profile | fixed | completed | heuristic | - | - | 0 | - |
| search | buggy | completed | heuristic | search-order | - | 0 | - |
| search | fixed | completed | heuristic | - | - | 0 | - |
| checkout | buggy | completed | heuristic | checkout-double | - | 0 | - |
| checkout | fixed | completed | heuristic | - | - | 0 | - |
| settings | buggy | completed | heuristic | settings-errorloss, settings-stale-load | - | 0 | - |
| settings | fixed | completed | heuristic | - | - | 0 | - |
| composer | buggy | completed | heuristic | composer-double | composer-draft | 0 | - |
| composer | fixed | completed | heuristic | - | - | 0 | - |
| newsletter | buggy | completed | heuristic | newsletter-focus | newsletter-errorloss | 0 | - |
| newsletter | fixed | completed | heuristic | - | - | 0 | - |

| App | Build | Experiment outcomes | Applicable experiments | Applicable invariant checks | Execution complete |
|---|---|---|---|---|---|
| profile | buggy | failed=4, passed=2 | 6 | 6 | True |
| profile | fixed | passed=6 | 6 | 6 | True |
| search | buggy | failed=1 | 1 | 1 | True |
| search | fixed | passed=1 | 1 | 1 | True |
| checkout | buggy | failed=1, passed=1 | 2 | 2 | True |
| checkout | fixed | passed=2 | 2 | 2 | True |
| settings | buggy | failed=3, passed=1 | 4 | 4 | True |
| settings | fixed | passed=4 | 4 | 4 | True |
| composer | buggy | failed=1, passed=1 | 2 | 2 | True |
| composer | fixed | passed=2 | 2 | 2 | True |
| newsletter | buggy | failed=2, passed=1 | 3 | 3 | True |
| newsletter | fixed | passed=3 | 3 | 3 | True |

Browser runs: 106; recorded Meta calls: 0.
Reported usage tokens in/out: 0/0.
Missing usage and failed requests may not be included in token totals; these are not billing estimates.
Target processing time: 208.9 s.
