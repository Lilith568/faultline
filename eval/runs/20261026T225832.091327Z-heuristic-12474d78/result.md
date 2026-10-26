# Evaluation run

Run: 20261026T225832.091327Z-heuristic-12474d78
Started: 2026-10-26T22:58:32.091422+00:00
Requested planner: heuristic
Status: completed
Completed targets: 2/2; errors: 0
Complete Meta targets: 0/2

Counts below describe completed targets of the requested pipeline, including any explicitly labelled fallback.
An incomplete or degraded run is not a complete live-model evaluation.

| Set | Selected apps | Found / evaluated known bugs | Planned known bugs | False alarms / fixed builds tested |
|---|---|---|---|---|
| Dev | checkout | 1/1 | 1 | 0 / 1 of 1 |
| Held out | - | 0/0 | 0 | 0 / 0 of 0 |

| App | Build | State | Actual planner | Found | Missed | False alarms / unexpected | Notes |
|---|---|---|---|---|---|---|---|
| checkout | buggy | completed | heuristic | checkout-double | - | 0 | - |
| checkout | fixed | completed | heuristic | - | - | 0 | - |

Browser runs: 13; recorded Meta calls: 0.
Reported usage tokens in/out: 0/0.
Missing usage and failed requests may not be included in token totals; these are not billing estimates.
Target processing time: 25.9 s.
