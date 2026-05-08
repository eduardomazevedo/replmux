---
name: replmux
description: Use when a user wants a persistent Python REPL shared between the agent and the user, especially for iterative data analysis.
---

# replmux

Use `replmux` to keep one Python process alive and send code into it. So for data analysis you can have a persistent REPL.

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
3. Send code `uv run replmux run 'df = load_data()'`. Then session persists: `uv run replmux run 'df["column"].mean()'` returns the value.
4. For multi-line code, pipe a heredoc:
   ```bash
   uv run replmux run <<'PY'
   x = 1
   print(x)
   PY
   ```
5. Use the same REPL for follow-up commands instead of starting from scratch.
6. Use `uv run replmux stop` to shut down.

## Notes

- Reuse an existing `replmux` tmux session when present instead of creating a new one.
- State persists across `run`.
- Treat the session like a long-lived Python process: variables, imports, loaded data, and helper functions remain available to later `run` commands.
- Prefer incremental commands that build on existing state to avoid unnecessary repeated work.
