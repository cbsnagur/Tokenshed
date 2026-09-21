---
name: doctor
description: Check Tokenshed's configuration, worker API reachability, and scan for a leaked API key.
group: tokenshed
---

Run the Tokenshed doctor script and show its complete, unedited output to
the user:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

Do not summarize, truncate, or paraphrase the output — every `[PASS]`,
`[FAIL]`, `[INFO]`, and `[SKIP]` line is meant to be read directly. If it
exits non-zero, show the failing checks; don't try to fix them yourself
unless the user asks you to.
