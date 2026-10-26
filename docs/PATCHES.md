# Review-only repair proposals

After a failure has been confirmed in every confirmation run, select the relevant source files in its finding sheet and explicitly consent to sending those files to the currently selected Meta model. The model receives the minimized steps, required disturbances, failed invariant and only the selected source contents.

The earlier "Let Muse read this page's own scripts" option controls diagnosis. It does not authorize a later patch request. The patch action has its own explicit source selection and consent.

## Review flow

1. Select supported source files and review their names before sharing. Files must use relative paths inside your project.
2. Confirm consent and request a proposal.
3. Read the returned unified diff and explanation. Faultline does not execute code, write the patch to your project or apply it.
4. Apply only the changes you approve using your own editor.
5. Restart your app if needed, then use **Re-test this build** with the fixed build's URL. Replay checks the existing counterexample; a pass does not prove the app has no other bugs.

The UI can display a rejection when the evidence or source is insufficient. A generated diff is labeled an unverified proposal until a separate replay succeeds. Even a passing replay does not establish general patch correctness: review the change and run your application's tests.

## Boundaries

The backend accepts only explicitly supplied text. It never reads a local path from the request and never traverses a repository. Hidden files, credential files, absolute paths, traversal, unsupported extensions and overly large source selections are refused. A credential-pattern check rejects suspected keys and private-key material before an API request; it is a guardrail, not a guarantee that arbitrary source is secret-free. Review files before sharing them.

The model may edit only a submitted source file. New files, deletions, renames, binary patches and mismatched or overlapping hunks are rejected. Hunk context and positions are checked against the selected original text in memory. No model-written command or code is run, and a valid hunk is not treated as evidence that the repair works.

Source hashes identify the submitted version (after normalizing line endings). Patch requests are not automatically persisted to hunt reports. Save a reviewed diff yourself if you need it later. Source contents and provider error bodies are not added to model-call telemetry.

The module's contract is:

```python
await propose_patch(settings, counterexample, files, consent=True)
```

`files` contains objects with `path` and `content`. A response has `status` equal to `proposed` or `rejected`, plus `diff`, `reason`, `model` and `files`. Successful proposals include `review_only: true`, `verified_fix: false` and `source_sha256`. Only confirmed failures with at least three successful confirmation reproductions are eligible.

The source and diff limits are enforced in `faultline/patches.py`; the HTTP endpoint can impose stricter request limits. Unsupported formats fail closed with a reviewable reason.
