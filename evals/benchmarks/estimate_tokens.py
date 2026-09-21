"""A rough, stdlib-only token estimator for the benchmark scaffold.

This is NOT a real tokenizer — it's a ~4-chars-per-token rule of thumb
(the same order of magnitude the PRD itself uses: "A 4,000-line file
costs over 30,000 tokens to read whole"). It's good enough to sanity-check
the harness and to compare relative savings between two texts measured
the same way, but a real benchmark run (see README.md in this directory)
should replace it with actual token counts pulled from real Claude Code
session logs.
"""


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
