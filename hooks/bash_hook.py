#!/usr/bin/env python3
"""Tokenshed Bash hook (PreToolUse).

Blocks `cat`/`less`/`more` on a large file, and `head`/`tail` when asked
for more lines than the threshold, unless the command pipes or redirects
its output. Implements B1-B4 from the PRD. Fails open on any error.
"""
import os
import shlex
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
    record_block,
    resolve_path,
    stamp_session,
)

READ_COMMANDS = {"cat", "less", "more"}
LIMITED_COMMANDS = {"head", "tail"}
SEQUENCE_OPERATORS = {";", "&&", "||", "&"}
PIPE_OR_REDIRECT = {"|", "|&", ">", ">>", "<", "<<"}
DEFAULT_HEAD_TAIL_LINES = 10


def tokenize(command: str):
    """Operator-aware tokenization: punctuation like |, >, ; and && come
    back as their own tokens instead of being glued to words."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def split_simple_commands(tokens):
    segments, current = [], []
    for tok in tokens:
        if tok in SEQUENCE_OPERATORS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def parse_files(args):
    return [a for a in args if not a.startswith("-")]


def parse_head_tail(args):
    """Return (requested_line_count_or_None, file_args)."""
    n = None
    files = []
    skip_next = False
    for i, tok in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if tok in ("-n", "--lines"):
            if i + 1 < len(args):
                try:
                    n = int(args[i + 1])
                except ValueError:
                    pass
                skip_next = True
            continue
        if tok.startswith("--lines="):
            try:
                n = int(tok.split("=", 1)[1])
            except ValueError:
                pass
            continue
        if tok.startswith("-n") and len(tok) > 2 and tok[2:].lstrip("+-").isdigit():
            try:
                n = int(tok[2:])
            except ValueError:
                pass
            continue
        if tok.startswith("-"):
            continue
        files.append(tok)
    return n, files


def check_large_file(path: str, cwd: str, threshold: int):
    """Return a deny reason for this path, or None to allow."""
    resolved = resolve_path(path, cwd)
    if not os.path.isfile(resolved):
        return None
    if is_allowlisted(resolved, cwd):
        return None
    if is_binary(resolved):
        return None
    count, capped = count_lines(resolved, threshold)
    if not capped and count <= threshold:
        return None
    record_block(resolved, "bash")
    return block_message(resolved, line_desc(count, capped), threshold)


def evaluate(data: dict):
    """Return a deny reason string, or None to allow."""
    if data.get("tool_name") != "Bash":
        return None

    command = (data.get("tool_input") or {}).get("command")
    if not command:
        return None

    cwd = data.get("cwd", "")
    threshold = read_threshold()

    try:
        tokens = tokenize(command)
    except ValueError:
        # Unbalanced quoting or similar: don't try to be clever about a
        # command we can't parse safely. Fail open.
        return None

    # B2: any pipe or redirect anywhere in the command lets it through —
    # output isn't landing raw in Claude's context the same way a direct
    # cat/less/more/head/tail to the terminal would.
    if any(tok in PIPE_OR_REDIRECT for tok in tokens):
        return None

    for segment in split_simple_commands(tokens):
        if not segment:
            continue
        cmd_name = os.path.basename(segment[0])
        args = segment[1:]

        if cmd_name in READ_COMMANDS:
            for file_arg in parse_files(args):
                reason = check_large_file(file_arg, cwd, threshold)
                if reason:
                    return reason

        elif cmd_name in LIMITED_COMMANDS:
            requested, files = parse_head_tail(args)
            effective = requested if requested is not None else DEFAULT_HEAD_TAIL_LINES
            if effective > threshold:
                for file_arg in files:
                    resolved = resolve_path(file_arg, cwd)
                    if not os.path.isfile(resolved):
                        continue
                    if is_allowlisted(resolved, cwd):
                        continue
                    record_block(resolved, "bash")
                    return block_message(
                        resolved,
                        f"requested {effective} lines via {cmd_name}",
                        threshold,
                    )

    return None


def main():
    data = read_stdin_json()
    stamp_session(data.get("session_id"))
    reason = evaluate(data)
    if reason is None:
        emit_allow()
    else:
        emit_deny(reason)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail open: never block a session on our own bug
        print(f"tokenshed: bash hook error, allowing call through: {exc}", file=sys.stderr)
        sys.exit(0)
