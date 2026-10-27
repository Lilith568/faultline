# Submission texts (Cerebral Valley form)

Track: Indie Developer Track
Problem statement: Push the Frontier
Team name: Faultline
Team members: Kevin Moritz (@Lilith568) — sole developer and submitter (solo)
Public GitHub repository: https://github.com/lilith568/faultline
Demo video: https://www.youtube.com/watch?v=V_Kpp8x-xhM (3:18; recorded Muse-plan replay)

## Project Description

Faultline breaks your web app on purpose, then hands you the failing test. Happy-path tests pass, yet real users on
slow networks lose work: a late response overwrites what they typed, search shows results for "ca" after they typed
"cat", a double-click places two orders, a failed save wipes the form. These bugs depend on timing, so they hide on
localhost and in test suites.

Faultline explores a local app with Playwright. A Meta Muse model reads the page inventory and the developer's goal
and proposes competing, falsifiable hypotheses, each with one experiment: steps, a network fault to inject and the
invariants that must hold. A strict validator only admits known controls, synthetic input and observed requests.
Playwright runs every experiment with the injected faults and decides pass or fail; the model never grades itself.
Muse then reads the verified results and designs follow-ups. Every failure is minimized, re-run three times and
attributed by removing each injected fault. Muse writes a diagnosis from the screenshot, the request timeline and,
if the developer allows it, the page source. Faultline exports a ready-to-run Playwright Test spec that fails while
the bug exists, and one click replays the same counterexample against the fixed build.

It fits into a developer's workflow: CI exit codes and JUnit reports, saved Playwright login state for local apps
behind a sign-in, and review-only fix proposals that Muse writes from source files the developer selects. Faultline
never applies or runs a generated patch; the developer applies it and the replay shows whether the bug is gone.

On six demo apps (each with a buggy and a fixed build), a rules-only baseline finds 6/6 bugs in the dev apps but only
2/4 in the held-out apps. Plans from muse-spark-1.3 find 4/4 in the held-out apps, with zero false alarms on the fixed
builds. The same 4/4 with zero false alarms was reproduced in live runs against the hosted Meta Model API
(12/12 calls successful, `eval/live/2026-10-27`). All results, every evaluation attempt and the recorded model
answers are in the repository.

## Describe your use of Meta products to build the submitted project

Faultline calls the Meta Model API (Chat Completions, structured output with a strict JSON schema) with muse-spark-1.3
by default and muse-wonder-1.0 as an option. Muse is used at four points: (1) it turns the discovered page inventory
and the developer's goal into competing hypotheses and executable experiments in a closed vocabulary, (2) it reads
Playwright-verified results and designs a follow-up round, (3) it diagnoses each verified failure from a screenshot of
the failing state and the request timeline (multimodal input), plus the page's inline scripts if the developer allows
it, and (4) on request it proposes a fix as a unified diff for source files the developer selects. An optional adapter
runs the same loop on Meta's open-weight models (Muse Spark Open, Muse Glimmer) through an OpenAI-compatible endpoint.
The Meta playground was used to test the planner prompt; those real Muse plans are stored in the repository and can be
replayed in the UI and from the command line without a key. Live runs on 2026-10-27 called the hosted API for every
plan, follow-up and diagnosis; their per-call evidence (timestamps, latency, tokens, HTTP status, returned model) is in
`eval/live/2026-10-27`.

## Why are Meta's models important to your solution?

Finding a race condition is an experimental-design problem: which request to slow down, what to type before it lands,
which invariant would expose the bug and distinguish it from other explanations. Rules only cover patterns someone
coded in advance; on our held-out apps the rules-only planner missed two of four bugs, and Muse's plans found all four.
Muse also closes the loop: it adapts experiments to verified evidence, explains the root cause in the developer's own
code and drafts the fix. Because Playwright, not the model, judges every experiment, Muse can be creative without the
tool ever reporting a bug that does not reproduce.

## Provide feedback from your experience using Meta products

Written by the submitter in the form.

## Provide feedback from your experience using partner technologies

Written by the submitter in the form.
