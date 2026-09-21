# Tokenshed

A lightweight, open-source Claude Code plugin that cuts token usage by
routing bulk file reading and boilerplate generation to a cheap model you
choose, over any OpenAI-compatible API — including local models via Ollama.

**Status:** under active development. See [`PLAN.md`](PLAN.md) for the full
build plan and [`plans/`](plans/) for the phase-by-phase breakdown. This
README will be filled out in Phase 3 (skills & packaging) with install
instructions, provider configuration, and usage.

## Why

Coding agents spend most of their tokens reading large files into context,
often to answer a narrow question. Tokenshed blocks whole-file reads over a
configurable line threshold and reroutes them to a worker model, returning
only a short answer to Claude's context — enforced with hooks, not
instructions.

## License

MIT — see [`LICENSE`](LICENSE).
