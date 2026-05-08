---
name: replmux
description: Use when a user wants a persistent Python REPL shared between the agent and the user, especially for iterative data analysis.
---

# replmux

Use `replmux` to keep one Python process alive and send code into it.

## Setup

`replmux` should be installed as a dev dependency in the project where you want to use it: `uv add --dev git+https://github.com/eduardomazevedo/replmux`

## Workflow

1. If the server is not running, tell the user to start it in `tmux` with `uv run replmux start`. The user can use the tmux tab to see what you are doing, but you just start replmux and detach.
2. Send code with `uv run replmux run '...'`.
3. For multi-line code, pipe a heredoc into `uv run replmux run`.
5. Use `uv run replmux stop` to shut the session down.

## Notes

- Successful statements may return no output. That is normal.
- State persists across `run`.