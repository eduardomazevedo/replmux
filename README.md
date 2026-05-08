# replmux

Persistent python repl for agents. Did you every want an agent to do data analysis on python? What it not to load 100Gb dataset every time? Want it not to repeat boiler plate before each command? Use repl like a normal person?

`replmux` runs a long-lived Python process, inside `tmux` or with `&`. Lets another shell send Python code into that same persistent session.

## Install

From the project where you want to use `replmux`, add it as a development dependency with `uv`:

```bash
uv add --dev git+https://github.com/eduardomazevedo/replmux
```

## Usage

Start the persistent REPL server in tmux:

```bash
tmux new -s replmux
replmux start
```

From another terminal, send code:

```bash
replmux run 'x = 41'
replmux run 'x + 1'
```

Send a multi-line block:

```bash
replmux run <<'PY'
def f(x):
    return x + 1

f(41)
PY
```

Join interactively:

```bash
replmux join
```

Stop the server:

```bash
replmux stop
```

## Security

None. Anyone who can connect to the Unix socket can execute Python code as your user.
