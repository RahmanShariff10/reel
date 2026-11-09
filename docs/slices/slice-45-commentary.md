# Slice 45 — Commentary keywords

**Owner:** Dev A · **Sprint:** F3 · **Target week:** 5–6 · **Depends on:** 44

*Replaces slice 32; now a core signal.*

## Module
`audio`

## What to build
The `commentary` stage writes `commentary.json`, following ARCHITECTURE.md: language check, faster-whisper (int8, CPU) on candidate windows only, keyword matching by type with the documented precedence, and `signals.commentary` to switch it off. The transcriber sits behind an interface so tests use a stub.

## Acceptance criteria
- [ ] Given `signals.commentary: false`, then nothing is transcribed and the stage writes empty results.
- [ ] Given stub transcripts containing "what a save", then the moment's type is `chance` with that keyword.
- [ ] Given "red card" and "what a save" in one window, then the type is `red_card`.
- [ ] Given a stub language of `fr`, then no keywords are produced and the language is recorded.
- [ ] Given a run, then only candidate windows are transcribed (verified by call arguments), never the full audio.
- [ ] Human: on a full real match, the stage takes ≤ 10 min.

## Out of scope for this slice
Non-English keywords.

## Human review required?
No.
