# Contributing to Tokenshed

Thanks for considering it. This project is small on purpose — see
`PLAN.md` for the full build plan and design goals before diving in.

## Getting started

```
git clone https://github.com/<owner>/tokenshed.git
cd tokenshed
python3 -m unittest discover -s evals -p "test_*.py"
```

No install step, no virtualenv, no `pip install -r requirements.txt` — the
whole point of this project is that it needs none. If tests don't pass on a
clean checkout, that's a bug; open an issue.

To run just one file's tests, e.g. while working on the Read hook:

```
python3 -m unittest evals.hooks.test_read_hook -v
```

To try a script or hook manually against a real (or local Ollama) worker,
set the three `TOKENSHED_*` env vars from the README and run it directly:

```
export TOKENSHED_MODEL=qwen2.5-coder:7b
export TOKENSHED_API_BASE=http://localhost:11434/v1
python3 scripts/bulk_read.py --question "what does this do" --paths README.md
```

## Where to find work

`PLAN.md`'s **Open items before v1.0 release** and **Later (v1.x and v2)**
sections are the current backlog — pick anything there, or open an issue
first if you want to propose something not listed. Small, well-scoped PRs
(one hook, one script, one requirement ID) are much easier to review than
broad ones.

## Project layout

| Path | What lives there |
|---|---|
| `hooks/` | The Read and Bash `PreToolUse` hooks and their shared helpers |
| `scripts/` | `bulk_read.py`, `code_write.py`, `doctor.py`, and the shared `_api`/`_cache`/`_files` modules they import |
| `skills/` | `SKILL.md` files telling Claude when/how to use each script |
| `commands/` | The `/tokenshed:doctor` slash command |
| `evals/` | All tests, mirroring the layout above (`evals/hooks/`, `evals/scripts/`, `evals/benchmarks/`) |
| `.claude-plugin/` | Plugin and marketplace manifests |

## Ground rules for any change

- **Stdlib only, still.** No dependencies beyond the Python 3.9+ standard
  library in anything under `hooks/`, `scripts/`, `skills/`, or
  `commands/` — see the section below. Dev-only tooling is exempt.
- **Fail open.** A hook (or anything a hook calls) must never turn an
  unexpected error into a blocked session. If you touch `hooks/`, keep the
  outer `try/except` in `__main__` intact and add a test that malformed
  input still exits 0.
- **No shell string-building.** Subprocess calls take argument lists,
  never an interpolated shell string; JSON goes through `json.dumps`/
  `json.load`, never string concatenation. This is what keeps file
  contents from being able to inject anything.
- **Never leak the API key.** `TOKENSHED_API_KEY` is read from the
  environment only. If you touch `scripts/_api.py` or `scripts/doctor.py`,
  double-check no code path can print, log, or embed it in an exception
  message — there's a test (`test_doctor.py::test_key_leak_detected_...`)
  that checks this for the doctor command specifically; extend it if you
  add a new place the key could leak.
- **Match a requirement ID where one exists.** The PRD's requirement IDs
  (R1–R4, B1–B4, BR1–BR8, CW1–CW4, S1–S2) are referenced in code comments
  and test names throughout — see `PLAN.md`'s requirement map. If your
  change implements or touches one, reference it in the PR description.

## Core constraint: stdlib only

Tokenshed ships as hooks and scripts with **no dependencies beyond the
Python 3.9+ standard library** — no `requests`, no `pip install` step, no
virtualenv required for end users. This is a deliberate design goal (see
`PLAN.md`), not an oversight: it's what keeps install to "clone/copy a
folder" instead of a package manager and a lockfile.

Before adding an `import` for anything outside the standard library, check
whether `urllib`, `json`, `hashlib`, `subprocess`, `shlex`, or another stdlib
module already covers it. If you believe a dependency is genuinely
necessary, raise it as an issue first — it changes the install story for
every user.

Dev-only tooling (test runners, linters) may use third-party packages since
they never ship to end users; keep them out of anything under `hooks/`,
`scripts/`, `skills/`, or `commands/`.

## Test runner

Tests use the standard library's `unittest` (via `python -m unittest
discover`), for the same stdlib-only reason. Do not add `pytest` as a
requirement for running the eval suite.

New behavior needs a new test. Hooks and scripts are both plain, importable
modules with a `main()`/`evaluate()`/`run_task()` entry point specifically
so tests can exercise them directly (see any file under `evals/`) instead of
only via subprocess — prefer that pattern for speed, and add one
subprocess-level test per script/hook to confirm the real CLI/stdin
contract still holds.

## Portability

Code under `hooks/` and `scripts/` must run unmodified on macOS, Linux, and
Windows (via WSL) under Python 3.9+. Avoid POSIX-only assumptions (path
separators, shell built-ins) outside of code that is explicitly
Bash-hook-specific.

## Before opening a PR

- `python3 -m unittest discover -s evals -p "test_*.py"` passes locally.
- Any new script or hook behavior has eval coverage, including a
  fail-open/error-path case if it's a hook.
- README.md and `PLAN.md` are updated if the change affects install steps,
  config vars, or the requirement/phase map.
