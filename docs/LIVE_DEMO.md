# Record a live Meta API demo

Live runs on both held-out apps were recorded on 2026-10-27 (4/4 known bugs, 0 false
alarms, 12/12 successful model calls); see [`eval/live/2026-10-27`](../eval/live/2026-10-27/README.md).
The steps below reproduce such a run on your own key.

## Start on Windows

From a fresh checkout, install once in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m playwright install chromium
```

Then run:

```powershell
.\.venv\Scripts\python.exe .\scripts\start_local_demo.py
```

The launcher uses your existing `MODEL_API_KEY` or local `.env`. If neither
contains a key, it prompts without displaying what you type. The key is used
by the local server, never sent to the browser or committed to GitHub. The
launcher selects the hosted Meta API, opens the demo page in your browser
and restores the process environment when the server exits. Press **Start hunt**
to make the model calls. No request starts just from opening the browser.

Manual setup: copy `.env.example` to `.env` only if you do not already have
one, put your Meta key in `MODEL_API_KEY`, keep
`FAULTLINE_MODEL_BACKEND=meta`, `META_BASE_URL=https://api.meta.ai/v1` and
`META_MODEL=muse-spark-1.3`, then start:

```powershell
.\.venv\Scripts\python.exe -m faultline serve
```

API calls use your Meta account and may consume credits. Get/manage the key
in the [Meta Model API dashboard](https://dev.meta.ai/); official
[quickstart](https://dev.meta.ai/docs/quickstart) and
[Chat Completions documentation](https://dev.meta.ai/docs/protocols/chat-completions).

## Run and check the evidence

1. Open `http://127.0.0.1:8000` and choose **Release notes**, **Buggy build**,
   **Live Muse API**, and **Spark**.
2. Set the goal to `Drafts must survive switching editor tabs and publishing must not submit twice.`
3. Start the hunt. The app calls Meta for the first plan, a follow-up based
   on browser results, and a diagnosis for each confirmed finding. The
   default two rounds permit a follow-up; a valid empty follow-up is allowed.
4. In **Model API evidence**, expand **Model-call details**. Check the returned model, UTC timestamps,
   response statuses, token counts when provided, and the successful network
   call count. Download the report JSON alongside the exported test.
5. Show one finding, the expected and observed value, its confirmation runs,
   then re-test the same counterexample against the fixed build.

In the UI, **Live Muse API** requires the model: a missing key, an initial
plan with no valid experiments, an API error, or a failed diagnosis stops the run instead of silently
switching to rules or a template. **Rules only** and **Recorded Muse plan**
remain separate choices. Failed runs retain a partial report.

The CLI has the same strict option:

```powershell
.\.venv\Scripts\python.exe -m faultline hunt "http://127.0.0.1:8000/demo/composer.html?mode=buggy" --planner meta --require-live --rounds 2 --goal "Drafts must survive switching editor tabs and publishing must not submit twice."
```

`live_api.status=complete` means the strict run completed with accepted
network Meta responses and no planner/diagnosis fallback. Injected test
transports and recorded plans do not receive that status. These are local
runtime records, not independent provider attestation. A complete API run
does not by itself mean every experiment was applicable or that any bug was
found: inspect the actual invariants and findings too.

## A three-minute cut

| Time | Show |
|---|---|
| 0:00–0:15 | The user problem: typed work disappears or a double-click submits twice. |
| 0:15–0:35 | Target, goal, Live Muse API selection and model. |
| 0:35–1:20 | Fresh hypotheses and browser experiments; then the evidence-based follow-up. |
| 1:20–2:00 | A confirmed failure, minimal steps and the model diagnosis. |
| 2:00–2:35 | Exported test and the same counterexample passing on the fixed build. |
| 2:35–2:55 | API-call evidence, real-world use and public repository. |

Record first, then edit to at most 3:00. If waiting is shortened, label that
cut and retain the original run report; do not present a recording or an
injected response as a new API call. Actual model outputs and timing vary,
so no particular finding or duration is guaranteed. If the live run fails,
show the failure honestly and fix it before recording the final take.

After uploading the new video, update the README and `docs/SUBMISSION.md`
with its new URL and actual duration. Keep the old video labelled as replay.
