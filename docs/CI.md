# CI and authenticated local apps

Faultline can gate a development build using Playwright-confirmed failures. It is
not a proof that the application is correct: the checks cover the experiments
the planner was able to construct.

## CI command

Start the application locally, then run:

```bash
python -m faultline hunt http://127.0.0.1:8000/demo/checkout.html?mode=fixed --planner heuristic --ci --junit artifacts/junit.xml
```

For an actual Meta run, configure `MODEL_API_KEY` locally (or as a GitHub Actions
secret) and use `--planner meta --require-live`. Never commit the key. The strict option stops rather
than using rules or a template if a requested model step fails. See [live demo setup](LIVE_DEMO.md)
for API-call evidence and recording instructions.

| Exit code | Meaning |
|---|---|
| `0` | The hunt finished, at least one applicable invariant was checked, no experiment failed to execute, and no confirmed or inconsistent failure remained. |
| `1` | At least one failure was confirmed in all confirmation runs, with at least three runs. Other incomplete checks remain visible in JUnit. |
| `2` | Infrastructure error, no applicable checks, inconsistent reproduction, or an unsuccessful explicitly requested Meta planner/diagnosis. |

An initial failed experiment is a candidate, not a confirmed bug. JUnit marks
confirmed findings as failures, execution/completeness problems as errors, and
inapplicable or unconfirmed candidate experiments as skipped. An inconsistent
candidate also adds a completeness error. A run that falls back to rules is
never a green `--planner meta --ci` check.

The example in `.github/workflows/faultline-example.yml` is manually triggered
and runs a bundled fixed build without a model key. Adapt the server startup
and URL to your own checked-out application; use a clean test database and
synthetic accounts. CI is allowed to submit forms as part of an experiment.

## Reuse a signed-in development session

Create a state file in Playwright's interactive browser:

```bash
python -m playwright codegen --save-storage=.auth/state.json http://127.0.0.1:5173
```

Sign in yourself, then close the browser so Playwright writes the state. Keep
`.auth/` outside version control. Faultline never types into password fields.

```bash
python -m faultline hunt http://127.0.0.1:5173/settings --storage-state .auth/state.json --ci --junit artifacts/junit.xml
python -m faultline replay artifacts/HUNT_ID/cx1/repro.json --url http://127.0.0.1:5173/settings --storage-state .auth/state.json
```

Each discovery, experiment, confirmation and replay receives a fresh context
initialized with that state. Only cookies for the exact target host and
localStorage for the exact target origin are retained. The state is loaded
from a bounded local JSON file; it is not included in model messages, reports,
exported tests or console output. IndexedDB and sessionStorage are not imported.

Signed-in pages can show private data, so by default they are never sent to a model:
an authenticated hunt uses the rules-only planner and says so in the report. Add
`--send-signed-in-pages` to let the Meta model see the signed-in page inventory and
screenshots as well. The saved login state itself is never sent in either case.

Authenticated contexts block service workers, WebSockets, HTTP redirects and
cross-origin resource requests. Use the final page URL directly. The authenticated
transport supports ordinary HTTP request/response apps, not streaming responses.
This can prevent apps that require a separate API origin, redirects or a third-party
CDN from loading; serve dependencies through the local app origin for these runs.
Browser cookies are host scoped, not port scoped, so a state file is not an
isolation boundary between mutually untrusted services on the same host. Use a
dedicated synthetic account and a local app you control. Playwright traces are
disabled when authentication state is supplied because they may contain request
credentials. Screenshots and visible page content can still contain application
data, so review artifacts before sharing them.

The standalone exported Playwright spec does not embed authentication. Configure
`use.storageState` in your own Playwright configuration when running it against a
signed-in page. Use a fresh state file if the app has logged out or the session
has expired. An inapplicable run must not be treated as a fixed bug.

