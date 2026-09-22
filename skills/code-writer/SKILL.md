---
name: code-writer
description: Delegate generating new boilerplate that closely follows an existing pattern to a cheap worker model, so the generated code never enters your context. Use for pattern-following generation like "write tests for X like the ones in Y", never for edits or design decisions.
group: tokenshed
---

# Code Writer

Generates a new file by imitating one or more reference files, using the
same cheap worker model bulk-reader uses. With `--target` set, the worker's
output is written straight to disk and only a one-line summary comes back
to you — the generated code itself never enters your context.

## When to use it

- "Write tests for `UserService` like the ones in `OrderTest`."
- "Add a new API route like the other routes in this file."
- Any other case where you'd otherwise write a large new file mostly by
  copying an existing pattern.

## When NOT to use it

- **Editing existing code.** code-write only ever produces a new file
  (or stdout); it never modifies an existing one in place.
- **Anything needing judgment about correctness or design.** If the task
  requires deciding *how* something should work, not just *what shape* it
  should have, do it yourself.
- **Small or one-off snippets.** If what you'd write is only a few lines,
  writing it directly is faster than the round-trip to a worker model.
- **Debugging.** Never delegate figuring out why something is broken.

## Syntax

```
python3 "$CLAUDE_PLUGIN_ROOT/scripts/code_write.py" \
  --spec "<what to write>" \
  --reference <file1> [<file2> ...] \
  [--target <output path>] \
  [--force]
```

- `--spec` (required): describe what the new file should do, precisely
  enough that "follow the pattern of the reference files" is the only
  judgment call left.
- `--reference` (required, one or more): the file(s) whose style,
  conventions, and imports the new code should match.
- `--target` (optional): where to write the result. **When set, the
  generated code is written directly to this path and never printed** —
  you'll see only a one-line summary (e.g. `wrote 84 lines to
  tests/test_user_service.py`). Omitting `--target` prints the code to
  stdout instead, for cases where you want to look at it before deciding
  where it goes.
- `--force` (optional): required if `--target` already exists. Without it,
  code-write refuses to overwrite anything.

After a `--target` write, **read the written file yourself** with a normal
(small, partial-friendly) `Read` to verify it before relying on it — the
worker's output is not automatically trustworthy just because it was
written to disk.

Worker token spend from this call is recorded to the local stats ledger
(see `/tokenshed:report`), attributed to the current session unless
`TOKENSHED_SESSION` overrides it.

## Example

```
python3 "$CLAUDE_PLUGIN_ROOT/scripts/code_write.py" \
  --spec "write tests for UserService, covering create/update/delete, in the same style as OrderTest" \
  --reference tests/test_order_service.py src/services/user_service.py \
  --target tests/test_user_service.py
```
