"""Token-savings ledger (see PLAN-feature-token-tracking.md).

Appends one JSON line per event — a hook denying a whole-file read
("block") or a worker script spending real tokens ("worker") — to a
per-user JSONL file, keyed by a session id that hooks and worker
scripts (separate processes) converge on via a marker file. Lives in
the same cache directory as `_cache.py`, never inside a project repo.
Recording is best-effort and fail-open: a ledger problem must never
break a hook or a worker script.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _cache import default_cache_dir  # noqa: E402


def stats_enabled() -> bool:
    return os.environ.get("TOKENSHED_STATS", "on").strip().lower() not in (
        "off",
        "0",
        "false",
        "no",
    )


def ledger_path() -> str:
    return os.path.join(default_cache_dir(), "stats.jsonl")


def marker_path() -> str:
    return os.path.join(default_cache_dir(), "session")


def session_id() -> str:
    env = os.environ.get("TOKENSHED_SESSION", "").strip()
    if env:
        return env
    try:
        with open(marker_path(), "r", encoding="utf-8") as fh:
            marker = fh.read().strip()
    except OSError:
        return "unknown"
    return marker or "unknown"


def stamp_session(sid) -> None:
    if not sid or not stats_enabled():
        return
    try:
        if session_id() == sid:
            return
        os.makedirs(default_cache_dir(), exist_ok=True)
        with open(marker_path(), "w", encoding="utf-8") as fh:
            fh.write(sid)
    except Exception:
        pass


def estimate_tokens(n_bytes: int) -> int:
    return max(0, n_bytes) // 4


def record(**event) -> None:
    if not stats_enabled():
        return
    try:
        event.setdefault("ts", int(time.time()))
        event.setdefault("session", session_id())
        os.makedirs(default_cache_dir(), exist_ok=True)
        with open(ledger_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
    except Exception:
        pass


def read_events(path=None) -> list:
    try:
        with open(path or ledger_path(), "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return []

    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _num(value) -> int:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _empty_totals() -> dict:
    return {"blocks": 0, "avoided_tokens": 0, "spent_tokens": 0, "saved_tokens": 0}


def summarize(events) -> dict:
    sessions = {}
    lifetime = _empty_totals()

    for event in events:
        sid = event.get("session", "unknown")
        totals = sessions.setdefault(sid, _empty_totals())
        if event.get("kind") == "block":
            totals["blocks"] += 1
            lifetime["blocks"] += 1
        avoided = _num(event.get("avoided_tokens", 0))
        spent = _num(event.get("spent_tokens", 0))
        totals["avoided_tokens"] += avoided
        totals["spent_tokens"] += spent
        lifetime["avoided_tokens"] += avoided
        lifetime["spent_tokens"] += spent

    for totals in sessions.values():
        totals["saved_tokens"] = totals["avoided_tokens"] - totals["spent_tokens"]
    lifetime["saved_tokens"] = lifetime["avoided_tokens"] - lifetime["spent_tokens"]

    return {"sessions": sessions, "lifetime": lifetime}
