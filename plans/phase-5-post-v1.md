# Phase 5 — Post-v1 (v1.x / v2)

**Goal:** track the PRD's explicitly deferred items so they don't get lost,
without pulling them into the v1 scope or timeline. Nothing here blocks the
v1.0 release in `plans/phase-4-benchmarks-and-beta.md`.

**Depends on:** v1.0 shipped.

## Deferred items (from PRD "Later (v1.x and v2)")

1. **Soft routing for `code-write`.** A hook that detects large new-file
   writes and nudges toward `code-write` automatically, the same way the
   Read hook enforces bulk-read. v1 relies on skill wording alone (Phase 3)
   for this — noted there as the primary risk area to watch in beta
   feedback. If beta or early usage shows Claude frequently generating
   code itself instead of delegating, pull this forward.

2. **Adapters for Codex and Cursor.** Reuse the Phase 2 scripts (they're
   agent-agnostic CLIs) behind each tool's own hook/extension mechanism.
   Scoping work: survey each tool's equivalent of a pre-read hook before
   estimating.

3. **Per-session savings report.** Surface tokens avoided and worker cost
   per session — most naturally built on top of the Phase 4 benchmark
   instrumentation, so it's largely a matter of exposing what the
   benchmark runner already computes, in a session-scoped, user-facing
   form (PRD explicitly excludes any UI/dashboard from v1).

## Also carried forward (P1 items not required to block v1, per PRD priority)

- **R4**: per-project allow-list for the Read hook.
- **B4**: `head`/`tail` line-count-aware blocking for the Bash hook.
- **BR5**: bulk-read request size refusal.
- These are P1, not "later" in the PRD's own milestone table, so the
  intent is to ship them within v1 if Phase 1/2 time allows, and treat this
  section as the fallback only if they slip.

## Not planned (PRD non-goals, listed here so they aren't rediscovered as "missing")

- Support for agents other than Claude Code in v1 (Codex/Cursor/Copilot are
  the v1.x item above, not a v1 gap).
- An MCP server — hooks plus scripts are the deliberate design, not a
  stepping stone to one.
- Hosting or reselling model access — users always bring their own key or
  local model.
- Delegating edits, debugging, or design decisions to the worker model —
  this is a permanent boundary (PRD's biggest named risk), not a v1
  limitation to lift later.
- A UI or dashboard — the per-session savings report above is the closest
  this gets, and it's plain text/CLI, not a UI.
