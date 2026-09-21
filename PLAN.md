# Tokenshed — Build Plan

Source: `PRD: Tokenshed — a lightweight token-saving plugin for Claude Code` (Sep 21, 2026).

Tokenshed is a Claude Code plugin that blocks large whole-file reads via hooks
and reroutes them to a cheap, user-chosen OpenAI-compatible model, returning
only a short answer to Claude's context. This document is the overall build
plan: phases, dependencies between them, the target repo layout, and how the
PRD's requirement IDs map to each phase. Each phase has its own sub-plan in
`plans/`.

## Guiding constraints (apply to every phase)

- **Fail open.** Any hook or script error must let the original call through,
  never block a session.
- **No dependencies beyond Python 3.9+ stdlib.** No server, no database, no
  build step.
- **No shell string-building.** Subprocess args as arrays; JSON via a real
  serializer, never f-string concatenation.
- **Privacy by construction.** Files only ever go to `TOKENSHED_API_BASE`.
  No telemetry. Cache lives outside the repo (`~/.cache/tokenshed` by
  default).
- **Security of secrets.** `TOKENSHED_API_KEY` read from env only; never
  logged, printed, or echoed in error messages.

## Phases and dependency order

Phases are sequential — each one is a prerequisite for the next, matching the
PRD's "hooks-first" build order (enforcement before delegation, delegation
before packaging, packaging before benchmarking).

| # | Phase | PRD milestone | Depends on | Sub-plan |
|---|-------|---------------|------------|----------|
| 0 | Project foundations | — (pre-M1) | none | [plans/phase-0-foundations.md](plans/phase-0-foundations.md) |
| 1 | Hooks | M1: Hooks | Phase 0 | [plans/phase-1-hooks.md](plans/phase-1-hooks.md) |
| 2 | Worker scripts | M2: Workers | Phase 1 | [plans/phase-2-workers.md](plans/phase-2-workers.md) |
| 3 | Skills & packaging | M3: Skills and packaging | Phase 2 | [plans/phase-3-skills-and-packaging.md](plans/phase-3-skills-and-packaging.md) |
| 4 | Benchmarks & beta | M4: Benchmarks and beta | Phase 3 | [plans/phase-4-benchmarks-and-beta.md](plans/phase-4-benchmarks-and-beta.md) |
| 5 | v1.0 release | v1.0 release | Phase 4 | [plans/phase-4-benchmarks-and-beta.md](plans/phase-4-benchmarks-and-beta.md) (release checklist section) |
| — | Post-v1 (v1.x / v2) | Later | Phase 5 | [plans/phase-5-post-v1.md](plans/phase-5-post-v1.md) |

Estimated timeline: ~4 weeks part-time, one phase per week (Phase 0 folds
into the front of Week 1 alongside Phase 1).

## Target repo layout

```
tokenshed/
├── .claude-plugin/        # Plugin and marketplace manifests
├── hooks/                 # Hook registration plus the Read and Bash hooks
├── scripts/               # bulk-read, code-write, shared API helper
├── skills/                # bulk-reader and code-writer skill files
├── commands/              # The /tokenshed:doctor command
├── evals/                 # Hook test cases, stubbed API tests, token benchmarks
├── README.md
└── LICENSE                # MIT
```

## Requirement-ID → phase map

| Requirement group | IDs | Phase |
|---|---|---|
| Read hook | R1–R4 | 1 |
| Bash hook | B1–B4 | 1 |
| bulk-read script | BR1–BR8 | 2 |
| code-write script | CW1–CW4 | 2 |
| Skills | S1–S2 | 3 |
| Provider config, install flow, doctor command | — | 3 |
| Benchmark suite, success metrics | — | 4 |

## Non-functional requirements, by phase

- **Performance** (hooks under 100 ms on a 10,000-line file) — verified in
  Phase 1, re-checked in Phase 4's benchmark suite.
- **Security** (no shell string-building, no key leakage, `--force` semantics)
  — built into Phase 2's scripts, checked by Phase 4's evals.
- **Privacy** (no telemetry, cache outside repo, Ollama documented) — Phase 2
  (cache location, provider routing) and Phase 3 (README callouts).
- **Portability** (macOS/Linux/Windows-WSL, Python 3.9+, no extra packages)
  — a standing constraint checked at the end of every phase, and explicitly
  re-verified in Phase 4.

## Success metrics (from PRD, tracked from Phase 4 onward)

| Metric | Target |
|---|---|
| Claude tokens saved on bulk-read tasks | ≥ 70% |
| Answer quality vs. baseline | No drop |
| Hook false blocks | < 2% of blocked calls |
| Hook latency | < 100 ms |
| Install to first delegated read | < 5 minutes |
| Worker cost as share of tokens saved | < 10% |

## Open items to resolve before Phase 3 packaging work

- Confirm the `tokenshed` name is free on GitHub and npm before the public
  marketplace listing (PRD open question, still unchecked).
- Pick and pin the recommended default hosted model in the quick start
  (cheapest capable model per M2 benchmarks at time of writing).
