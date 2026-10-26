# Submission draft

Track: Indie Developer Track  
Problem statement: Push the Frontier  
Team: Faultline (solo owner; verify accepted participant details)  
Public repository URL: pending (required by the supplied Guide)  
Three-minute demo video URL: pending (required by the supplied Guide)  
Final model configuration and live evidence: pending

This is a draft, not a submitted entry. The owner supplied the participant Guide: it requires a public repository, an accessible three-minute demo video and clear identification of event-built contributions. These requirements were checked against that text copy, not a directly authenticated page. Check current organizer updates and actual portal fields before use. Source provenance and remaining questions are recorded in `docs/RULES_REVIEW.md` and `eval/participant-guide-review.json`.

## Project description

Faultline breaks a local web app under controlled timing and request failures, then exports the failing regression test. It targets lost edits, stale results and duplicate actions that happy-path tests often miss.

A Meta Muse model reads the discovered UI and proposes falsifiable hypotheses. A closed validator limits its experiments to known controls, synthetic input and observed request patterns. Playwright executes each experiment and evaluates the invariants independently. Muse can review that evidence and propose follow-up experiments. Reproducible failures are reduced, checked repeatedly and diagnosed before export.

The evidence sheet shows expected and observed behavior, a screenshot, the reduced sequence and the actual Playwright test. Developers can request a review-only patch from explicitly selected source, apply any fix themselves and replay the same counterexample against the repaired build. Faultline never executes or automatically applies generated patches.

CI gates and JUnit reports make confirmed failures actionable in development. Saved Playwright state supports a documented subset of authenticated local applications. Every evaluation attempt is retained, including errors and rules fallbacks.

## Meta's role

Meta models perform experimental design, evidence-informed follow-up and diagnosis. They can also propose a bounded source patch after separate developer consent. Browser checks decide whether an invariant fails; the model does not evaluate its own answer. This makes Meta's reasoning useful without treating an explanation as proof.

The hosted configuration uses Muse Spark by default and can select Muse Wonder. An optional compatible HTTP adapter supports documented Meta open-weight models. The implementation and mocked tests do not establish live endpoint quality or prize eligibility; only claim those after recording actual runs.

## Evidence that may currently be cited

Historical raw files `eval/results-heuristic.*` record the rules baseline finding 6/6 known dev bugs and 2/4 held-out bugs, with no findings on the corresponding fixed builds. `eval/results-recorded.*` records saved Muse Spark plans finding 4/4 held-out bugs, with no findings on those fixed builds. These are small purpose-built apps and the Muse evidence is a recorded-plan replay, not a completed live API comparison.

New revision checks are linked from `eval/verification/release-checks.json`. Upstream TodoMVC and 2048 probes are narrow compatibility evidence only; no real upstream bug was established. They are not included in the held-out detection score.

Before submission, replace this paragraph only with claims supported by the final saved live evaluation attempts. Report incomplete runs, fallbacks, per-bug coverage, latency and observed usage. Do not select only the best repeated run or turn absent coverage into a clean result.

## Why this matters

The intended users are developers who need a reproducible explanation for a timing-sensitive UI failure. A failing regression test, reviewable evidence and an explicit fixed-build replay make a finding usable in a development workflow. The next impact proof is a real, independently reviewed defect in an unmodified network-backed upstream app; it has not been established yet.

## Development provenance

The original author used Anthropic Claude. ChatGPT (OpenAI) assisted with this separate revision. Runtime model calls remain Meta only. Details and the original-history limitation are disclosed in `docs/PROVENANCE.md`.

## Feedback fields

The owner must supply their actual experience with Meta and any partner services. Do not invent service usage, feedback, customer validation or model results.

## Required submission checks

- Provide the public repository URL and an accessible three-minute video link; list all human contributors.
- Identify the specific features, code and functionality created during the event. Preserve the original Git history and disclose development assistance.
- Resolve the Guide's October 26 kickoff versus October 27 building-period boundary before certifying the initial work's eligibility. The original author declares work began after kickoff; this snapshot cannot independently verify the dates.
- Submit by November 5 at 03:00 Berlin time, corresponding to the Guide's November 4 at 21:00 Eastern deadline.
- Claim the Open Weight award condition only after a real eligible Muse Glimmer/Spark Open deployment and run can be verified. For Baseten, the supplied Guide specifies `meta-models/muse-spark-open-1026`.
- Treat the Agentic and Creative awards as judged categories, not automatic qualifications. Wonder use alone does not establish a creative project. Prize stacking remains unspecified.

For the optional Viral award, a demo post on X and its submitted platform link are required. The Guide counts engagement until November 8 EOD; confirm the exact timezone. Community voting opens November 9 and its winner is announced November 16. No social post, publication or competition submission has been performed by preparing this draft.
