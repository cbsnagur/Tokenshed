"""bulk-read's answer cache (BR6-BR8).

Keyed on a SHA-256 of the normalized question, the model name, a prompt
version, and each file's path + content hash — so an edited file, a
model switch, or a prompt-wording change all invalidate automatically.
Lives in the user's cache directory, never inside a project repo.
Entries expire after 30 days; once the cache exceeds 50MB, oldest
entries are pruned first. All of this runs synchronously on write —
no background process.
"""
import hashlib
import json
import os
import time

MAX_AGE_DAYS = 30
MAX_CACHE_BYTES = 50 * 1024 * 1024


def default_cache_dir() -> str:
    override = os.environ.get("TOKENSHED_CACHE_DIR", "").strip()
    if override:
        return override
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "tokenshed", "Cache")
    if hasattr(os, "uname") and os.uname().sysname == "Darwin":
        return os.path.expanduser("~/Library/Caches/tokenshed")
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg:
        return os.path.join(xdg, "tokenshed")
    return os.path.expanduser("~/.cache/tokenshed")


def cache_enabled() -> bool:
    return os.environ.get("TOKENSHED_CACHE", "on").strip().lower() not in (
        "off",
        "0",
        "false",
        "no",
    )


def compute_key(question: str, model: str, prompt_version: str, file_hashes) -> str:
    payload = {
        "question": question,
        "model": model,
        "prompt_version": prompt_version,
        "files": sorted(file_hashes),
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _answers_dir(cache_dir: str) -> str:
    return os.path.join(cache_dir, "answers")


def _entry_path(cache_dir: str, key: str) -> str:
    return os.path.join(_answers_dir(cache_dir), f"{key}.json")


def load_entry(cache_dir: str, key: str):
    path = _entry_path(cache_dir, key)
    try:
        stat = os.stat(path)
    except OSError:
        return None

    # Age is judged by file mtime (matches _maintain's sweep) rather than
    # a "created" field baked into the JSON, so tests and tooling that
    # touch mtime directly stay consistent with real expiry behavior.
    age_days = (time.time() - stat.st_mtime) / 86400
    if age_days > MAX_AGE_DAYS:
        try:
            os.remove(path)
        except OSError:
            pass
        return None

    try:
        with open(path, "r", encoding="utf-8") as fh:
            entry = json.load(fh)
    except (OSError, ValueError):
        return None
    return entry.get("answer")


def store_entry(cache_dir: str, key: str, answer: str) -> None:
    answers_dir = _answers_dir(cache_dir)
    os.makedirs(answers_dir, exist_ok=True)
    path = _entry_path(cache_dir, key)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump({"answer": answer, "created": time.time()}, fh)
    os.replace(tmp_path, path)
    _maintain(answers_dir)


def _maintain(answers_dir: str) -> None:
    """Sweep expired entries, then prune oldest-first above the size cap."""
    try:
        names = os.listdir(answers_dir)
    except OSError:
        return

    now = time.time()
    entries = []
    for name in names:
        path = os.path.join(answers_dir, name)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        age_days = (now - stat.st_mtime) / 86400
        if age_days > MAX_AGE_DAYS:
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        entries.append((stat.st_mtime, stat.st_size, path))

    total = sum(size for _, size, _ in entries)
    if total <= MAX_CACHE_BYTES:
        return

    entries.sort(key=lambda e: e[0])  # oldest first
    for _, size, path in entries:
        if total <= MAX_CACHE_BYTES:
            break
        try:
            os.remove(path)
            total -= size
        except OSError:
            pass
