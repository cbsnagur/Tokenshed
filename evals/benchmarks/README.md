# Tokenshed benchmark scaffold

This directory is the scaffold for PRD milestone M4's benchmark suite —
runnable today for a local sanity check, but **not yet the full benchmark
run the PRD describes**. What's here vs. what's still needed:

## What this scaffold does

- `estimate_tokens.py` — a rough ~4-chars/token estimator (stdlib only,
  no tokenizer dependency).
- `tasks/*.json` — task definitions: a question, the file(s) to ask it
  about, and a human-authored answer key.
- `fixtures/sample_large_file.py` — a synthetic 377-line file so the one
  included example task (`tasks/example_summarize.json`) can run without
  a real target repo.
- `run_benchmark.py` — loads every task, calls the *real*
  `scripts/bulk_read.py` (unmodified) for each one, and reports estimated
  tokens saved, latency, cache status, and a crude automated
  quality-overlap signal.

Run it with a worker configured, same as the plugin itself:

```
export TOKENSHED_MODEL=qwen2.5-coder:7b
export TOKENSHED_API_BASE=http://localhost:11434/v1
python3 evals/benchmarks/run_benchmark.py
```

## What a full M4 benchmark run still needs (PRD's actual exit criteria)

1. **Real public repos, not the local fixture.** The PRD calls for 3–5
   public open-source repos across different languages, so results are
   independently reproducible. Add each as a `tasks/*.json` file whose
   `paths` point into a checkout of that repo (or vendor a pinned copy
   under `fixtures/`), covering all four PRD use cases per repo:
   summarize a large file, cross-file method search, pattern-following
   generation (a `code-write` task type isn't wired into
   `run_benchmark.py` yet — add one alongside the `summarize` kind), and
   a small targeted bug-fix task that's deliberately *not* delegated (to
   confirm the hook correctly lets small partial reads through).
2. **Real token counts, not the estimator.** `estimate_tokens.py` is a
   stand-in. A real run needs actual Claude token counts for the same
   task run twice — hooks+scripts on, and off — pulled from real Claude
   Code session transcripts, not this heuristic.
3. **Human-graded answer quality**, not `quality_hits`'s crude word-overlap
   check. The PRD wants "no drop vs. baseline," which means a real human
   (or a calibrated LLM-judge setup) scoring each answer against the
   answer key.
4. **A beta program.** 5–10 real users, onboarding from `README.md` alone,
   covering the persona table in `PLAN.md` (subscription individual,
   per-token team, privacy-conscious/Ollama user, OSS maintainer).
   Nothing in this repo can simulate that — it's a recruitment and
   coordination task for whoever is driving the release.
5. **Worker cost accounting.** Provider billing dashboards, summed across
   a benchmark run, to check the "worker cost under 10% of tokens saved"
   metric from `PLAN.md`.

Items 1–3 are mechanical extensions of what's already here (add real
tasks, swap the estimator for real counts, add a grading step). Items 4–5
require a human driving an actual release and are out of scope for
anything that runs unattended in this repo.
