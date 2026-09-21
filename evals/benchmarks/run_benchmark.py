#!/usr/bin/env python3
"""Tokenshed benchmark harness (scaffold).

Compares, per task: the token cost of Claude reading the target file(s)
whole ("hooks off" baseline) against the token cost of only the
bulk-read answer entering context ("hooks on"). Uses a rough ~4-char/token
estimate (see estimate_tokens.py) rather than real Claude Code token
counts — see README.md in this directory for what a full benchmark run
still needs beyond this scaffold (real repos, real Claude Code sessions,
human-graded answer quality, and a live worker model).

Requires TOKENSHED_MODEL (and friends) to be set, exactly like the real
plugin — this harness calls the real bulk_read.py script, unmodified.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(BENCH_DIR))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
DEFAULT_TASKS_DIR = os.path.join(BENCH_DIR, "tasks")

sys.path.insert(0, BENCH_DIR)
from estimate_tokens import estimate_tokens  # noqa: E402


def load_tasks(tasks_dir: str):
    tasks = []
    for path in sorted(glob.glob(os.path.join(tasks_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as fh:
            task = json.load(fh)
        task["_source"] = path
        tasks.append(task)
    return tasks


def resolve_task_paths(task: dict):
    return [os.path.join(BENCH_DIR, p) for p in task["paths"]]


def quality_hits(answer: str, answer_key):
    """Crude automated sanity signal: how many answer-key phrases have at
    least one significant word appearing in the answer. NOT a substitute
    for real human/LLM grading — see README.md."""
    answer_lower = answer.lower()
    hits = 0
    for phrase in answer_key:
        words = [w for w in phrase.lower().split() if len(w) > 3]
        if any(w in answer_lower for w in words):
            hits += 1
    return hits, len(answer_key)


def run_task(task: dict):
    paths = resolve_task_paths(task)
    missing = [p for p in paths if not os.path.isfile(p)]
    if missing:
        return {"id": task["id"], "error": f"missing fixture file(s): {missing}"}

    baseline_text = ""
    for p in paths:
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            baseline_text += fh.read()
    baseline_tokens = estimate_tokens(baseline_text) + estimate_tokens(task["question"])

    argv = [
        sys.executable,
        os.path.join(SCRIPTS_DIR, "bulk_read.py"),
        "--question",
        task["question"],
        "--paths",
        *paths,
    ]
    start = time.perf_counter()
    result = subprocess.run(argv, capture_output=True, text=True, timeout=300)
    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        return {"id": task["id"], "error": result.stderr.strip()}

    raw_answer = result.stdout.strip()
    cached = raw_answer.startswith("(cached)")
    answer = raw_answer[len("(cached) "):] if cached else raw_answer
    delegated_tokens = estimate_tokens(answer) + estimate_tokens(task["question"])

    hits, total = quality_hits(answer, task.get("answer_key", []))

    return {
        "id": task["id"],
        "baseline_tokens": baseline_tokens,
        "delegated_tokens": delegated_tokens,
        "pct_saved": 1 - (delegated_tokens / baseline_tokens) if baseline_tokens else 0,
        "latency_s": round(elapsed, 2),
        "cached": cached,
        "quality_hits": f"{hits}/{total}",
        "answer": answer,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the Tokenshed benchmark scaffold.")
    parser.add_argument("--tasks-dir", default=DEFAULT_TASKS_DIR)
    args = parser.parse_args(argv)

    if not os.environ.get("TOKENSHED_MODEL", "").strip():
        print(
            "run_benchmark: TOKENSHED_MODEL is not set. Configure a worker "
            "model (see README.md) before running the benchmark.",
            file=sys.stderr,
        )
        return 1

    tasks = load_tasks(args.tasks_dir)
    if not tasks:
        print(f"run_benchmark: no task files found in {args.tasks_dir}", file=sys.stderr)
        return 1

    results = [run_task(task) for task in tasks]

    ok_results = [r for r in results if "error" not in r]
    for r in results:
        if "error" in r:
            print(f"[ERROR] {r['id']}: {r['error']}")
            continue
        print(
            f"[{r['id']}] baseline={r['baseline_tokens']} tokens, "
            f"delegated={r['delegated_tokens']} tokens, "
            f"saved={r['pct_saved']:.0%}, latency={r['latency_s']}s, "
            f"cached={r['cached']}, quality={r['quality_hits']}"
        )

    if ok_results:
        avg_saved = sum(r["pct_saved"] for r in ok_results) / len(ok_results)
        print(f"\naverage tokens saved: {avg_saved:.0%} across {len(ok_results)} task(s)")

    return 0 if not any("error" in r for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
