# Evaluation run

Run: 20261026T225923.634329Z-recorded-cd9663d4
Started: 2026-10-26T22:59:23.634560+00:00
Requested planner: recorded
Status: completed
Completed targets: 4/4; errors: 0
Complete Meta targets: 0/4

Counts below describe completed targets of the requested pipeline, including any explicitly labelled fallback.
An incomplete or degraded run is not a complete live-model evaluation.

| Set | Selected apps | Found / evaluated known bugs | Planned known bugs | False alarms / fixed builds tested |
|---|---|---|---|---|
| Dev | - | 0/0 | 0 | 0 / 0 of 0 |
| Held out | composer, newsletter | 4/4 | 4 | 0 / 2 of 2 |

| App | Build | State | Actual planner | Found | Missed | False alarms / unexpected | Notes |
|---|---|---|---|---|---|---|---|
| composer | buggy | completed | recorded | composer-double, composer-draft | - | 0 | - |
| composer | fixed | completed | recorded | - | - | 0 | - |
| newsletter | buggy | completed | recorded | newsletter-errorloss, newsletter-focus | - | 0 | - |
| newsletter | fixed | completed | recorded | - | - | 0 | - |

Browser runs: 40; recorded Meta calls: 0.
Reported usage tokens in/out: 0/0.
Missing usage and failed requests may not be included in token totals; these are not billing estimates.
Target processing time: 62.9 s.
