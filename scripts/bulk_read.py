#!/usr/bin/env python3
"""tokenshed bulk-read: answer a question about one or more files using a
cheap worker model, so only the answer — never the files — enters
Claude's context. Implements BR1-BR8 from the PRD.
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _api import ApiError, chat_completion, get_config  # noqa: E402
from _cache import cache_enabled, compute_key, default_cache_dir, load_entry, store_entry  # noqa: E402
from _files import read_text, wrap_file  # noqa: E402
from _stats import record  # noqa: E402

PROMPT_VERSION = "v1"
DEFAULT_MAX_BYTES = 1_500_000

SYSTEM_PROMPT = (
    "You are a fast code-reading assistant helping a coding agent avoid "
    "reading large files itself. Answer the question using only the "
    "provided files. Respond in terse bullet points. Cite file paths and "
    "line numbers (from the numbering in each <file> block) when relevant. "
    "If the files do not contain the answer, say so plainly instead of "
    "guessing."
)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="bulk-read",
        description="Delegate a bulk file-reading question to a cheap worker model.",
    )
    parser.add_argument("--question", required=True)
    parser.add_argument("--paths", nargs="+", required=True)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--max-bytes", type=int, default=None)
    return parser.parse_args(argv)


def fail(message: str, code: int = 1):
    print(f"bulk-read: {message}", file=sys.stderr)
    sys.exit(code)


def _max_bytes(override):
    if override is not None:
        return override
    raw = os.environ.get("TOKENSHED_MAX_BYTES", "").strip()
    if not raw:
        return DEFAULT_MAX_BYTES
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_MAX_BYTES


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    missing = [p for p in args.paths if not os.path.isfile(p)]
    if missing:
        fail("file(s) not found: " + ", ".join(missing))

    max_bytes = _max_bytes(args.max_bytes)
    total_bytes = sum(os.path.getsize(p) for p in args.paths)
    if total_bytes > max_bytes:
        fail(
            f"request is {total_bytes} bytes, over the {max_bytes}-byte "
            f"limit (TOKENSHED_MAX_BYTES); split the file list across "
            f"multiple bulk-read calls"
        )

    try:
        config = get_config()
    except ApiError as exc:
        fail(str(exc))

    file_hashes = []
    wrapped_sections = []
    for path in args.paths:
        content = read_text(path)
        file_hashes.append(
            [path, hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()]
        )
        wrapped_sections.append(wrap_file(path, content))

    normalized_question = " ".join(args.question.split())
    use_cache = cache_enabled()
    cache_dir = default_cache_dir()
    cache_key = compute_key(normalized_question, config.model, PROMPT_VERSION, file_hashes)

    if use_cache and not args.no_cache:
        cached_answer = load_entry(cache_dir, cache_key)
        if cached_answer is not None:
            print(f"(cached) {cached_answer}")
            return 0

    user_prompt = (
        f"Question: {normalized_question}\n\n" + "\n\n".join(wrapped_sections)
    )

    try:
        answer, usage = chat_completion(SYSTEM_PROMPT, user_prompt, config=config)
    except ApiError as exc:
        fail(str(exc))

    record(
        kind="worker",
        script="bulk_read",
        model=config.model,
        spent_tokens=usage.get("total_tokens", 0),
    )

    print(answer)

    if use_cache:
        store_entry(cache_dir, cache_key, answer)

    return 0


if __name__ == "__main__":
    sys.exit(main())
