#!/usr/bin/env python3
"""tokenshed report: prints blocked-read and worker-spend totals from the
local stats ledger, for the current session and lifetime.
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _stats import read_events, session_id, summarize  # noqa: E402

TITLE = "tokenshed report — tokens saved"
EMPTY_TOTALS = {"blocks": 0, "avoided_tokens": 0, "spent_tokens": 0, "saved_tokens": 0}

# (label, totals key, estimated) — estimated rows get a leading "~"
ROWS = [
    ("blocked reads", "blocks", False),
    ("tokens avoided", "avoided_tokens", True),
    ("worker tokens spent", "spent_tokens", False),
    ("tokens saved", "saved_tokens", True),
]


def format_section(totals):
    rows = []
    for label, key, estimated in ROWS:
        value = f"{totals.get(key, 0):,}"
        if estimated:
            value = "~" + value
        rows.append((label, value))
    label_width = max(len(label) for label, _ in rows)
    value_width = max(len(value) for _, value in rows)
    return [
        f"  {label:<{label_width}}  {value:>{value_width}}" for label, value in rows
    ]


def parse_since(raw):
    """YYYY-MM-DD -> epoch seconds at local midnight, or None if empty."""
    if not raw:
        return None
    try:
        dt = datetime.datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"invalid --since date {raw!r} (expected YYYY-MM-DD)")
    return dt.timestamp()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Show Tokenshed token-savings totals.")
    parser.add_argument("--session", help="report only this session (default: current + lifetime)")
    parser.add_argument("--since", help="drop events before this date (YYYY-MM-DD)")
    args = parser.parse_args(argv)

    try:
        cutoff = parse_since(args.since)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    events = read_events()
    if cutoff is not None:
        events = [e for e in events if e.get("ts", 0) >= cutoff]

    print(TITLE)
    print("=" * len(TITLE))

    if not events:
        print("no events recorded yet — nothing has been blocked or delegated so far.")
        return 0

    summary = summarize(events)
    sessions = summary.get("sessions", {})
    lifetime = summary.get("lifetime", EMPTY_TOTALS)

    if args.session:
        totals = sessions.get(args.session)
        if totals is None:
            print(f"no events recorded for session {args.session}")
            return 0
        print(f"Session {args.session}:")
        for line in format_section(totals):
            print(line)
        return 0

    current = session_id()
    totals = sessions.get(current, EMPTY_TOTALS)
    print(f"Session {current} (current):")
    for line in format_section(totals):
        print(line)
    print()
    print("Lifetime totals:")
    for line in format_section(lifetime):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
