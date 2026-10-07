# Tokenshed — Design

This document explains why Tokenshed is built the way it is: the problem,
the approaches considered and rejected, the trade-offs in the chosen
design, and what would have to change for it to work at larger scale.
For the build plan and phase status, see [`PLAN.md`](../PLAN.md). For
usage, see [`README.md`](../README.md).

## 1. Problem

Coding agents spend most of their tokens reading files into context, and
the largest reads are usually the least efficient. An agent that needs
five facts from a 4,000-line file reads all of it, which costs over 30,000
tokens. That cost is paid again on every later turn while the file stays
in context. It also pushes useful context out of the window sooner.

The obvious fix is an instruction in `CLAUDE.md` ("don't read large
files whole"). In practice agents often ignore that kind of rule,
especially mid-task. The problem is enforcement, not awareness.

**Goal:** cut tokens spent on bulk file reading by 70% or more, with no
drop in answer quality, without slowing the agent loop down or making it
less reliable.

**Constraints** (from the PRD, applied to every component):

- **Fail open.** Tokenshed must never be the reason a session breaks.
- **Python 3.9+ standard library only.** No server, database, build step,
  or `pip install`.
- **Privacy by construction.** Files go only to the endpoint the user
  configures, and no telemetry is sent.
- **Provider-agnostic.** Any OpenAI-compatible endpoint works, including
  a local model.

## 2. Design

```
 Claude Code ──Read / Bash──▶ PreToolUse hook ──small / partial / allowed──▶ tool runs
                                   │
                                   └─ large whole-file read ──▶ deny + instructions
                                                                    │
 Claude ◀── short answer ── bulk_read.py ◀── cache ◀── worker model ┘
                                 (question + file contents)
```

Three layers, from hard enforcement to soft guidance:

1. **Hooks** (`hooks/`). `PreToolUse` hooks on `Read` and `Bash` deny a
   whole-file read above `TOKENSHED_MIN_LINES` (350 by default). The deny
   message names the file and its line count, and gives the exact
   `bulk_read` command to run instead, plus the grep-then-partial-read
   route for edits. The denial *is* the routing: the agent gets a better
   path at the moment it is about to take the expensive one.
2. **Worker scripts** (`scripts/`). `bulk_read.py` sends the question and
   the files to a cheap worker model and prints only the answer.
   `code_write.py` generates boilerplate that follows a reference file's
   pattern. Both are plain CLIs, so nothing in them is specific to Claude.
3. **Skills** (`skills/`). These tell the agent when to delegate, when not
   to (edits, debugging, design decisions), and the exact syntax.

Supporting pieces:

- **Answer cache** (`scripts/_cache.py`). Keyed on the question, the
  model, the prompt version, and each file's path and content hash.
  Editing a file, switching model, or changing the prompt invalidates an
  entry automatically. Entries expire after 30 days, and the cache is
  capped at 50MB. It lives in the user's cache directory, never in the
  repo.
- **Savings ledger** (`scripts/_stats.py`, `/tokenshed:report`). This is
  an append-only JSONL file. Hooks record estimated tokens avoided
  (file bytes ÷ 4) when they deny a read. Workers record the exact tokens
  spent, taken from the API's `usage` field.

## 3. Alternatives considered

| Approach | Why it was rejected |
|---|---|
| **Instructions in `CLAUDE.md` only** | Advisory only. Agents ignore it under task pressure, which is the problem Tokenshed exists to solve. Tokenshed keeps skills as a soft layer, but enforcement lives in hooks. |
| **An MCP server exposing a "summarize file" tool** | Adding a tool doesn't take away the expensive one: the agent can still call `Read`. It also adds a long-running process to install and supervise. A PRD non-goal. |
| **Truncating in the hook (return the first N lines)** | Silently gives the agent a partial file it thinks is whole. That trades a cost problem for a correctness problem. |
| **Compressing context after the read** | Too late. The tokens are already spent on the read, and the full file was in context for at least one turn. |
| **An embeddings / RAG index of the repo** | Needs an index store, a build step, and re-indexing on every edit. It also violates the stdlib-only, no-server constraint. Retrieval also answers "where is X" well but "what does this file do" poorly. |
| **The agent's own sub-agents on a cheaper model** | Still limited to one vendor's models, with no local option. Code can't stay on the machine, and the user can't pick the cheapest model that is good enough. |
| **Blocking by token count instead of line count** | A precise token count needs a tokenizer (a dependency) or a full read (too slow for a hook). Counting lines is cheap, bounded, and close enough for a threshold. |

## 4. Trade-offs in the chosen design

- **Enforcement vs. friction.** A hard deny costs one extra turn: the
  agent gets the deny, then delegates. That turn is far cheaper than a
  30,000-token read. The friction falls only on large whole-file reads.
  Partial reads (`offset`/`limit`), small files, binary files, missing
  files, and allow-listed paths always pass through.
- **Fail open over fail closed.** On any hook error the read is allowed.
  Sometimes a large file will get through, but a Tokenshed bug can never
  block a session. Savings are a nice-to-have, and reliability is not.
- **Line-count heuristic.** Line counting is cheap. It stops early at
  20× the threshold, which keeps hooks well under 100 ms on large files.
  The cost is accuracy: a minified one-line bundle passes the line check
  and is read whole. A byte-size check alongside the line count would
  close that gap at almost no cost.
- **Worker accuracy vs. cost.** A cheap or local model is less accurate
  than the main agent. This is acceptable because delegation is limited
  to reading and boilerplate. Edits, debugging, and design decisions stay
  with the main agent permanently. The worker prompt asks for line-cited
  answers and for "not in the files" instead of a guess, so the main agent
  can verify with a targeted partial read.
- **Hosted vs. local worker.** Hosted is the default because setup takes
  minutes. Local (Ollama) keeps code on the machine but needs a capable
  machine and is slower. The README states the privacy consequence up
  front instead of hiding it in a setting.
- **Estimated vs. exact accounting.** Tokens spent are exact (from the
  API). Tokens avoided are estimated (bytes ÷ 4), because the read that
  was avoided never happened and can't be measured directly. The report
  is directionally right but not exact: if the agent later reads part of
  a blocked file, that cost isn't subtracted.
- **Stdlib only.** There is nothing to install, but Tokenshed gives up a
  real tokenizer, an HTTP client with retries, and a structured store.
  Each of those is replaced by something smaller that is good enough at
  current scale (see §5 for where that stops holding).

## 5. What changes at scale

The current design targets one developer, one machine, and repos of
ordinary size. These are the parts that would have to change, roughly in
the order they would start to hurt:

- **Concurrent sessions.** Session attribution uses a single marker file
  in the cache directory. Two Claude Code sessions running at once on the
  same machine overwrite each other's marker, so worker spend can be
  booked to the wrong session. The fix is to pass the session id
  explicitly. The deny message could embed `TOKENSHED_SESSION=<id>` in the
  command it suggests, so attribution no longer depends on shared state.
- **Ledger growth.** `stats.jsonl` is append-only and read in full by the
  report. That is fine for months of personal use, but a heavy user or a
  team pipeline would need rotation (one file per month) or a rollup file.
  SQLite from the standard library would be the next step.
- **Very large or many-file questions.** `bulk_read` sends everything in
  one request, capped by `TOKENSHED_MAX_BYTES` (1.5MB). A question that
  spans a whole subsystem needs map-reduce instead: answer per file or
  per chunk, then merge. That brings in partial-answer caching and the
  question of how to merge answers without losing citations.
- **Team and CI use.** Each person's cache is private, so a team pays
  again for the same answers. A shared cache keyed on content hashes is
  safe to share, since it holds no paths beyond the repo. But it brings
  back a server, plus access control for cached answers that describe
  proprietary code. That is a deliberate step away from the v1 constraints
  and would need its own design.
- **Cost and rate limits.** At scale the worker provider's rate limits
  matter. `_api.py` has a timeout but no retry or backoff, which is the
  right call for an interactive tool. Batch or CI use would need bounded
  retries with jitter, plus a per-day spend cap so a runaway loop can't
  run up a bill.
- **Quality assurance.** At one user, "no drop in quality" can be checked
  by eye. At scale it needs a standing eval: benchmark tasks on pinned
  public repos, real token counts from session transcripts, and graded
  answers. These run on every worker-model or prompt change. The
  `evals/benchmarks/` scaffold is the start of this, and its README lists
  what's still missing.
- **More agents.** The worker scripts are already agent-agnostic CLIs.
  Supporting Codex or Cursor means a thin enforcement adapter per agent,
  using its own hook or extension mechanism, around the same scripts.

## 6. Measuring success

| Metric | Target | How it's measured |
|---|---|---|
| Claude tokens saved on bulk-read tasks | ≥ 70% | Same task run with Tokenshed on and off, with token counts from real session transcripts |
| Answer quality vs. baseline | No drop | Graded against human-written answer keys |
| Hook false blocks | < 2% of blocked calls | Review of blocked calls in the ledger |
| Hook latency | < 100 ms | Latency cases in `evals/hooks/` |
| Worker cost as share of tokens saved | < 10% | Provider billing, summed over a benchmark run |

The scaffold in `evals/benchmarks/` runs today. A full run on real repos
with real token counts is the remaining gate before v1.0 (see `PLAN.md`).
