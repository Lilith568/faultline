# Evaluation summary

Created: 2026-10-26T23:19:05.173925+00:00
Result files seen: 6; attempts counted: 6.

Groups match code/configuration/dependency fingerprints. All attempt statuses are shown. Detection ranges require complete evaluations with applicable checks and unchanged runtime hashes; partial, fallback and source-unverified runs remain visible. Repeated runs on the same small apps do not measure real-world accuracy.

## Comparable group 1

Fingerprint: `fe4d3374c5b95c5f11eac2a45068f7071bfdb7923fa51d29ec63c4ae0b7ee8f4`
Planner: heuristic; model: none; apps: checkout.
Attempts: completed=1.
Runtime hash checks: not_recorded=1.
Complete evaluations used for detection ranges: 0 of 1 attempts.

| Set | Found per complete run | Known bugs per run | Mean found | Range | False alarms per complete run |
|---|---|---|---|---|---|
| Dev | [] | [] | not measured | not measured | [] |
| Held out | [] | [] | not measured | not measured | [] |

All targets below include fallback and partial runs. They are coverage evidence, not pure model scores.

| Known bug | Targets completed / listed | Found in completed targets | Found in complete evaluations |
|---|---|---|---|
| checkout-double | 1/1 | 1 | 0 |

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
Runtime hash checks: not_recorded=1.
Complete evaluations used for detection ranges: 0 of 1 attempts.

| Set | Found per complete run | Known bugs per run | Mean found | Range | False alarms per complete run |
|---|---|---|---|---|---|
| Dev | [] | [] | not measured | not measured | [] |
| Held out | [] | [] | not measured | not measured | [] |

All targets below include fallback and partial runs. They are coverage evidence, not pure model scores.

| Known bug | Targets completed / listed | Found in completed targets | Found in complete evaluations |
|---|---|---|---|
| composer-double | 1/1 | 1 | 0 |
| composer-draft | 1/1 | 1 | 0 |
| newsletter-errorloss | 1/1 | 1 | 0 |
| newsletter-focus | 1/1 | 1 | 0 |

| Fixed build | Targets completed / listed | False alarms on completed targets |
|---|---|---|
| composer | 1/1 | 0 |
| newsletter | 1/1 | 0 |

| Attempt | Status |
|---|---|
| 20261026T225923.634329Z-recorded-cd9663d4 | completed |

## Comparable group 3

Fingerprint: `2669ae5da8c03b79750badd6153967fd7867d6d24b2d9f0b11b6291827aca5b7`
Planner: heuristic; model: none; apps: profile, search, checkout, settings, composer, newsletter.
Attempts: completed=1.
Runtime hash checks: unchanged=1.
Complete evaluations used for detection ranges: 1 of 1 attempts.

| Set | Found per complete run | Known bugs per run | Mean found | Range | False alarms per complete run |
|---|---|---|---|---|---|
| Dev | [6] | [6] | 6 | 6–6 | [0] |
| Held out | [2] | [4] | 2 | 2–2 | [0] |

All targets below include fallback and partial runs. They are coverage evidence, not pure model scores.

| Known bug | Targets completed / listed | Found in completed targets | Found in complete evaluations |
|---|---|---|---|
| checkout-double | 1/1 | 1 | 1 |
| composer-double | 1/1 | 1 | 1 |
| composer-draft | 1/1 | 0 | 0 |
| newsletter-errorloss | 1/1 | 0 | 0 |
| newsletter-focus | 1/1 | 1 | 1 |
| profile-focus | 1/1 | 1 | 1 |
| profile-overwrite | 1/1 | 1 | 1 |
| search-order | 1/1 | 1 | 1 |
| settings-errorloss | 1/1 | 1 | 1 |
| settings-stale-load | 1/1 | 1 | 1 |

| Fixed build | Targets completed / listed | False alarms on completed targets |
|---|---|---|
| checkout | 1/1 | 0 |
| composer | 1/1 | 0 |
| newsletter | 1/1 | 0 |
| profile | 1/1 | 0 |
| search | 1/1 | 0 |
| settings | 1/1 | 0 |

| Attempt | Status |
|---|---|
| 20261026T230757.259291Z-heuristic-3bb44875 | completed |

## Comparable group 4

Fingerprint: `a24993f6e7516fbf9c60e337bd11b657d0322d12f2e7c811e6b98166d5c5cb71`
Planner: recorded; model: none; apps: composer, newsletter.
Attempts: degraded=1.
Runtime hash checks: changed_or_unverifiable=1.
Complete evaluations used for detection ranges: 0 of 1 attempts.

| Set | Found per complete run | Known bugs per run | Mean found | Range | False alarms per complete run |
|---|---|---|---|---|---|
| Dev | [] | [] | not measured | not measured | [] |
| Held out | [] | [] | not measured | not measured | [] |

All targets below include fallback and partial runs. They are coverage evidence, not pure model scores.

| Known bug | Targets completed / listed | Found in completed targets | Found in complete evaluations |
|---|---|---|---|
| composer-double | 1/1 | 1 | 0 |
| composer-draft | 1/1 | 1 | 0 |
| newsletter-errorloss | 1/1 | 1 | 0 |
| newsletter-focus | 1/1 | 1 | 0 |

| Fixed build | Targets completed / listed | False alarms on completed targets |
|---|---|---|
| composer | 1/1 | 0 |
| newsletter | 1/1 | 0 |

| Attempt | Status |
|---|---|
| 20261026T231123.089907Z-recorded-c0fd88b5 | degraded |

## Comparable group 5

Fingerprint: `6c09eeee0f84f690d55d93ccaf082a44e86d1e84b8135493dbfc8ea8ad24b6cf`
Planner: heuristic; model: none; apps: profile, search, checkout, settings, composer, newsletter.
Attempts: completed=1.
Runtime hash checks: unchanged=1.
Complete evaluations used for detection ranges: 1 of 1 attempts.

| Set | Found per complete run | Known bugs per run | Mean found | Range | False alarms per complete run |
|---|---|---|---|---|---|
| Dev | [6] | [6] | 6 | 6–6 | [0] |
| Held out | [2] | [4] | 2 | 2–2 | [0] |

All targets below include fallback and partial runs. They are coverage evidence, not pure model scores.

| Known bug | Targets completed / listed | Found in completed targets | Found in complete evaluations |
|---|---|---|---|
| checkout-double | 1/1 | 1 | 1 |
| composer-double | 1/1 | 1 | 1 |
| composer-draft | 1/1 | 0 | 0 |
| newsletter-errorloss | 1/1 | 0 | 0 |
| newsletter-focus | 1/1 | 1 | 1 |
| profile-focus | 1/1 | 1 | 1 |
| profile-overwrite | 1/1 | 1 | 1 |
| search-order | 1/1 | 1 | 1 |
| settings-errorloss | 1/1 | 1 | 1 |
| settings-stale-load | 1/1 | 1 | 1 |

| Fixed build | Targets completed / listed | False alarms on completed targets |
|---|---|---|
| checkout | 1/1 | 0 |
| composer | 1/1 | 0 |
| newsletter | 1/1 | 0 |
| profile | 1/1 | 0 |
| search | 1/1 | 0 |
| settings | 1/1 | 0 |

| Attempt | Status |
|---|---|
| 20261026T231428.030908Z-heuristic-3ae17dba | completed |

## Comparable group 6

Fingerprint: `1ddc831994927cc0d7af546e570cce11250e1521d0bd81f1c97f22692b5b7d83`
Planner: recorded; model: none; apps: composer, newsletter.
Attempts: completed=1.
Runtime hash checks: unchanged=1.
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
| 20261026T231758.114126Z-recorded-61131d58 | completed |

