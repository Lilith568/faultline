# Evaluation summary

Created: 2026-10-26T23:00:42.978330+00:00
Result files seen: 2; attempts counted: 2.

Groups match code/configuration/dependency fingerprints. All attempt statuses are shown. Detection ranges use only complete evaluations; partial and fallback runs remain visible. Repeated runs on the same small apps do not measure real-world accuracy.

## Comparable group 1

Fingerprint: `fe4d3374c5b95c5f11eac2a45068f7071bfdb7923fa51d29ec63c4ae0b7ee8f4`
Planner: heuristic; model: none; apps: checkout.
Attempts: completed=1.
Complete evaluations used for detection ranges: 1 of 1 attempts.

| Set | Found per complete run | Known bugs per run | Mean found | Range | False alarms per complete run |
|---|---|---|---|---|---|
| Dev | [1] | [1] | 1 | 1–1 | [0] |
| Held out | [0] | [0] | 0 | 0–0 | [0] |

All targets below include fallback and partial runs. They are coverage evidence, not pure model scores.

| Known bug | Targets completed / listed | Found in completed targets | Found in complete evaluations |
|---|---|---|---|
| checkout-double | 1/1 | 1 | 1 |

| Fixed build | Targets completed / listed | False alarms on completed targets |
|---|---|---|
| checkout | 1/1 | 0 |

| Attempt | Status |
|---|---|
| 20261026T225832.091327Z-heuristic-12474d78 | completed |

## Comparable group 2

Fingerprint: `93d9dfdcce92a17c631719d2ac5468b52c2102177fd677f7a9149e07ab78ceca`
Planner: recorded; model: none; apps: composer, newsletter.
Attempts: completed=1.
Complete evaluations used for detection ranges: 1 of 1 attempts.

| Set | Found per complete run | Known bugs per run | Mean found | Range | False alarms per complete run |
|---|---|---|---|---|---|
| Dev | [0] | [0] | 0 | 0–0 | [0] |
| Held out | [4] | [4] | 4 | 4–4 | [0] |

All targets below include fallback and partial runs. They are coverage evidence, not pure model scores.

| Known bug | Targets completed / listed | Found in completed targets | Found in complete evaluations |
|---|---|---|---|
| composer-double | 1/1 | 1 | 1 |
| composer-draft | 1/1 | 1 | 1 |
| newsletter-errorloss | 1/1 | 1 | 1 |
| newsletter-focus | 1/1 | 1 | 1 |

| Fixed build | Targets completed / listed | False alarms on completed targets |
|---|---|---|
| composer | 1/1 | 0 |
| newsletter | 1/1 | 0 |

| Attempt | Status |
|---|---|
| 20261026T225923.634329Z-recorded-cd9663d4 | completed |

