"""Shared helpers for Tokenshed's Read and Bash hooks.

Stdlib only. Every function here is written to be cheap: hooks run on
every Read/Bash call and must stay well under 100ms even on large files.
"""
import fnmatch
import json
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "scripts"),
)
try:
    import _stats
except Exception:  # pragma: no cover - fail open if the ledger module is missing/broken
    _stats = None

DEFAULT_MIN_LINES = 350
BULK_READ_INVOCATION = (
    'python3 "$CLAUDE_PLUGIN_ROOT/scripts/bulk_read.py" '
    '--question "<your question>" --paths {path}'
)

# How many lines past the threshold we bother counting exactly before
# giving up and reporting "at least N". Keeps line-counting bounded on
# pathologically large files without losing the useful case (files a
# few thousand lines long) where an exact count is cheap and helpful.
COUNT_CAP_MULTIPLIER = 20


def read_threshold() -> int:
    raw = os.environ.get("TOKENSHED_MIN_LINES", "")
    try:
        value = int(raw) if raw.strip() else DEFAULT_MIN_LINES
        return value if value > 0 else DEFAULT_MIN_LINES
    except (ValueError, AttributeError):
        return DEFAULT_MIN_LINES


def read_stdin_json() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def resolve_path(path: str, cwd: str) -> str:
    """Resolve a possibly-relative path against the hook-provided cwd,
    never the hook process's own working directory (requirement B3)."""
    if not path:
        return path
    if os.path.isabs(path):
        return path
    base = cwd or os.getcwd()
    return os.path.normpath(os.path.join(base, path))


def is_binary(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(8192)
    except OSError:
        # Missing/unreadable file: not our problem, let the real tool
        # surface the error (requirement R2).
        return False
    return b"\x00" in chunk


def count_lines(path: str, threshold: int):
    """Return (count, capped). `capped` is True when we stopped early
    because the file is clearly over threshold * COUNT_CAP_MULTIPLIER
    lines; `count` is then a lower bound, not exact."""
    cap = threshold * COUNT_CAP_MULTIPLIER
    n = 0
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    return n, False
                n += chunk.count(b"\n")
                if n > cap:
                    return n, True
    except OSError:
        return 0, False


def load_allow_patterns(cwd: str):
    """Requirement R4: a per-project list of path globs that are always
    allowed regardless of size. One glob per line in
    <cwd>/.claude/tokenshed-allow.txt (lines starting with # ignored),
    plus a comma-separated TOKENSHED_ALLOWLIST env var for quick/CI use."""
    patterns = []
    allow_file = os.path.join(cwd or os.getcwd(), ".claude", "tokenshed-allow.txt")
    try:
        with open(allow_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    except OSError:
        pass

    env_patterns = os.environ.get("TOKENSHED_ALLOWLIST", "")
    patterns.extend(p.strip() for p in env_patterns.split(",") if p.strip())
    return patterns


def is_allowlisted(path: str, cwd: str) -> bool:
    patterns = load_allow_patterns(cwd)
    if not patterns:
        return False
    base = cwd or os.getcwd()
    try:
        rel = os.path.relpath(path, base)
    except ValueError:
        rel = path
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path, pattern):
            return True
    return False


def emit_allow():
    # Silent allow: no stdout, no JSON, exit 0. The hook simply doesn't
    # report itself as having made a decision.
    sys.exit(0)


def emit_deny(reason: str):
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(2)


def block_message(path: str, line_desc: str, threshold: int) -> str:
    """Requirement R3: name the file, its line count, the bulk-read
    command to use, and the grep-then-partial-read route for edits."""
    return (
        f"tokenshed: blocked a whole-file read of {path} ({line_desc}, "
        f"over the {threshold}-line threshold).\n"
        f"To understand the file, delegate to the worker model:\n"
        f"  {BULK_READ_INVOCATION.format(path=path)}\n"
        f"To edit the file, find the region first, then read only that "
        f"part:\n"
        f'  grep -n "<pattern>" {path}\n'
        f"  then Read {path} with offset/limit around the matching line."
    )


def line_desc(count: int, capped: bool) -> str:
    return f"at least {count} lines" if capped else f"{count} lines"


def stamp_session(sid) -> None:
    """Best-effort session marker write; never raises."""
    try:
        _stats.stamp_session(sid)
    except Exception:
        pass


def estimate_avoided_tokens(path) -> int:
    try:
        return _stats.estimate_tokens(os.path.getsize(path))
    except (OSError, AttributeError):
        return 0


def record_block(path, script) -> None:
    try:
        size = os.path.getsize(path)
        _stats.record(
            kind="block",
            script=script,
            file=path,
            bytes=size,
            avoided_tokens=_stats.estimate_tokens(size),
        )
    except Exception:
        pass
