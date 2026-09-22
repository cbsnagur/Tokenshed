#!/usr/bin/env python3
"""tokenshed code-write: generate boilerplate that follows a given
pattern, using a cheap worker model, so the generated code never enters
Claude's context when written straight to disk. Implements CW1-CW4.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _api import ApiError, chat_completion, get_config  # noqa: E402
from _files import read_text, wrap_file  # noqa: E402
from _stats import record  # noqa: E402

SYSTEM_PROMPT = (
    "You are a code-generation assistant helping a coding agent produce "
    "boilerplate. Follow the spec exactly, matching the style, imports, "
    "and conventions of the reference files. Respond with ONLY the "
    "generated code for the new file, with no explanation before or "
    "after it. Prefer a single fenced code block."
)

FENCE_RE = re.compile(r"^```[a-zA-Z0-9_+-]*\n(.*?)\n```\s*$", re.DOTALL)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="code-write",
        description="Delegate pattern-following code generation to a cheap worker model.",
    )
    parser.add_argument("--spec", required=True)
    parser.add_argument("--reference", nargs="+", required=True)
    parser.add_argument("--target", default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def fail(message: str, code: int = 1):
    print(f"code-write: {message}", file=sys.stderr)
    sys.exit(code)


def strip_code_fences(text: str) -> str:
    """Requirement CW2: strip markdown code fences from the worker's reply."""
    stripped = text.strip()
    match = FENCE_RE.match(stripped)
    body = match.group(1) if match else stripped
    return body if body.endswith("\n") else body + "\n"


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    missing = [p for p in args.reference if not os.path.isfile(p)]
    if missing:
        fail("reference file(s) not found: " + ", ".join(missing))

    # CW4: refuse to overwrite an existing target unless --force.
    if args.target and os.path.exists(args.target) and not args.force:
        fail(f"target already exists: {args.target} (use --force to overwrite)")

    try:
        config = get_config()
    except ApiError as exc:
        fail(str(exc))

    wrapped_sections = [wrap_file(p, read_text(p)) for p in args.reference]
    user_prompt = (
        f"Spec: {args.spec}\n\nReference files (match their style and "
        f"conventions):\n\n" + "\n\n".join(wrapped_sections)
    )

    try:
        raw, usage = chat_completion(SYSTEM_PROMPT, user_prompt, config=config)
    except ApiError as exc:
        fail(str(exc))

    record(
        kind="worker",
        script="code_write",
        model=config.model,
        spent_tokens=usage.get("total_tokens", 0),
    )

    code = strip_code_fences(raw)

    if args.target:
        # CW3: write only to the exact path given, then print only a
        # one-line summary — the code itself never reaches stdout here.
        target_dir = os.path.dirname(os.path.abspath(args.target))
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        with open(args.target, "w", encoding="utf-8") as fh:
            fh.write(code)
        line_count = code.count("\n")
        print(f"wrote {line_count} lines to {args.target}")
    else:
        sys.stdout.write(code)

    return 0


if __name__ == "__main__":
    sys.exit(main())
