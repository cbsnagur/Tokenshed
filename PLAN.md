# Tokenshed — Build Plan

Source: `PRD: Tokenshed — a lightweight token-saving plugin for Claude Code` (Sep 21, 2026).

Tokenshed is a Claude Code plugin that blocks large whole-file reads via hooks
and reroutes them to a cheap, user-chosen OpenAI-compatible model, returning
only a short answer to Claude's context. This document is the build plan:
phases, dependencies between them, the target repo layout, and how the PRD's
requirement IDs map to each phase and to the code that implements them.

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

| # | Phase | PRD milestone | Status | Where |
|---|-------|---------------|--------|-------|
| 0 | Project foundations | — (pre-M1) | done | `.claude-plugin/`, `LICENSE`, `CONTRIBUTING.md` |
| 1 | Hooks | M1: Hooks | done | `hooks/`, `evals/hooks/` |
| 2 | Worker scripts | M2: Workers | done | `scripts/_api.py`, `scripts/_cache.py`, `scripts/bulk_read.py`, `scripts/code_write.py`, `evals/scripts/` |
| 3 | Skills & packaging | M3: Skills and packaging | done | `skills/`, `commands/doctor.md`, `scripts/doctor.py`, `README.md` |
| 4 | Benchmarks & beta | M4: Benchmarks and beta | scaffold done, real run pending | `evals/benchmarks/` (see its README for what's still manual) |
| 5 | v1.0 release | v1.0 release | pending | tag + marketplace listing, after a real Phase 4 run |

Estimated timeline: ~4 weeks part-time, one phase per week (Phase 0 folded
into the front of Week 1 alongside Phase 1).

## Target repo layout

```
tokenshed/
├── .claude-plugin/        # Plugin and marketplace manifests
├── hooks/                 # Hook registration plus the Read and Bash hooks
├── scripts/               # bulk-read, code-write, doctor, shared API/cache helpers
├── skills/                # bulk-reader and code-writer skill files
├── commands/              # The /tokenshed:doctor command
├── evals/                 # Hook, script, and benchmark test cases
├── README.md
└── LICENSE                # MIT
```

## Requirement-ID → phase map

| Requirement group | IDs | Phase | Code |
|---|---|---|---|
| Read hook | R1–R4 | 1 | `hooks/read_hook.py` |
| Bash hook | B1–B4 | 1 | `hooks/bash_hook.py` |
| bulk-read script | BR1–BR8 | 2 | `scripts/bulk_read.py`, `scripts/_cache.py` |
| code-write script | CW1–CW4 | 2 | `scripts/code_write.py` |
| Skills | S1–S2 | 3 | `skills/bulk-reader/`, `skills/code-writer/` |
| Provider config, install flow, doctor command | — | 3 | `README.md`, `scripts/doctor.py` |
| Benchmark suite, success metrics | — | 4 | `evals/benchmarks/` |

## Non-functional requirements, by phase

- **Performance** (hooks under 100 ms on a 10,000-line file) — verified in
  Phase 1 (`evals/hooks/test_*.py` latency cases), re-checked in Phase 4's
  benchmark suite.
- **Security** (no shell string-building, no key leakage, `--force` semantics)
  — built into Phase 2's scripts, checked by Phase 2/3 evals.
- **Privacy** (no telemetry, cache outside repo, Ollama documented) — Phase 2
  (cache location, provider routing) and Phase 3 (README callouts).
- **Portability** (macOS/Linux/Windows-WSL, Python 3.9+, no extra packages)
  — a standing constraint checked at the end of every phase.

## Success metrics (from PRD, tracked from Phase 4 onward)

| Metric | Target |
|---|---|
| Claude tokens saved on bulk-read tasks | ≥ 70% |
| Answer quality vs. baseline | No drop |
| Hook false blocks | < 2% of blocked calls |
| Hook latency | < 100 ms |
| Install to first delegated read | < 5 minutes |
| Worker cost as share of tokens saved | < 10% |

## Open items before v1.0 release

- Confirm the `tokenshed` name is free on GitHub and npm before the public
  marketplace listing (PRD open question, still unchecked).
- Run a real Phase 4 benchmark (real repos, real token counts, human-graded
  answer quality) — see `evals/benchmarks/README.md` for the gap between the
  scaffold and a full run.
- Recruit and run the 5–10 person beta program.

## Later (v1.x and v2) — deferred by design, not forgotten

- **Soft routing for `code-write`.** A hook that detects large new-file
  writes and nudges toward `code-write` automatically, the same way the
  Read hook enforces bulk-read. v1 relies on skill wording alone
  (`skills/code-writer/SKILL.md`) — this is the thing to watch in beta
  feedback; pull it forward if Claude keeps generating code itself instead
  of delegating.
- **Adapters for Codex and Cursor.** Reuse the Phase 2 scripts (they're
  agent-agnostic CLIs) behind each tool's own hook/extension mechanism.
- **A per-session savings report.** Tokens avoided and worker cost per
  session, built on top of the Phase 4 benchmark instrumentation. Plain
  text/CLI — the PRD excludes any UI or dashboard from v1.

**Explicitly not planned** (PRD non-goals): support for agents other than
Claude Code beyond the v1.x item above; an MCP server; hosting or reselling
model access; delegating edits, debugging, or design decisions to the
worker model (a permanent boundary, not a v1 limitation); a UI or
dashboard.
