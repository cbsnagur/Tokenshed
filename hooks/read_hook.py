#!/usr/bin/env python3
"""Tokenshed Read hook (PreToolUse).

Blocks a whole-file Read of a large text file and points Claude at the
bulk-read script and the grep-then-partial-read route instead.
Implements R1-R4 from the PRD. Fails open: any unexpected error here
must allow the call through, never break the session.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    block_message,
    count_lines,
    emit_allow,
    emit_deny,
    is_allowlisted,
    is_binary,
    line_desc,
    read_stdin_json,
    read_threshold,
    resolve_path,
)


def evaluate(data: dict):
    """Return a deny reason string, or None to allow."""
    if data.get("tool_name") != "Read":
        return None

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        return None

    # R2: partial reads (offset or limit set) always proceed.
    if tool_input.get("offset") or tool_input.get("limit"):
        return None

    cwd = data.get("cwd", "")
    path = resolve_path(file_path, cwd)

    # R2: missing files are not our problem; let Read raise its own error.
    if not os.path.isfile(path):
        return None

    # R4: per-project allow-list always wins.
    if is_allowlisted(path, cwd):
        return None

    # R2: binary files are always allowed (bulk-read only understands text).
    if is_binary(path):
        return None

    threshold = read_threshold()
    count, capped = count_lines(path, threshold)

    # R2: small files pass straight through.
    if not capped and count <= threshold:
        return None

    # R1 + R3: block, naming the file, its line count, and both alternatives.
    return block_message(path, line_desc(count, capped), threshold)


def main():
    data = read_stdin_json()
    reason = evaluate(data)
    if reason is None:
        emit_allow()
    else:
        emit_deny(reason)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail open: never block a session on our own bug
        print(f"tokenshed: read hook error, allowing call through: {exc}", file=sys.stderr)
        sys.exit(0)
