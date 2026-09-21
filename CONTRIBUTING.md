# Contributing to Tokenshed

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

## Portability

Code under `hooks/` and `scripts/` must run unmodified on macOS, Linux, and
Windows (via WSL) under Python 3.9+. Avoid POSIX-only assumptions (path
separators, shell built-ins) outside of code that is explicitly
Bash-hook-specific.
