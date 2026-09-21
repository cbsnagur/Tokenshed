"""Shared file-reading and prompt-wrapping helpers for the worker scripts."""


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def wrap_file(path: str, content: str) -> str:
    """Requirement BR2: wrap a file in <file path="..."> tags with line
    numbers, so the worker's answer can cite exact lines."""
    lines = content.splitlines()
    numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
    return f'<file path="{path}">\n{numbered}\n</file>'
