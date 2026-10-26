# Evaluation run

Run: 20261026T231123.089907Z-recorded-c0fd88b5
Started: 2026-10-26T23:11:23.090412+00:00
Requested planner: recorded
Status: degraded
Completed targets: 4/4; errors: 0
Complete Meta targets: 0/4
Targets with applicable checks: 4/4
Runtime source unchanged during run: False

Counts below describe completed targets of the requested pipeline, including any explicitly labelled fallback.
An incomplete or degraded run is not a complete live-model evaluation.

| Set | Selected apps | Found / known bugs in completed targets | Planned known bugs | False alarms / fixed targets completed |
|---|---|---|---|---|
| Dev | - | 0/0 | 0 | 0 / 0 of 0 |
| Held out | composer, newsletter | 4/4 | 4 | 0 / 2 of 2 |

| App | Build | State | Actual planner | Found | Missed | False alarms / unexpected | Notes |
|---|---|---|---|---|---|---|---|
| composer | buggy | completed | recorded | composer-double, composer-draft | - | 0 | - |
| composer | fixed | completed | recorded | - | - | 0 | - |
| newsletter | buggy | completed | recorded | newsletter-errorloss, newsletter-focus | - | 0 | - |
| newsletter | fixed | completed | recorded | - | - | 0 | - |

| App | Build | Experiment outcomes | Applicable experiments | Applicable invariant checks | Execution complete |
|---|---|---|---|---|---|
| composer | buggy | failed=2, passed=2 | 4 | 4 | True |
| composer | fixed | passed=4 | 4 | 4 | True |
| newsletter | buggy | failed=2, passed=2 | 4 | 6 | True |
| newsletter | fixed | passed=4 | 4 | 6 | True |

Runtime source changed during this attempt: faultline/discover.py

Browser runs: 40; recorded Meta calls: 0.
Reported usage tokens in/out: 0/0.
Missing usage and failed requests may not be included in token totals; these are not billing estimates.
Target processing time: 64.6 s.
