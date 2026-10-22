# ship-kit

A starting point for AI-assisted builds: structure the thinking (research → PRD → architecture → sprints → slices) so a coding agent can execute cleanly, instead of improvising from a single chat.

As AI coding agents handle more of the actual implementation, the human's job shifts upstream — to defining requirements and architecture precisely enough that an agent can build the right thing without guessing. `ship-kit` is a lightweight set of doc templates and a `CLAUDE.md`/`AGENTS.md` for exactly that: minimal structure, no heavy process, designed to stay out of your way until you actually need it.

## Use this template
Click **"Use this template"** above to create a new repo with this structure already in place. Rename it, then start at Phase 0 below.

## What's inside

```
/docs
  research.md          → problem framing, who has it, what exists
  PRD.md                → goal, users, features, explicitly out of scope
  ARCHITECTURE.md       → stack, system flow, modules, API contract, constraints
  /decisions
    ADR-001-xxx.md       → only when a choice is non-obvious (opportunistic, not mandatory)
  /sprints
    sprint-01.md
  /slices
    slice-01-xxx.md
CLAUDE.md / AGENTS.md    → house rules for coding agents working in this repo
.env.example
```

## Workflow (short version)

1. **Research** — talk it through with web AI, write `docs/research.md`
2. **PRD** — lock goal/users/features/out-of-scope before moving on
3. **Architecture** — stack, flow, modules, constraints; ADR only if genuinely non-obvious
4. **Sprints** — break architecture into feature-level chunks (`docs/sprints/`)
5. **Slices** — break each sprint into agent-session-sized units with testable acceptance criteria (`docs/slices/`)
6. **Execute** — hand a slice to a coding agent, it opens a PR referencing the slice ID, human review required for auth/payments/data-deletion/infra/secrets, merge, deploy

A matching Notion page template mirrors this `/docs` structure for commenting and status-tracking — the repo is the canonical source, Notion is the visible/collaborative mirror.

## Not included by default
CI, Docker, and release pipelines are intentionally left out — add them only when a project's actual pain calls for it, by asking the coding agent to set it up. See `CLAUDE.md` / `AGENTS.md`.

## License
MIT — see `LICENSE`.
