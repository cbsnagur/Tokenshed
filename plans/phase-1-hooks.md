# Phase 1 — Hooks (PRD milestone M1)

**Goal:** the enforcement layer. Whole-file `Read` calls and equivalent
`Bash` commands (`cat`, `less`, `more`) over the line threshold are blocked
with a message pointing at the delegation path — before that path exists.
This is deliberately built first because, per the PRD, "enforcement is where
the savings come from": without it, savings depend on Claude remembering a
rule, which the PRD notes is routinely ignored.

**Depends on:** Phase 0 (repo scaffolding, manifest skeleton).
**Blocks:** Phase 2 (workers are only reachable once the hook's block
message can name them) and Phase 4 (hook latency/false-block benchmarks).

**Estimate:** ~1 week (Week 1).

## Requirements covered

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | Block a whole-file Read when the file has more lines than the threshold (default 350) | P0 |
| R2 | Allow partial reads (offset/limit set), small files, binary files, missing files | P0 |
| R3 | Block message names the file, its line count, the bulk-read command, and the grep-then-partial-read route | P0 |
| R4 | Per-project allow-list of paths always allowed (e.g. generated lockfiles) | P1 |
| B1 | Block `cat`, `less`, `more` when any file argument is over the threshold | P0 |
| B2 | Allow commands that pipe or redirect output, and all non-read commands | P0 |
| B3 | Resolve relative paths against the session's working directory | P0 |
| B4 | Block `head`/`tail` only when asked for more lines than the threshold | P1 |

## Task breakdown

1. **Hook registration** (`hooks/`)
   - Wire `PreToolUse`-style hooks (or whatever the current Claude Code hook
     event is called) for the `Read` tool and for `Bash`.
   - Read `TOKENSHED_MIN_LINES` (default 350) at hook invocation time — no
     caching across sessions, since a user editing the env var mid-session
     should take effect on the next call.

2. **Read hook** (R1–R4)
   - Determine "whole-file read": no `offset`/`limit` params set.
   - Count lines cheaply (avoid loading the whole file into memory just to
     block it — stream and count, or use file size as a fast pre-filter
     before a full line count).
   - Detect binary files (R2) — e.g. a null-byte sniff on the first N bytes
     — and always allow them through regardless of size.
   - Handle missing files (R2): let the call through so the underlying tool
     produces its normal "file not found" error; don't let the hook mask it.
   - Build the block message (R3): file path, line count, the exact
     `bulk-read --question ... --paths ...` invocation to run, and the
     `grep -n <pattern> <file>` then partial-`Read` alternative for edits.
   - Allow-list (R4): read a per-project config (e.g.
     `.claude/tokenshed.allow` or a key in the plugin's project settings)
     of path globs that are always allowed regardless of size. Lockfiles,
     generated code, etc.

3. **Bash hook** (B1–B4)
   - Parse the command safely (use `shlex.split`, never regex-splice the
     raw string) to find `cat`/`less`/`more`/`head`/`tail` invocations and
     their file arguments.
   - B3: resolve relative paths against the hook-provided working directory,
     not the hook process's own `cwd`.
   - B2: any command containing a pipe (`|`), redirect (`>`, `>>`), or a
     non-read command name must pass through unexamined — this hook only
     ever inspects the direct file-reading commands listed, never rewrites
     or blocks anything else.
   - B4: `head`/`tail` are only blocked when their explicit line count
     (`-n`) exceeds the threshold; with no `-n` (defaults to 10) or a small
     `-n`, allow.
   - Apply the same line-counting and allow-list logic as the Read hook so
     the two hooks agree on what counts as "large."

4. **Fail-open wrapper**
   - Wrap both hooks' entire body in a top-level try/except: on any
     unexpected exception, log to stderr (never stdout, never anything a
     user would have to parse as a block) and allow the call through. This
     is the single most important line of defense per the PRD's NFRs.

5. **Eval cases** (`evals/`, feeds Phase 4's fuller benchmark suite)
   - Table-driven cases per requirement ID above: large file → blocked,
     small file → allowed, partial read → allowed, binary → allowed,
     missing file → allowed through, allow-listed path → allowed,
     `cat bigfile.py | grep foo` → allowed, `head -n 5000 bigfile.py` →
     blocked, `head -n 5 bigfile.py` → allowed.
   - A timing case: run the hook against a generated 10,000-line file and
     assert wall-clock time is under 100 ms (PRD NFR).

## Deliverables

- `hooks/read_hook.py`, `hooks/bash_hook.py` (or equivalent single
  dispatch file, per whatever the finalized manifest from Phase 0 expects).
- Hook registration wired into the Phase 0 manifest.
- `evals/hooks/` test cases covering every ID above.

## Exit criteria (PRD M1)

- All hook eval cases pass.
- Hook latency confirmed under 100 ms on a 10,000-line file.

## Risks specific to this phase

- **False blocks** frustrating users if line-counting or path-resolution is
  wrong — mitigated by the eval suite and by allow-listing (R4).
- **Fail-open bugs**: an exception inside the fail-open handler itself would
  defeat the purpose — keep that handler trivial and covered by its own
  eval case.
