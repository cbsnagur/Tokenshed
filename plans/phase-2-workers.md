# Phase 2 — Worker Scripts (PRD milestone M2)

**Goal:** the delegation layer. Once Phase 1's hooks block a large read and
tell Claude what to run instead, that command has to actually exist and
work against any OpenAI-compatible provider, with caching so repeat
questions are free.

**Depends on:** Phase 1 (the hook's block message already names these
exact commands, so their CLI surface — flags, output shape — should be
finalized here to match what Phase 1 promised, or Phase 1's message
strings updated to match).
**Blocks:** Phase 3 (skills document these scripts' syntax).

**Estimate:** ~1 week (Week 2).

## Requirements covered

| ID | Requirement | Priority |
|----|-------------|----------|
| BR1 | Take `--question` and `--paths` (one or more files) | P0 |
| BR2 | Wrap each file in `<file path="...">` tags with line numbers | P0 |
| BR3 | Instruct worker to answer in terse bullets, say when files lack the answer | P0 |
| BR4 | Print only the answer; clear errors for missing files, bad keys, unreachable APIs | P0 |
| BR5 | Refuse requests over a configurable size, suggest a split | P1 |
| BR6 | Cache keyed on SHA-256 of normalized question + model + prompt version + per-file path/content hash | P0 |
| BR7 | Cache in user cache dir, never repo; expire after 30 days; prune oldest-first above 50 MB | P0 |
| BR8 | Mark cached answers `(cached)`; support `--no-cache` | P0 |
| CW1 | Take `--spec`, one or more required `--reference` files, optional `--target` | P0 |
| CW2 | Strip markdown code fences from the worker's reply | P0 |
| CW3 | With `--target`, write the file and print only a one-line summary | P0 |
| CW4 | Refuse to overwrite an existing target unless `--force` | P0 |

## Task breakdown

1. **Shared API helper** (`scripts/_api.py` or similar, imported by both
   scripts — not a separate CLI)
   - Read `TOKENSHED_MODEL` (required — error immediately if unset),
     `TOKENSHED_API_BASE` (default `https://api.openai.com/v1`),
     `TOKENSHED_API_KEY` (optional, e.g. for Ollama), `TOKENSHED_TEMPERATURE`
     (default 0.2, `none` omits it), `TOKENSHED_TIMEOUT` (default 180s).
   - Build the OpenAI-compatible chat completion request using stdlib
     `urllib` (no `requests` dependency) or a vendored minimal HTTP client —
     confirm this against the "no dependencies beyond stdlib" constraint.
   - Build request bodies with `json.dumps`, never string concatenation
     (security NFR — no injection via file contents).
   - Map failure modes to single clear stderr lines: bad/missing key →
     "authentication failed", unreachable host → "could not reach
     <base_url>", non-2xx → include status code, never the key. Never log
     the key itself anywhere, including in verbose/debug output.
   - This module is the single place that talks to the network; both
     scripts below call into it.

2. **bulk-read script** (`scripts/bulk_read.py`)
   - CLI: `--question`, `--paths` (nargs, one or more), `--no-cache`
     (BR8), optionally `--max-bytes` override.
   - Read each path, wrap in `<file path="...">` with line numbers on every
     line (BR2) — this is what lets the returned answer cite exact lines.
   - System/user prompt instructs terse bullet answers and an explicit
     "not found in these files" fallback (BR3). Version this prompt string
     (a `PROMPT_VERSION` constant) since it's part of the cache key (BR6).
   - Size guard (BR5): sum file bytes before calling the worker; over
     `TOKENSHED_MAX_BYTES` (default 1,500,000) refuse with a message
     suggesting the caller split the file set.
   - Cache (BR6–BR8):
     - Key: SHA-256 over `(normalized question, model name, prompt
       version, sorted [(path, content_hash), ...])`.
     - Store: `TOKENSHED_CACHE_DIR` (default OS user cache dir via
       stdlib, e.g. `platformdirs`-equivalent hand-rolled logic since no
       extra deps — `~/.cache/tokenshed` on Linux, matching
       `XDG_CACHE_HOME` conventions, similar platform-appropriate paths on
       macOS/Windows).
     - Expire entries after 30 days; prune oldest-first once total cache
       size exceeds 50 MB. Do this prune opportunistically on write, not
       via a background process (no daemons per the "lightweight" goal).
     - `TOKENSHED_CACHE=off` disables read+write entirely; `--no-cache`
       disables read only for that invocation (still writes a fresh entry,
       per "force a fresh call" semantics — confirm this write-through
       behavior is what's wanted, or make `--no-cache` skip writes too, and
       record the decision here once implemented).
     - On cache hit, prefix output with `(cached)` (BR8).
   - Output (BR4): print only the worker's answer (or cache hit) to
     stdout; any error path prints one clear line to stderr and exits
     non-zero, so Claude sees a short actionable message, never a stack
     trace.

3. **code-write script** (`scripts/code_write.py`)
   - CLI: `--spec` (the instruction, e.g. "write tests for UserService like
     OrderTest"), `--reference` (nargs, one or more, required — the
     files to imitate), `--target` (optional output path), `--force`.
   - Build a prompt combining the spec and the reference files' contents
     (reuse the same `<file path="...">` wrapping as bulk-read for
     consistency and line-citation ability, even though citations matter
     less here).
   - Strip markdown code fences from the reply (CW2) — handle the common
     ```` ```lang\n...\n``` ```` shape and bare triple-backtick shape;
     don't attempt to parse arbitrary markdown, just fence-stripping.
   - Without `--target`: print the cleaned code to stdout (for cases where
     Claude wants to review before writing — confirm this against CW3's
     "code never enters Claude's context" framing; likely `--target` is
     the expected default path for delegated writes, and stdout-only mode
     is a secondary/debug mode).
   - With `--target` (CW3): write the file, then print only a one-line
     summary (e.g. `wrote 84 lines to tests/test_user_service.py`) — the
     generated code itself must never reach stdout in this mode.
   - `--force` gating (CW4): if `--target` exists and `--force` not passed,
     refuse with a clear error naming the existing path; never silently
     overwrite.
   - Path safety: write only to the exact `--target` path given — no
     inferring or rewriting paths, no writing outside the working
     directory implicitly.

4. **Cross-cutting security pass**
   - Audit both scripts for any place a filename or file content could
     reach a shell (`subprocess` with `shell=True`, string-built commands)
     — there should be none; all subprocess use (if any) must pass argument
     lists.
   - Confirm the API key never appears in: stdout, stderr, cache files on
     disk, or any exception message (wrap network exceptions and re-raise
     sanitized messages).

## Deliverables

- `scripts/_api.py`, `scripts/bulk_read.py`, `scripts/code_write.py`.
- Cache implementation with expiry/pruning, tested against a temp cache
  dir (never the real `~/.cache` in tests).
- Manual verification against OpenAI, Gemini's OpenAI-compatible endpoint,
  and a local Ollama model (the three providers named in PRD's exit
  criteria for M2).

## Exit criteria (PRD M2)

- Works against OpenAI, Gemini, and Ollama.
- A repeated question against unchanged files hits the cache (no network
  call, `(cached)` marker shown).

## Risks specific to this phase

- **Worker latency** (10–30s/call per PRD) — mitigated by the cache; not
  otherwise a Phase 2 concern (it's inherent to using a model at all).
- **Provider quirks**: some OpenAI-compatible endpoints reject unknown
  fields like `temperature` — `TOKENSHED_TEMPERATURE=none` exists
  specifically to omit it; test this against at least one such provider
  during manual verification.
- **Stale cache entries** (PRD risk: "a cached answer outlives a change") —
  content-hash-keyed cache (BR6) handles file edits; a change to the
  worker model or prompt wording is also covered since both are part of
  the key.
