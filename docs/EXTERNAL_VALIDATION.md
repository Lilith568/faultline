# Upstream compatibility probes

Faultline was run against unmodified, locally served copies of TodoMVC and 2048.
These are exploratory compatibility checks, not a real-world accuracy benchmark.
The runs used the rules-only planner; no Meta API call was made. No upstream bug
was established by these probes. In particular, an absence of applicable
experiments is not evidence that an application is correct.

## Sources

| Application | Upstream revision | Served directory | License |
|---|---|---|---|
| TodoMVC JavaScript ES5 | `tastejs/todomvc` at `ff43b02e59dfa604386bb382034b2cd07c2bcd8a` | `examples/javascript-es5/dist` | [MIT](https://github.com/tastejs/todomvc/blob/ff43b02e59dfa604386bb382034b2cd07c2bcd8a/license.md) |
| 2048 | `gabrielecirulli/2048` at `478b6ec346e3787f589e4af751378d06ded4cbbc` | repository root | [MIT](https://github.com/gabrielecirulli/2048/blob/478b6ec346e3787f589e4af751378d06ded4cbbc/LICENSE.txt) |

Both source revisions and archive SHA-256 hashes are recorded with each result.
The TodoMVC build artifacts ship in that upstream revision; no build step or
application code change was needed. Upstream sources are not bundled with
Faultline and no vendor code was added to its planners or prompts.

## What actually ran

| Application | Inventoried controls | Planned / applicable experiments | Confirmed failures | Interpretation |
|---|---:|---:|---:|---|
| TodoMVC | 7 | 1 / 1 | 0 | A narrow input-preservation check passed; not broad app coverage. |
| 2048 | 4 | 0 / 0 | 0 | Inconclusive: the planner had no applicable experiment. |

Raw results, including the exact Faultline source hashes used:

- [TodoMVC result](../eval/external/20261026T225927.618781Z-69b54250/result.json)
- [2048 result](../eval/external/20261026T225933.652627Z-2d29f87d/result.json)

The TodoMVC experiment delayed `GET /learn.json`, an auxiliary learning-metadata
request, while text was entered into the new-todo field. The field retained that
text. This does **not** demonstrate coverage of a backend save race, order
submission, or application data synchronization: this upstream implementation
uses in-memory storage. The report includes the complete experiment and observed
request timeline so the narrow claim can be inspected.

On 2048, discovery inventoried attribution links but not the application's
script-driven anchors without `href` or accessible button roles. No experiment
ran. This exposes a current limitation in discovery and in the available
form-oriented invariants. The external runner returns an inconclusive exit code
for this case rather than turning it into a success.

## Independent fixture checks and failed attempts

The [final fixture sanity check](../eval/external/smoke-20261026T230037.477670Z-13e8dd48.json)
established that the downloaded apps actually function locally:
TodoMVC supports creating a todo on blur, completing and clearing it, and resets
its documented in-memory store on reload. 2048 starts a board, accepts keyboard
moves, persists game state, and resets through New Game.

These are manually authored Playwright checks in
`scripts/check_external_fixtures.py`, not discoveries made by Faultline or Muse.
Earlier failed attempts remain in `eval/external/`:

- `20261026T225820.139593Z-0e5e6def` and `20261026T225820.905486Z-bc0d0bf6`
  failed because the execution environment isolated the local server and browser
  in different network namespaces. The associated smoke file records the same
  connection failures.
- `smoke-20261026T225927.434549Z-ebfaff28.json` assumed that Enter commits a new
  TodoMVC item. This pinned implementation binds creation to the input's change
  event instead.
- `smoke-20261026T230036.391821Z-52758533.json` assumed that Todos survive reload.
  The upstream README and `store.js` explicitly use in-memory storage; the final
  check tests that documented behavior. Neither assumption failure is claimed as
  an upstream bug.

The app code and Faultline's planner were not changed to make these checks pass.

## Reproduce

From a directory beside the Faultline repository:

```bash
git clone https://github.com/tastejs/todomvc.git
git -C todomvc checkout ff43b02e59dfa604386bb382034b2cd07c2bcd8a
git clone https://github.com/gabrielecirulli/2048.git
git -C 2048 checkout 478b6ec346e3787f589e4af751378d06ded4cbbc
```

Run each server in a separate terminal on your machine:

```bash
python -m http.server 8181 --bind 127.0.0.1 --directory todomvc/examples/javascript-es5/dist
python -m http.server 8182 --bind 127.0.0.1 --directory 2048
```

From Faultline, with its virtual environment active:

```bash
python scripts/check_external_fixtures.py
python scripts/evaluate_external.py http://127.0.0.1:8181/ --application todomvc --repository https://github.com/tastejs/todomvc --commit ff43b02e59dfa604386bb382034b2cd07c2bcd8a --license-url https://github.com/tastejs/todomvc/blob/ff43b02e59dfa604386bb382034b2cd07c2bcd8a/license.md --archive-sha256 22fd7c5251b636773561cc0ab606896f48c8dbcad80e79b427989bfc0e134718
python scripts/evaluate_external.py http://127.0.0.1:8182/ --application 2048 --repository https://github.com/gabrielecirulli/2048 --commit 478b6ec346e3787f589e4af751378d06ded4cbbc --license-url https://github.com/gabrielecirulli/2048/blob/478b6ec346e3787f589e4af751378d06ded4cbbc/LICENSE.txt --archive-sha256 4f3e35b3b9124c5a5c16231b71684288d8d781c2d534754f6b36119336231e2e
```

The recorded archive hashes refer to GitHub's downloaded source tar archives,
not to a working-tree hash. The supplied revision metadata should always match
the source actually served. Keep local apps disposable: discovery performs
ordinary UI interactions.

Every invocation creates a fresh result directory and keeps earlier results.
Exit codes are: `0` for completed probes with applicable experiments and no
confirmed counterexample; `1` for confirmed counterexamples needing review;
`2` for errors, no applicable experiments, or source changes during the run.
No public site is tested and the runner disables model calls regardless of the
operator's API-key configuration.

## What is still missing

An authenticated, network-backed upstream app with meaningful business
invariants and an independently reviewed bug remains a stronger validation
target. Live Muse runs on such an app have not been performed. The compatibility
results above must not be merged into the held-out demo benchmark or cited as
real-world bug-detection accuracy.
