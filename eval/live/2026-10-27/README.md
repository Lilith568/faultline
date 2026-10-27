# Live Meta API runs, 2026-10-27

Four hunts with the UI's **Live Muse API** mode against the hosted Meta Model API
(`api.meta.ai`, model `muse-spark-1.3`, medium reasoning). Every planning and
diagnosis step was a real network call; the mode stops instead of falling back to
rules, and none of the runs used recorded plans or injected responses.

| App (held out) | Build | Live API status | Successful calls | Verified failures | Confirmation | Duration | Report |
|---|---|---|---|---|---|---|---|
| Release notes (`composer`) | buggy | complete | 4 | draft lost when switching Write → Preview → Write; double-activating Publish sends two requests | 3/3, 3/3 | 66.5 s | [report](20261027-145146-2c85b8-composer-buggy/report.json) |
| Newsletter | buggy | complete | 4 | failed signup clears email and name; closing the dialog does not return focus | 3/3, 3/3 | 73.5 s | [report](20261027-145650-23ec44-newsletter-buggy/report.json) |
| Release notes (`composer`) | fixed | complete | 2 | none | – | 40.2 s | [report](20261027-150032-571a68-composer-fixed/report.json) |
| Newsletter | fixed | complete | 2 | none | – | 41.1 s | [report](20261027-150244-08c648-newsletter-fixed/report.json) |

**Result:** 4/4 known held-out bugs verified with live Muse plans, 0 false alarms on
the fixed builds, 12/12 model calls successful (HTTP 200, reported model
`muse-spark-1.3`). The rules-only planner finds 2/4 of these bugs
(`eval/results-heuristic.md`).

Each report lists, per call, the purpose (plan, follow-up plan, diagnosis), UTC start
time, latency, input/output tokens, HTTP status, transport (`network`), endpoint host
and the model name the API returned. `summary.json` collects the same figures.

## How they were produced

- Faultline 0.4.1 (installed by the Windows setup, commit `1c8575c`) on the developer's
  Windows PC, started with the desktop launcher; the API key came from the user
  environment and never appears in the reports.
- Settings: demo app selected in the UI, **Live Muse API**, **Spark**, default goal and
  two rounds (initial plan plus one Muse follow-up based on the browser results).
- The reports are byte-for-byte the files served by `/api/hunts/<id>/report`.
  The `screenshot`, `trace`, `spec_file` and `repro_file` paths point to that PC and are
  not part of the repository.

SHA-256 of the stored reports:

```
9f3a98f827bceb98c9b38faeffa25c29261c96029ddb4e43527c73cb98a64727  20261027-145146-2c85b8-composer-buggy/report.json
1ad7b67d651129da73eeb3b333773d844cab6fbe007391841f96b8da6914ded4  20261027-145650-23ec44-newsletter-buggy/report.json
cce5721595c9b53c6c71b588bce8f4560e0daed453d28b35cf66bcce170ec68f  20261027-150032-571a68-composer-fixed/report.json
6553d7343eed98dac38bc92a454169f3d67e68a44b093dc04a3c986dec732e61  20261027-150244-08c648-newsletter-fixed/report.json
```

## Demo video and screenshots

The [demo video](https://www.youtube.com/watch?v=Ks4pQ3-GUso) and the screenshots in `docs/img/live-*.png` come from
a fifth live run on the buggy release-notes app (started 15:10 UTC, same settings): 2 verified failures, 4 successful
model calls, shown in its Model API evidence panel. Its report was not exported, so it is not counted above.

## Limits

One live run per app and build. Model output varies between runs, so this shows that
the live loop works end to end and reproduces the recorded-plan result on the held-out
apps; it is not a measured success rate.
