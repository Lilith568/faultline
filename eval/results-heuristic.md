### Planner: heuristic
Run: 2026-10-26T22:10:56.304755+00:00

| Set | Bugs found | False positives on fixed builds | Unexpected findings on buggy builds |
|---|---|---|---|
| Dev apps (profile, search, checkout, settings) | 6/6 | 0 | 0 |
| Held-out apps (composer, newsletter) | 2/4 | 0 | 0 |

Browser runs: 106 · Meta calls: 0 · Tokens in/out: 0/0 · Wall time: 194.7 s

| App | Build | Found | Missed | Unexpected | Browser runs |
|---|---|---|---|---|---|
| profile | buggy | profile-focus, profile-overwrite | - | - | 25 |
| profile | fixed | - | - | - | 6 |
| search | buggy | search-order | - | - | 8 |
| search | fixed | - | - | - | 1 |
| checkout | buggy | checkout-double | - | - | 11 |
| checkout | fixed | - | - | - | 2 |
| settings | buggy | settings-errorloss, settings-stale-load | - | - | 27 |
| settings | fixed | - | - | - | 4 |
| composer (held-out) | buggy | composer-double | composer-draft | - | 10 |
| composer (held-out) | fixed | - | - | - | 2 |
| newsletter (held-out) | buggy | newsletter-focus | newsletter-errorloss | - | 7 |
| newsletter (held-out) | fixed | - | - | - | 3 |
