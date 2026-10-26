# Readiness review

The current assessment is **about 7/10 for competition readiness**, not a jury score, a win probability or a guarantee. The subjective weighted assessment and its assumptions are stored in `eval/verification/readiness-assessment.json`. Verification results are recorded separately in `eval/verification/release-checks.json`; passing tests are not a measure of model accuracy.

## Strengths

Faultline has a coherent evidence loop: hypothesize, test, reduce, confirm, explain and export. The model is separated from the verifier. The fixed twin and the exact generated test make the demonstration inspectable. New CI and saved-session support give developers a practical integration path. The notebook interface makes phases and findings understandable without adding a complex frontend toolchain.

The independent review led to concrete repairs: incomplete model follow-ups no longer look like successful CI, local API host/origin checks were tightened, dynamic password fields are refused, malformed diff coordinates are rejected, and source changes or missing experiment coverage prevent a complete comparable evaluation. Historical evidence and demo files remain intact.

## Why it is not a top-readiness score yet

| Area | Assessment | Main gap |
|---|---:|---|
| Impact | 6/10 | No independently reviewed real defect in a meaningful network-backed upstream app. |
| Meta use | 7/10 | Live repeated API behavior and actual patch quality have not been measured. |
| Technical execution | 8/10 | Strong testable boundaries, but authenticated transport, discovery and invariant coverage remain deliberately narrow. |
| Demo | 7/10 | Working UI and replay flow; final real Meta video and submitted artifacts are still missing. |

The resulting weighted readiness estimate is 6.9/10. It is deliberately approximate and should change with evidence rather than extra feature count.

## Highest-value next improvements

1. **Complete the live model comparison.** Run a predeclared set of independent attempts with the owner's key. Report every attempt, per-bug coverage, failed calls, follow-up behavior, latency and observed usage. Compare Muse Wonder separately if useful.
2. **Demonstrate a real development outcome.** Pin an unmodified network-backed upstream revision, define expectations before planning, investigate a reproduced finding, and show the exported test failing before and passing after a reviewed fix. If no bug is found, report that result and the measured coverage honestly.
3. **Exercise the review-only fix loop with Meta.** Mock tests prove consent and validation behavior, not that a generated patch repairs anything. Record selected-source consent, the actual proposal, manual application and the same failing test replayed.
4. **Finish the submission experience.** Apply the supplied participant Guide: prepare the required public repository and three-minute video, preserve original Git history, and verify the ambiguous build-start date and bonus stacking with the organizer. Publish only with the owner's instruction.
5. **Add open weights only for a validated reason.** The adapter is implemented. A real checkpoint-backed deployment and comparable saved evaluation are needed before calling it successful or claiming a prize condition.

## What we intentionally did not expand

Offline phases and new experimental actions were deferred because they would change the vocabulary and evaluation surface while the core evidence was still being strengthened. No new held-out app was invented or exposed to the planner. The current upstream probes remain separate from the held-out benchmark. The owner can reconsider these features after the live evidence gaps are closed, subject to the planned feature freeze.

The priority is evidence that an unfamiliar user's app benefits from Faultline. More speculative features would not resolve the main remaining uncertainty.
