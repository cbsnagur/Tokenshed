# Tokenshed

A lightweight, open-source Claude Code plugin that cuts token usage by
routing bulk file reading and boilerplate generation to a cheap model you
choose, over any OpenAI-compatible API — including local models via Ollama.

Coding agents spend most of their tokens reading large files into context,
often to answer a narrow question. A 4,000-line file costs over 30,000
tokens to read whole, even when the agent needs five facts from it. Written
rules like "don't read big files" in `CLAUDE.md` are routinely ignored.
Tokenshed enforces the rule with hooks instead: a whole-file `Read` (or
`cat`/`less`/`more`/`head`/`tail`) over a configurable line threshold is
blocked, and the block message tells Claude to delegate the question to a
worker model instead. Only the worker's short answer enters Claude's
context — never the file itself.

## Install

```
claude plugin marketplace add cbsnagur/tokenshed
claude plugin install tokenshed@tokenshed
```

Then set three environment variables in your shell profile (only
`TOKENSHED_MODEL` is required):

```
export TOKENSHED_MODEL=gemini-2.5-flash        # any model your provider serves
export TOKENSHED_API_BASE=https://api.openai.com/v1   # optional, this is the default
export TOKENSHED_API_KEY=sk-...                # optional, e.g. not needed for Ollama
```

Start a new Claude Code session — hooks and skills load automatically.
Optionally run `/tokenshed:doctor` to confirm your settings and worker API
are reachable.

### Manual install (no marketplace)

Copy `hooks/`, `scripts/`, `skills/`, and `commands/` into your project's
`.claude/` directory.

## Quick start: hosted model (default)

The fastest path uses a cheap hosted model — no local hardware, no setup
beyond an API key:

```
export TOKENSHED_MODEL=gemini-2.5-flash
export TOKENSHED_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai
export TOKENSHED_API_KEY=<your Gemini API key>
```

**This means your code leaves your machine and goes to the provider you
configure.** If you work on proprietary, regulated, or client code, or your
employer restricts sending code to third parties, use the local Ollama
setup below instead.

## Alternative: local worker with Ollama

```
# Local worker: code never leaves your machine
ollama pull qwen2.5-coder:7b
export TOKENSHED_API_BASE=http://localhost:11434/v1
export TOKENSHED_MODEL=qwen2.5-coder:7b
```

No `TOKENSHED_API_KEY` needed. Nothing is sent anywhere outside your
machine — this is the right choice for proprietary or regulated code, or if
your employer restricts sending code to third-party services. Trade-off:
needs a capable machine (16GB RAM or more), and is slower and somewhat less
accurate than a hosted model.

|  | Hosted cheap model | Ollama (local) |
|---|---|---|
| Where your code goes | To the provider's servers | Nowhere; stays on your machine |
| API key needed | Yes | No |
| Cost per call | Small, per token | Free after setup |
| Works offline | No | Yes |
| Trade-offs | None on hardware | Needs a capable machine; slower, less accurate with small models |

## Supported providers

| Provider | `TOKENSHED_API_BASE` | Notes |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | Default |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | Gemini's OpenAI-compatible endpoint |
| OpenRouter | `https://openrouter.ai/api/v1` | One key for many models |
| Ollama (local) | `http://localhost:11434/v1` | No key; code stays on the machine |

Any other OpenAI-compatible endpoint works too.

## Configuration reference

All settings are environment variables.

| Variable | Default | Purpose |
|---|---|---|
| `TOKENSHED_MODEL` | none (**required**) | Worker model name, e.g. `gemini-2.5-flash` |
| `TOKENSHED_API_BASE` | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `TOKENSHED_API_KEY` | none | API key; not needed for local Ollama |
| `TOKENSHED_MIN_LINES` | `350` | Threshold above which whole-file reads are blocked |
| `TOKENSHED_TEMPERATURE` | `0.2` | Worker temperature; `none` omits it for models that reject it |
| `TOKENSHED_TIMEOUT` | `180` | Request timeout in seconds |
| `TOKENSHED_MAX_BYTES` | `1500000` | Largest bulk-read request allowed before refusing |
| `TOKENSHED_CACHE` | `on` | Set to `off` to disable the bulk-read answer cache |
| `TOKENSHED_CACHE_DIR` | user cache dir | Where cached answers are stored |
| `TOKENSHED_ALLOWLIST` | none | Comma-separated glob patterns always allowed regardless of size |

### Per-project allow-list

To always allow certain large files (generated lockfiles, vendored code,
etc.) regardless of size, list glob patterns one per line in
`.claude/tokenshed-allow.txt` at your project root:

```
# .claude/tokenshed-allow.txt
*.lock
vendor/**
```

## How it works

Three layers, from hard enforcement to soft guidance:

1. **Hooks** (`hooks/`) — block a whole-file `Read`, or `cat`/`less`/`more`
   on a large file, or `head`/`tail` asking for more lines than the
   threshold. Commands that pipe or redirect their output always pass
   through, since their output isn't landing raw in Claude's context.
   Partial reads (`offset`/`limit`), small files, binary files, missing
   files, and allow-listed paths are always allowed. Hooks **fail open** —
   any unexpected error lets the call through rather than breaking your
   session.
2. **Scripts** (`scripts/`) — `bulk_read.py` answers a question about one
   or more files using the worker model; `code_write.py` generates new
   boilerplate that follows a reference file's pattern. Both talk to the
   worker over `TOKENSHED_API_BASE` using only the Python standard
   library — no dependencies to install.
3. **Skills** (`skills/`) — tell Claude when to reach for each script, when
   not to, and the exact syntax. See `skills/bulk-reader/SKILL.md` and
   `skills/code-writer/SKILL.md`.

bulk-read caches each answer on local disk, keyed on the question, the
model, and a hash of every file's contents — so repeating a question about
unchanged files costs nothing, and editing any file invalidates the cache
entry automatically.

## Privacy and security

- Files go only to the endpoint in `TOKENSHED_API_BASE`. No telemetry,
  analytics, or phone-home of any kind.
- A hosted worker means your code leaves your machine; use Ollama (above)
  if it can't.
- The answer cache lives in your own cache directory
  (`TOKENSHED_CACHE_DIR`, default `~/.cache/tokenshed` on Linux), never
  inside a project repo where it could be committed.
- No shell string-building: scripts pass arguments as arrays and build
  JSON with a real serializer, so file contents can't inject commands or
  break requests.
- `code-write` never overwrites an existing file without `--force`, and
  writes only to the exact path given.
- `TOKENSHED_API_KEY` is read from the environment only — never printed,
  logged, or included in error messages. Run `/tokenshed:doctor` to check
  it hasn't been accidentally committed to a tracked file.

## Repo layout

```
tokenshed/
├── .claude-plugin/        # Plugin and marketplace manifests
├── hooks/                 # Hook registration plus the Read and Bash hooks
├── scripts/                # bulk-read, code-write, doctor, and the shared API helper
├── skills/                 # bulk-reader and code-writer skill files
├── commands/                # The /tokenshed:doctor command
└── evals/                  # Hook, script, and doctor test cases
```

See [`PLAN.md`](PLAN.md) for the full build plan, phase status, and what's
still open before a v1.0 release.

## Contributing

Want to help? See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to get set
up, the project's ground rules (stdlib-only, fail-open hooks, no shell
string-building), and where to find open work.

## License

MIT — see [`LICENSE`](LICENSE).
