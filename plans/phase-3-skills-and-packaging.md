# Phase 3 — Skills & Packaging (PRD milestone M3)

**Goal:** the soft-guidance layer plus everything needed for a stranger to
install Tokenshed and have it work in under five minutes. Hooks (Phase 1)
enforce; scripts (Phase 2) do the work; skills tell Claude when and how to
reach for the scripts, and packaging makes the whole thing installable.

**Depends on:** Phase 2 (skills document the exact, finalized script
syntax).
**Blocks:** Phase 4 (the benchmark suite runs against the packaged plugin,
and beta users install it via this phase's install flow).

**Estimate:** ~1 week (Week 3).

## Requirements covered

| ID | Requirement | Priority |
|----|-------------|----------|
| S1 | A bulk-reader skill and a code-writer skill, each stating when to use it, when not to, and exact syntax | P0 |
| S2 | Both skills list what never gets delegated: debugging, editing, small files, design decisions | P0 |

Plus (not requirement-ID'd in the PRD, but explicitly scoped to this
milestone): provider documentation, install flow, `/tokenshed:doctor`
command, and the README.

## Task breakdown

1. **bulk-reader skill** (`skills/bulk-reader/`)
   - When to use: answering a question about a large file or set of files
     ("what does this do", "which methods touch X across these files").
   - When not to use (S2): debugging, editing, files already under the
     threshold, anything requiring a design decision — those stay with
     Claude directly.
   - Exact syntax: the real `bulk-read --question ... --paths ...`
     invocation, matching Phase 2's finalized CLI exactly (and matching
     Phase 1's hook block-message wording — reconcile any drift between
     the two now that both are built).
   - Note the `(cached)` marker and `--no-cache` escape hatch so Claude
     knows a fast repeat answer isn't stale.

2. **code-writer skill** (`skills/code-writer/`)
   - When to use: generating new boilerplate that closely follows an
     existing pattern ("write tests for X like the ones in Y").
   - When not to use (S2): editing existing code, anything needing
     judgment about correctness or design, small/one-off snippets not
     worth the round-trip.
   - Exact syntax: `code-write --spec ... --reference ... [--target ...]
     [--force]`, and the expectation that with `--target` the code itself
     never appears in the conversation — only a one-line summary Claude
     should then verify by reading the written file (a normal, small,
     partial-friendly read, not a delegated one).

3. **`/tokenshed:doctor` command** (`commands/`)
   - Checks: required env vars set (`TOKENSHED_MODEL` at minimum), API
     reachability with a tiny (cheap/free where possible) test call against
     `TOKENSHED_API_BASE`, and a scan of tracked files for an accidentally
     committed `TOKENSHED_API_KEY` value (PRD risk: "users paste API keys
     into committed settings" → "a doctor warning if a key appears in a
     tracked file").
   - Output: pass/fail per check, in plain text, never echoing the key
     itself even when warning about it (name the file/line, not the
     value).

4. **README**
   - Overview and problem statement (from PRD's own framing).
   - Install flow, verbatim from PRD: `claude plugin marketplace add
     <owner>/tokenshed` → `claude plugin install tokenshed@tokenshed` → set
     `TOKENSHED_MODEL`/`TOKENSHED_API_BASE`/`TOKENSHED_API_KEY` in shell
     profile → new session → optional `/tokenshed:doctor`.
   - Manual install path for non-marketplace users: copy `hooks/`,
     `scripts/`, `skills/`, `commands/` into a project's `.claude/`.
   - Quick start using the cheapest capable hosted model at time of
     writing (pick and pin the specific model name — open item carried
     from `PLAN.md`).
   - Full Ollama alternative, verbatim shape from PRD:
     ```
     ollama pull qwen2.5-coder:7b
     export TOKENSHED_API_BASE=http://localhost:11434/v1
     export TOKENSHED_MODEL=qwen2.5-coder:7b
     ```
     with an explicit callout on why (code never leaves the machine) and
     who it's for (proprietary/regulated code, employer restrictions).
   - Provider table (OpenAI, Gemini, OpenRouter, Ollama) with base URLs,
     from the PRD.
   - Full env var reference table (all `TOKENSHED_*` vars, defaults,
     purpose) from the PRD's configuration section.
   - Privacy/security statement: no telemetry, cache location, key
     handling.
   - License (MIT).

5. **Manifest finalization**
   - Fill in the Phase 0 manifest skeleton with real hook paths, script
     entries, skill entries, and the doctor command.
   - Confirm marketplace metadata (name, description) — contingent on the
     open "is `tokenshed` free on GitHub/npm" item.

## Deliverables

- `skills/bulk-reader/`, `skills/code-writer/` skill files.
- `commands/doctor.md` (or equivalent) implementing `/tokenshed:doctor`.
- Full `README.md`.
- Finalized `.claude-plugin/` manifests.

## Exit criteria (PRD M3)

- A fresh-machine install (marketplace add → install → set three env vars
  → new session) completes in under 5 minutes, timed as a literal
  walkthrough.

## Risks specific to this phase

- **Claude ignores code-write and generates code itself** (PRD risk) —
  mitigated here by clear, opinionated skill wording on when code-write
  applies; a soft-routing hook to catch this automatically is explicitly
  deferred to v1.x (see `plans/phase-5-post-v1.md`), so this phase's skill
  wording is the only defense in v1 — worth extra iteration/testing time.
- **Doctor false negatives**: a passing doctor check that doesn't actually
  predict a working end-to-end call would be worse than no command at all
  — test it against a deliberately broken config (wrong key, wrong base
  URL) to confirm it fails loudly in each case.
