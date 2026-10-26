# Demo recording plan

The owner-supplied participant Guide requires a three-minute demo video and a public repository. This requirement was checked against the supplied copy, not a directly authenticated page; see `eval/participant-guide-review.json`. Record a real run before editing the video. Show only the features, code and functionality built during the hackathon, and identify those contributions clearly. Label any cuts, prerecorded model plan or time compression; do not fabricate results.

| Segment | Show | Suggested narration |
|---|---|---|
| Opening | A typed input lost after a delayed response | "Your happy-path tests pass. A slow response can still erase a user's work." |
| Experiment design | Local target, goal, configured Meta model and hypotheses | "Faultline asks Muse what could fail and which experiment would distinguish the causes." |
| Verification | Live phase bar, network fault, deterministic check | "Playwright executes the experiment. The model does not grade its own answer." |
| Evidence | Expected versus observed, screenshot, reduced steps and confirmations | "This is a reproducible counterexample, with the smallest experiment we found." |
| Fix loop | Generated test; optional reviewed diff; human applies a fix | "Keep the regression test. A proposed patch is for review only; Faultline never applies it." |
| Re-test | Exact counterexample against the fixed build | "The same check now passes on this build. That is evidence for this fix, not a proof of all correctness." |
| Close | Evidence files, CI use and honest limitations | "Every evaluation is saved, including failures and fallbacks. Our next validation target is a network-backed upstream app." |

Use a real Meta-powered run for the primary presentation when available. Keep a clearly labelled recorded-plan replay as a resilience option, not as a hidden replacement for the live API. Show no keys, login state, private user data or unrelated desktop content.

The strongest final story would replace the bundled opening example with a verified defect in an unmodified upstream revision. Do not claim that story before it has been demonstrated.

Before submission, check that the public repository and video links are accessible and that all human contributors are listed. Resolve the Guide's October 26 kickoff versus October 27 building-period boundary before describing the initial code as verified eligible work. Keep original timestamps and Git history rather than reconstructing them.
