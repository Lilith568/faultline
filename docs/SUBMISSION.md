# Submission texts (Cerebral Valley form)

Track: Indie Developer Track
Problem statement: Push the Frontier
Team name: Faultline
Team members: the submitter only (solo)
Public GitHub repository: (link after publishing)
3-minute demo video: (link after recording)

## Project Description

Faultline breaks your web app on purpose, then hands you the failing test. Happy-path tests pass, yet real users on
slow networks lose work: a late response overwrites what they typed, search shows results for "ca" after they typed
"cat", a double-click places two orders, a failed save wipes the form. These bugs depend on timing, so they hide on
localhost and in test suites.

Faultline explores a local app with Playwright, then a Meta Muse model reads the page inventory and the developer's goal
and proposes competing, falsifiable hypotheses, each with one experiment: steps, a network fault to inject and the
invariants that must hold. Playwright runs every experiment with the injected faults and decides pass or fail; the
model never grades itself. Muse then sees the verified results and designs follow-ups. Every failure is minimized,
re-run three times, its cause is attributed by removing each injected fault, Muse writes a diagnosis from the
screenshot, request timeline and page source, and Faultline exports a ready-to-run Playwright Test spec that fails
while the bug exists and passes once it is fixed.

On six demo apps (each with a buggy and a fixed build), a strong rules-only baseline finds 6/6 bugs in the dev apps
and 3/4 in the held-out apps. Muse plans find 4/4 in the held-out apps, including the "draft lost when switching
tabs" bug no rule covers, with zero false alarms on fixed builds.

## Describe your use of Meta products to build the submitted project

Faultline calls the Meta Model API (Chat Completions, structured output with a strict JSON schema) with muse-spark-1.3
by default and muse-wonder-1.0 as an option. Muse is used three times per hunt: (1) to turn the discovered page
inventory and the developer's goal into competing hypotheses and executable experiments in a closed vocabulary,
(2) to read Playwright-verified results and design a follow-up round, and (3) to diagnose each verified failure from
a screenshot of the failing state, the request timeline and the page's inline source (multimodal input), returning
cause, impact, fix and the responsible code. The Meta playground was used to test the planner prompt; those real Muse
plans are stored in the repository and can be replayed without a key.

## Why are Meta's models important to your solution?

Finding a race condition is an experimental-design problem: which request to slow down, what to type before it lands,
which invariant would expose the bug and distinguish it from other explanations. Rules only cover patterns someone
coded in advance; on our held-out apps the rules-only planner missed a draft-loss bug that Muse's plan found on the
first try. Muse also closes the loop: it adapts experiments to verified evidence and explains the root cause in the
developer's own code. Because Playwright, not the model, judges every experiment, Muse can be creative without the
tool ever reporting a bug that does not reproduce.

## Provide feedback from your experience using Meta products

(Write from your own experience. Points observed while building: structured output with a JSON schema made plans easy
to validate; reasoning effort "medium" answered in about 15 s per planning call; the playground's JSON mode and
system instructions made prompt iteration fast; the OpenAI-compatible endpoint meant no SDK was needed.)

## Provide feedback from your experience using partner technologies

(Optional. Faultline did not use Fireworks, Modal or Baseten.)
