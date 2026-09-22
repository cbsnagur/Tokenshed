# Tokenshed — Token-Savings Tracking Implementation Plan

## Goal

Track how many tokens Tokenshed saves, per session and lifetime, via a
plain-text CLI report (`/tokenshed:report`). Reuses the existing
stdlib-only, fail-open, privacy-by-construction constraints and the
deferred "per-session savings report" item in `PLAN.md:111-113`.

## Measurements (confirmed: option 1)

- **Tokens avoided** — estimated when a hook **denies** a whole-file read:
  file bytes ÷ 4 (reuses the project's existing estimator rule in
  `evals/benchmarks/estimate_tokens.py:13`).
- **Tokens spent** — the worker's **exact** `usage.total_tokens` from the
  OpenAI-compatible API response (currently discarded at `_api.py:107`).
- **Saved = Σ avoided − Σ spent**, aggregated per session and lifetime.

## Session-id propagation

Hooks and worker scripts are separate processes; only hooks know the
session id (`data["session_id"]` in hook input). Mechanism:

1. **Hook** on any deny stamps `~/.cache/tokenshed/session` with the
   current `session_id`.
2. **Worker script** on launch: session = `TOKENSHED_SESSION` env if set,
   else the marker file contents.

Both converge on the same session key; no dependence on undocumented
Claude internals.

## Ledger

`~/.cache/tokenshed/stats.jsonl` (append-only JSONL, same cache dir as
`_cache.default_cache_dir()`):

```
{"ts":1728000000,"session":"abc-123","kind":"block","script":"read","file":"src/x.py","bytes":120000,"avoided_tokens":30000}
{"ts":1728000100,"session":"abc-123","kind":"worker","script":"bulk_read","model":"gemini-2.5-flash","spent_tokens":1290}
```

- `TOKENSHED_STATS=off` disables recording (mirrors `TOKENSHED_CACHE`).
- Best-effort only: any ledger error is swallowed — never fails a
  hook/worker.
- Local only, no telemetry.

## File changes

| File | Change |
|---|---|
| `scripts/_stats.py` (new) | `ledger_path()`, `session_id()` (env→marker), `record()`, `read_events()`, `summarize()`; fail-open, stdlib-only |
| `scripts/_api.py` | `chat_completion` returns `(content, usage)` — surface real `usage.total_tokens` |
| `scripts/bulk_read.py` | Record `worker` event on cache miss only (cache hits spend nothing) |
| `scripts/code_write.py` | Record `worker` event after successful generation |
| `hooks/_common.py` | Add `estimate_avoided_tokens(path)` (getsize÷4) and `stamp_session(id)` |
| `hooks/read_hook.py` | On deny (`:65`) stamp session + record `block` event |
| `hooks/bash_hook.py` | On deny (`:157`, `:161`) stamp session + record `block` event |
| `scripts/report.py` (new) | Read ledger, print per-session + lifetime totals; `--since`/`--session` filters |
| `commands/report.md` (new) | `/tokenshed:report` slash command, mirrors `doctor.md` |
| `skills/bulk-reader/SKILL.md`, `skills/code-writer/SKILL.md` | Note `TOKENSHED_SESSION` override |
| `PLAN.md`, `README.md` | Move deferred item to done; document feature + env vars |

## Tests (CI: `python -m unittest discover -s evals -p "test_*.py"`)

- Update `test_api.py`, `test_bulk_read.py`, `test_code_write.py` for the
  new `(content, usage)` return; assert worker events on real calls, none
  on cache hits.
- Update `test_read_hook.py`, `test_bash_hook.py` for `block` events on
  deny only.
- **New** `test_stats.py`: append/summarize, per-session grouping,
  env→marker precedence, fail-open on corrupt ledger, `TOKENSHED_STATS=off`
  opt-out.

## Sample report output

```
tokenshed report — tokens saved
===============================
Session abc-123 (current):
  blocked reads         12
  tokens avoided    ~360,000
  worker tokens spent     9,100
  tokens saved      ~350,900

Lifetime totals:
  blocked reads         47
  tokens avoided   ~1,420,000
  worker tokens spent    31,500
  tokens saved     ~1,388,500
```

## Caveat

"Saved" inherits the ~4-chars/token approximation for the avoided half
(unavoidable — no access to Claude's tokenizer); a future real-tokenizer
swap is a single-function change in `_stats.py`.
