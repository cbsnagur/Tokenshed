# Phase 4 — Benchmarks, Beta & v1.0 Release (PRD milestone M4 + release)

**Goal:** prove the 70%-token-saving claim reproducibly, run it past real
users, fix what they find, and ship the public marketplace listing.

**Depends on:** Phase 3 (a fully packaged, installable plugin to benchmark
and hand to beta users).
**Blocks:** nothing (final phase of v1); feeds directly into
`plans/phase-5-post-v1.md` for anything found here but deferred.

**Estimate:** ~1 week (Week 4), through end-of-week-4 release.

## Success metrics this phase is responsible for proving

| Metric | Target | How measured |
|---|---|---|
| Claude tokens saved on bulk-read tasks | ≥ 70% | Benchmark suite, hooks on vs. off |
| Answer quality on benchmark questions | No drop vs. baseline | Graded answer key per task |
| Hook false blocks | < 2% of blocked calls | Hook eval cases (extends Phase 1's suite) |
| Hook latency | < 100 ms | Timed on a 10,000-line file (re-confirms Phase 1) |
| Time from install to first delegated read | < 5 minutes | Fresh-machine walkthrough (re-confirms Phase 3) |
| Worker cost as share of tokens saved | < 10% | Provider billing on benchmark runs |

## Task breakdown

1. **Benchmark suite** (`evals/benchmarks/`)
   - Select 3–5 public open-source repos across different languages (PRD:
     "so anyone can reproduce the numbers") — pick repos with a mix of
     large files so the 350-line threshold has real material to work
     against.
   - Define a fixed task set per repo: a mix of the four PRD use cases —
     summarize a large file, cross-file method search, pattern-following
     generation, and a targeted bug-fix (the last one deliberately *not*
     delegated, to confirm the hook correctly allows small partial reads
     through untouched).
   - Build a graded answer key per task (human-authored expected answer or
     key facts) to score quality, not just token count.
   - Run each task twice: hooks+scripts ON, and OFF (baseline Claude Code),
     recording actual token counts from both runs.
   - Compute: % token reduction, per-task quality score vs. baseline,
     worker API cost for the ON run, hook latency samples, and a count of
     any block that a human grader judges to have been unnecessary (false
     block rate).

2. **Beta program**
   - Recruit 5–10 beta users (PRD number) — ideally covering the target
     personas from the PRD's user table: subscription individual, per-token
     team, privacy-conscious/Ollama user, OSS maintainer.
   - Give them the Phase 3 README as their only onboarding material — this
     doubles as a real-world test of the "under 5 minutes" install claim
     outside of an internal walkthrough.
   - Collect structured feedback: install friction, any false blocks hit in
     real work, any case where code-write's output needed heavy correction,
     any confusion in skill wording.

3. **Fix pass**
   - Triage beta feedback and benchmark misses against the P0/P1 priorities
     already set in earlier phases' requirement tables — a P0 miss (e.g.
     the 70% target not met on some language) blocks release; a P1 gap
     (e.g. R4/B4 edge cases) can slip to v1.x per PRD's stated priority
     split.
   - Re-run the affected benchmark tasks after each fix to confirm no
     regression.

4. **v1.0 release checklist**
   - Confirm the open naming question (`tokenshed` free on GitHub/npm) is
     resolved — this blocks the public marketplace listing regardless of
     technical readiness.
   - Final pass on README/docs incorporating anything learned from beta
     (common gotchas, an FAQ if patterns emerge).
   - Tag `v1.0.0`, publish the marketplace listing.
   - Publish the benchmark methodology and results alongside the release
     (PRD explicitly wants this reproducible, so numbers without the method
     undercut the credibility goal).

## Deliverables

- `evals/benchmarks/` suite with repo list, task definitions, answer keys,
  and a runner script that reports the metrics table above.
- A benchmark results writeup (can live in `README.md` or a
  `BENCHMARKS.md`) with numbers and methodology.
- Beta feedback log and resulting fix commits.
- Tagged `v1.0.0` release and live marketplace listing.

## Exit criteria (PRD M4 + release)

- ≥ 70% token saving demonstrated, with no quality drop, across the
  benchmark suite.
- Beta feedback addressed (each item resolved or explicitly deferred with a
  reason — deferred items go into `plans/phase-5-post-v1.md`).

## Risks specific to this phase

- **Benchmark gaming**: hand-picking tasks that flatter the 70% number
  undercuts the PRD's own credibility goal ("so anyone can reproduce the
  numbers") — keep task selection principled (e.g. every file over the
  threshold in the sampled repos gets at least one task) rather than
  cherry-picked after the fact.
- **Beta timeline risk**: 5–10 external users inside a single week is tight
  — recruit before Phase 4 starts (during Phase 3) so onboarding isn't the
  bottleneck.
