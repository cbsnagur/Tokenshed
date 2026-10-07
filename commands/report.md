---
name: report
description: Show how many tokens Tokenshed has saved this session and lifetime, by reading the local stats ledger.
group: tokenshed
---

Run the Tokenshed report script and show its complete, unedited output to
the user:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/report.py"
```

Do not summarize, truncate, or paraphrase the output — the session and
lifetime totals are meant to be read directly. Pass along `--session SID`
or `--since YYYY-MM-DD` if the user asks to filter the report; otherwise
run it with no arguments.
