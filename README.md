# replmux

Persistent python repl for agents. Did you every want an agent to do data analysis on python? Want it not to load a 100Gb dataset every time? Want it not to waste tokens on boiler plate every time? Want it to use repl like a normal person?

`replmux` runs a long-lived Python process. Recommended to run inside `tmux`. And lets another shell (where your agent is) send Python code into the persistent session.

## Install

From the project where you want to use `replmux`, add it as a dev dependency:

```bash
uv add --dev git+https://github.com/eduardomazevedo/replmux
```

## Usage

Start the persistent REPL server:

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
