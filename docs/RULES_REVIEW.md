# Rules and participant-guide review

This review distinguishes two sources. It is not a declaration of full eligibility, guaranteed prize eligibility or complete compliance.

- The public [event details and embedded Official Rules](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details) were retrieved on 2026-10-26 at 22:56:41 UTC. Their source metadata and extracted-content hash remain in [`eval/rules-review.json`](../eval/rules-review.json), an unchanged historical review.
- The owner subsequently supplied a complete text copy titled **Meta Global AI Developer Hackathon Participant Guide**. Its exact-byte hash, review time and structured facts are in [`eval/participant-guide-review.json`](../eval/participant-guide-review.json). The findings below were checked against that supplied copy, not against a directly authenticated page. The copy has no stated revision date. The full Guide is not bundled.

## Requirements established by the supplied Guide

The project must incorporate Meta models and fit a listed theme. Faultline targets the software portion of **Push the Frontier**; the organizer determines eligibility.

The repository must be public. The submission requires an accessible three-minute demo video, an accessible repository link and the contributors listed on the submission page. Teams submit one project through their representative; solo entries are allowed, with at most four participants per team.

Only work built during the event may be presented. The demo must identify the features, code and functionality created during the hackathon. The Guide explicitly permits startups to extend an existing codebase when they identify their new contribution; it does not state the same exception for Indie entrants. Generic project examples include simple education chatbots and basic RAG; the prohibited examples also cover medical advice and political or war-related projects.

The submission deadline is **November 4 at 21:00 Eastern Time**, equivalent to **November 5 at 03:00 in Berlin**. Late submissions are excluded. November 3 is the last full day for submission questions.

## Judging and awards

Theme fit and meaningful Meta use first receive a pass/fail check. Projects then receive weighted scores: impact 30%, Meta tooling 25%, technical execution 20%, and demo 25%. The highest five projects per track advance to live final judging under the same rubric.

Indie awards by rank are $150,000, $100,000, $75,000, $50,000 and $25,000. The Guide allocates these additional awards:

| Award | Amount | Required evidence or judging basis |
|---|---:|---|
| Most Viral Project | $20,000 | Publish a demo on X and submit its post link through the platform; likes, reposts and comments count until November 8 EOD. Confirm the exact cutoff timezone. |
| Best Build on Meta Open Weight Models | $10,000 | Actual use of Muse Glimmer or Muse Spark Open on participant hardware or partner inference; infrastructure verification is required. An adapter alone is insufficient. |
| Community Vote | $10,000 | Public-gallery votes, limited to one vote per verified account. Voting opens November 9; the winner is announced November 16. |
| Best Agentic Use-Case | $5,000 | Autonomy, effective task completion and practical usefulness. |
| Best Creative Build | $5,000 | An original creative project using Muse Image or Muse Wonder, judged on originality, execution and model contribution. Merely selecting Wonder is insufficient. |

The earlier public legal terms leave bonus allocation to the organizers and say bonus awards do not reduce track awards. The supplied Guide adds category details but does **not explicitly authorize prize stacking**. Do not calculate a guaranteed maximum for one project. Its Community Vote announcement date is more specific than the earlier legal text's approximate additional-prize announcement timing; check subsequent organizer announcements.

## Model and partner details

The Guide names the Muse Spark series, Muse Wonder, Muse Image, Muse Voice Transcribe and SAM 3.1 through Meta Model API, and Muse Glimmer/Muse Spark Open as open-weight options. Meta model use is required; this project's stricter Meta-only runtime policy remains our implementation choice.

For Baseten, the Guide specifically replaces the general documentation identifier with **`meta-models/muse-spark-open-1026`** for the hackathon. A live deployment and recorded run are still needed before claiming that path works or satisfies an award condition. Credits and partner limits are recorded in the evidence JSON; they are not cash prizes, and partner credits are discretionary.

## Timing and provenance still need resolution

The Guide schedules kickoff on **October 26**, but separately labels the building period **October 27–November 4**. The original author says Faultline began after the October 26 kickoff. The supplied text does not resolve whether that initial work satisfies the stated building-period boundary. Obtain the organizer's interpretation and preserve the original commit history; do not claim either automatic disqualification or verified compliance.

The recovered snapshot lacks the original Git history, so this review cannot independently establish initial creation times. The Guide also does not explicitly name ChatGPT/Claude as development assistants, explain switching the application idea, or authorize multiple stacked awards. The public legal text allows third-party technical help subject to ownership and rights; that is not a model-specific ruling. Check current participant updates and the actual submission form for additional conditions.

## Implementation choices

Preserve all evaluation attempts, distinguish recorded plans from live calls, keep runtime reasoning on Meta models, and disclose development assistance. Never apply generated patches automatically. Submit only claims backed by saved evidence; no real upstream defect or successful live open-weights run has yet been established in this revision.
