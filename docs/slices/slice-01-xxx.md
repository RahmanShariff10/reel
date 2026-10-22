# Slice [0X] — [Short name]

> One slice = one agent session (one sitting, one context window). It's fine if it produces 2–3 small commits/PRs, not just one — the boundary is coherence, not commit count. If the acceptance criteria below stop being checkable as a single unit, split it into two slices.

## Module
Which module (from Architecture) does this belong to?

## What to build
Plain description — specific enough that the agent isn't guessing, short enough to read in 30 seconds.

## Acceptance criteria
Written as testable statements. This IS the test plan — no separate testing doc needed.

- [ ] Given ..., when ..., then ...
- [ ] Given ..., when ..., then ...

## Mockup / reference (if UI-facing)
Link to Figma / image / rough sketch — whatever exists. Skip if this slice has no UI surface.

## Out of scope for this slice
Anything adjacent that might tempt the agent to over-build. Optional — only if genuinely likely to be assumed.

## Human review required?
Default: no, unless this touches auth, payments, data deletion, infra/CI, or secrets — in which case: yes.