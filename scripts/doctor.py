#!/usr/bin/env python3
"""tokenshed doctor: checks settings, reaches the worker API with a tiny
test call, and warns if TOKENSHED_API_KEY appears to be committed in a
tracked file. Never prints the key's value, only where it was found.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _api import ApiError, chat_completion, get_config  # noqa: E402


def check_key_leak(cwd: str):
    """Return None if there's nothing to check (no key set, or not a git
    repo), else a (possibly empty) list of 'path:line' findings."""
    key = os.environ.get("TOKENSHED_API_KEY", "").strip()
    if not key:
        return None

    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    findings = []
    for rel_path in result.stdout.splitlines():
        abs_path = os.path.join(cwd, rel_path)
        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if key in line:
                        findings.append(f"{rel_path}:{lineno}")
                        break
        except OSError:
            continue
    return findings


def main(cwd=None):
    cwd = cwd or os.getcwd()
    ok = True

    print("tokenshed doctor")
    print("================")

    model = os.environ.get("TOKENSHED_MODEL", "").strip()
    if model:
        print(f"[PASS] TOKENSHED_MODEL is set ({model})")
    else:
        print("[FAIL] TOKENSHED_MODEL is not set")
        ok = False

    api_base = os.environ.get("TOKENSHED_API_BASE", "https://api.openai.com/v1")
    print(f"[INFO] TOKENSHED_API_BASE = {api_base}")

    has_key = bool(os.environ.get("TOKENSHED_API_KEY", "").strip())
    print(
        f"[INFO] TOKENSHED_API_KEY is "
        f"{'set' if has_key else 'not set (fine for local Ollama)'}"
    )

    if model:
        try:
            config = get_config()
            chat_completion(
                "Reply with a single word.", "Say OK.", config=config
            )
            print("[PASS] worker API reachable and responding")
        except ApiError as exc:
            print(f"[FAIL] worker API check failed: {exc}")
            ok = False
    else:
        print("[SKIP] worker API check (TOKENSHED_MODEL not set)")

    findings = check_key_leak(cwd)
    if findings:
        print("[FAIL] TOKENSHED_API_KEY value appears to be committed:")
        for finding in findings:
            print(f"       {finding}")
        ok = False
    elif findings is not None:
        print("[PASS] no tracked file contains the TOKENSHED_API_KEY value")
    else:
        print("[SKIP] key-leak scan (no TOKENSHED_API_KEY set, or not a git repo)")

    print()
    print("All checks passed." if ok else "Some checks failed — see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
