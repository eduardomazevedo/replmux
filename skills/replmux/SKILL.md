---
name: replmux
description: Use when a user wants a persistent Python REPL shared between the agent and the user, especially for iterative data analysis.
---

# replmux

Use `replmux` to keep one Python process alive and send code into it.

## Setup

`replmux` should be installed as a dev dependency in the project where you want to use it: `uv add --dev git+https://github.com/eduardomazevedo/replmux`

## Workflow

1. Check whether a `tmux` session named `replmux` already exists:
   ```bash
   tmux has-session -t replmux 2>/dev/null
   ```
2. If it does not exist, start `replmux` detached inside `tmux` from the project directory:
   ```bash
   tmux has-session -t replmux 2>/dev/null || tmux new-session -d -s replmux "cd $(pwd) && uv run replmux start"
   ```
   The user can inspect the session in tmux.
3. Send code `uv run replmux run '...'`.
4. For multi-line code, pipe a heredoc into `uv run replmux run`.
5. Keep reusing the same REPL for follow-up commands instead of starting from scratch. For example, if you already loaded a dataframe into `df`, later commands should use `df` directly rather than re-importing and re-reading the same file unless you intentionally want a fresh state.
6. Use `uv run replmux stop` to shut down.

## Notes

- Reuse an existing `replmux` tmux session when present instead of creating a new one.
- State persists across `run`.
- Treat the session like a long-lived Python process: variables, imports, loaded data, and helper functions remain available to later `run` commands.
- Prefer incremental commands that build on existing state to avoid unnecessary repeated work.
