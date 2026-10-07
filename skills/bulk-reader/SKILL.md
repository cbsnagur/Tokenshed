---
name: bulk-reader
description: Delegate a question about one or more large files to a cheap worker model instead of reading the whole file yourself. Use this whenever the Read hook blocks a whole-file read, or before attempting to Read a file you expect to be large.
group: tokenshed
---

# Bulk Reader

Tokenshed's Read hook blocks a whole-file `Read` of any text file over the
configured line threshold (350 lines by default) and tells you to use this
instead. The point is to keep large files out of your own context: the
worker model reads them, and only its short answer comes back to you.

## When to use it

- "What does this file/service do?"
- "Which methods across these files touch the database / call this API /
  handle X?"
- Any other question you can answer from a file's *contents* without
  needing to reason about it yourself or change it.

## When NOT to use it

- **Debugging.** Never delegate root-causing a bug — read the relevant
  region yourself with `grep -n` then a partial `Read`.
- **Editing.** bulk-read only answers questions; it never touches the file.
  To edit, find the region first, then `Read` with `offset`/`limit`.
- **Small files.** If the file is already under the threshold, just `Read`
  it — there is nothing to save here.
- **Design decisions.** Anything that requires judgment about correctness,
  architecture, or trade-offs stays with you. The worker only summarizes
  and cites; it doesn't decide anything.

## Syntax

```
python3 "$CLAUDE_PLUGIN_ROOT/scripts/bulk_read.py" \
  --question "<your question>" \
  --paths <file1> [<file2> ...]
```

- `--question` (required): a single, specific question. Vague questions
  produce vague, less useful answers.
- `--paths` (required, one or more): the files to read. You can pass
  several files in one call to answer a question that spans them, instead
  of running bulk-read once per file.
- `--no-cache` (optional): force a fresh call even if an identical
  question against these exact file contents was answered before.

The answer is printed to stdout, in terse bullets, citing file paths and
line numbers where relevant. If a previous identical call already answered
this exact question against these exact file contents, the output is
prefixed with `(cached)` and no network call is made — you don't need to
do anything differently in that case, just read the answer.

Worker token spend from this call is recorded to the local stats ledger
(see `/tokenshed:report`), attributed to the current session unless
`TOKENSHED_SESSION` overrides it.

## Example

```
python3 "$CLAUDE_PLUGIN_ROOT/scripts/bulk_read.py" \
  --question "which methods in these files write to the database" \
  --paths src/services/user_service.py src/services/order_service.py
```
