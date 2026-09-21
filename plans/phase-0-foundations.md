# Phase 0 — Project Foundations

**Goal:** a repo that a plugin can be built into, with the skeleton in place
before any hook logic is written. No user-facing behavior yet.

**Depends on:** nothing. **Blocks:** Phase 1.

**Estimate:** 0.5–1 day, absorbed into the front of Week 1 (M1).

## Tasks

1. **Repo scaffolding**
   - Create the target layout: `.claude-plugin/`, `hooks/`, `scripts/`,
     `skills/`, `commands/`, `evals/`.
   - Add `LICENSE` (MIT).
   - Add a minimal `README.md` stub (title, one-line description, "under
     construction" — filled out fully in Phase 3).
   - Add `.gitignore` covering Python artifacts (`__pycache__/`, `*.pyc`,
     `.venv/`) and anything that could accidentally capture local secrets
     (e.g. `.env`).

2. **Plugin/marketplace manifest skeleton**
   - Draft `.claude-plugin/plugin.json` (or the current Claude Code plugin
     manifest format) with name `tokenshed`, version `0.1.0`, and empty
     `hooks`/`commands`/`skills` sections to be filled in later phases.
   - Draft the marketplace manifest so the repo can serve as its own
     marketplace (per PRD: `claude plugin marketplace add <owner>/tokenshed`).
   - Do not wire real hook/script paths yet — that's Phase 1/2/3 work. This
     step only proves the manifest shape is accepted by Claude Code.

3. **Dev environment baseline**
   - Confirm target Python version support: 3.9+ only, stdlib only. Add a
     short `CONTRIBUTING.md` note (or a section in README) stating this
     constraint so later phases don't accidentally introduce a dependency.
   - Decide the eval/test runner: given the "no dependencies beyond stdlib"
     rule, prefer `unittest` (stdlib) over `pytest` unless the user
     explicitly wants `pytest` as a dev-only dependency. Record the decision
     here once made.

4. **CI stub (optional but cheap)**
   - A minimal GitHub Actions workflow that runs `python -m unittest` (or
     chosen runner) on push/PR, even before there's anything to test. Keeps
     Phase 1's eval suite from being the first thing that has to fight CI
     setup.

## Deliverables

- Empty-but-correct directory structure, committed.
- `LICENSE`, README stub, `.gitignore`.
- A plugin manifest that Claude Code recognizes (even with no real hooks
  registered).
- Decision recorded on test runner.

## Exit criteria

- `claude plugin marketplace add <owner>/tokenshed` (or local-path
  equivalent) succeeds without error against the manifest skeleton.
- Repo layout matches the table in `PLAN.md`.

## Risks

- Manifest format drift: Claude Code's plugin/hook schema could differ from
  what's documented at planning time. Mitigation: validate the manifest
  early against a real local Claude Code install before building hook logic
  on top of it, and pin the minimum Claude Code version once confirmed (PRD
  risk: "Claude Code changes its hook or plugin format").
