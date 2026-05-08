#!/usr/bin/env python3
import ast
import codeop
import io
import os
import socket
import sys
import textwrap
import traceback

SOCKET_PATH = "/tmp/replmux_session.sock"

CHUNK_SIZE = 64 * 1024
MAX_MESSAGE_BYTES = 64 * 1024 * 1024

EXIT_COMMAND = "EXIT_SESSION"

BLUE = "\033[94m"
GREEN = "\033[92m"
RESET = "\033[0m"


def recv_all(sock, max_bytes=MAX_MESSAGE_BYTES):
    """
    Read until the peer closes or shutdowns its write side.

    This fixes the main protocol bug in the original version:
    one sendall() does not imply one recv().
    """
    chunks = []
    total = 0

    while True:
        chunk = sock.recv(CHUNK_SIZE)
        if not chunk:
            break

        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"message too large: exceeded {max_bytes} bytes")

        chunks.append(chunk)

    return b"".join(chunks).decode("utf-8", errors="replace")


def send_text(sock, text):
    sock.sendall(text.encode("utf-8"))


def console_write(text):
    """Write directly to the tmux-visible server console."""
    sys.__stdout__.write(text)
    sys.__stdout__.flush()


def print_result(result):
    if result is None:
        return

    if result.endswith("\n"):
        print(result, end="")
    else:
        print(result)


def prepare_socket_path():
    """
    Remove a stale socket, but refuse to overwrite a live server.
    This keeps the /tmp path from your original design.
    """
    if not os.path.exists(SOCKET_PATH):
        return

    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    try:
        probe.connect(SOCKET_PATH)
    except OSError:
        os.remove(SOCKET_PATH)
    else:
        raise RuntimeError(f"session already appears to be running at {SOCKET_PATH}")
    finally:
        probe.close()


def print_value(value):
    """
    REPL-style display hook.

    Stores the last expression result in _, like the normal Python REPL.
    """
    if value is not None:
        print(repr(value))


def execute_code(code, session_globals):
    """
    Execute code inside the persistent session namespace.

    Behavior:
      - Single expressions echo their repr.
      - Multi-statement blocks execute normally.
      - If a multi-statement block ends with an expression, echo that final value.
    """
    code = textwrap.dedent(code)

    if not code.strip():
        return

    filename = "<agent-repl>"

    session_globals.setdefault("__name__", "__main__")
    session_globals.setdefault("__builtins__", __builtins__)

    # First, try pure expression mode:
    #
    #   1 + 1
    #
    # should print:
    #
    #   2
    try:
        compiled_expr = compile(code, filename, "eval")
    except SyntaxError:
        compiled_expr = None

    if compiled_expr is not None:
        value = eval(compiled_expr, session_globals)
        session_globals["_"] = value
        print_value(value)
        return

    # Otherwise parse as a normal block. If the last top-level statement is an
    # expression, execute the earlier statements, then eval and display the last
    # expression. This gives notebook/cell-like behavior:
    #
    #   x = 40
    #   x + 2
    #
    # prints:
    #
    #   42
    tree = ast.parse(code, filename=filename, mode="exec")

    if tree.body and isinstance(tree.body[-1], ast.Expr):
        head = ast.Module(
            body=tree.body[:-1],
            type_ignores=tree.type_ignores,
        )
        ast.fix_missing_locations(head)

        if head.body:
            exec(compile(head, filename, "exec"), session_globals)

        tail_expr = ast.Expression(tree.body[-1].value)
        ast.fix_missing_locations(tail_expr)

        value = eval(compile(tail_expr, filename, "eval"), session_globals)
        session_globals["_"] = value
        print_value(value)
    else:
        exec(compile(tree, filename, "exec"), session_globals)


def start_session():
    """Start the persistent foreground Python process. Run this in tmux."""
    prepare_socket_path()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    bound = False

    try:
        server.bind(SOCKET_PATH)
        bound = True

        # Reasonable local-only permission for the socket file.
        try:
            os.chmod(SOCKET_PATH, 0o600)
        except OSError:
            pass

        server.listen(1)

        console_write(
            "========================================\n"
            "replmux server started in foreground\n"
            f"Listening on: {SOCKET_PATH}\n"
            "========================================\n\n"
        )   

        session_globals = {}

        while True:
            try:
                conn, _ = server.accept()
            except KeyboardInterrupt:
                console_write("\n[SYSTEM]: KeyboardInterrupt at server console. Shutting down.\n")
                break

            with conn:
                try:
                    code = recv_all(conn)
                except Exception as exc:
                    output = f"[PROTOCOL ERROR] {exc}\n"
                    console_write(output)
                    send_text(conn, output)
                    continue

                if code == EXIT_COMMAND:
                    output = "\n[SYSTEM]: Shutdown signal received. Closing server.\n"
                    console_write(output)
                    send_text(conn, output)
                    break

                console_write(f"\n{BLUE}[INCOMING COMMAND]{RESET}\n{code}\n")

                old_stdout, old_stderr = sys.stdout, sys.stderr
                redirected = io.StringIO()
                sys.stdout = redirected
                sys.stderr = redirected

                try:
                    execute_code(code, session_globals)
                except KeyboardInterrupt:
                    print("KeyboardInterrupt")
                except SystemExit as exc:
                    print(f"SystemExit: {exc}")
                except Exception:
                    traceback.print_exc()
                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

                output = redirected.getvalue()

                console_write(f"{GREEN}[OUTPUT]{RESET}\n{output}")
                send_text(conn, output)

    finally:
        server.close()

        if bound and os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)


def run_command(code):
    """Send code to the persistent session and return the result."""
    if not os.path.exists(SOCKET_PATH):
        return "Error: session not started. Run 'replmux start' first.\n"

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(SOCKET_PATH)
            client.sendall(code.encode("utf-8"))

            # This is what lets the server's recv_all() know the request is done.
            client.shutdown(socket.SHUT_WR)

            return recv_all(client)
    except OSError as exc:
        return f"Error: could not connect to session: {exc}\n"
    except ValueError as exc:
        return f"Error: protocol failure: {exc}\n"


def read_interactive_block(compiler):
    """
    Read one complete Python block from the human.

    Supports things like:

        def f(x):
            return x + 1

    and:

        x = [
            1,
            2,
            3,
        ]

    Type exit or quit at a fresh prompt to leave join mode.
    """
    lines = []
    prompt = ">>> "

    while True:
        line = input(prompt)

        if not lines and line.strip().lower() in {"exit", "quit"}:
            return None

        if not lines and not line.strip():
            continue

        lines.append(line)
        source = "\n".join(lines)

        try:
            compiled = compiler(source, "<agent-join>", "exec")
        except (SyntaxError, OverflowError, ValueError):
            # Send syntactically invalid code to the server anyway so the
            # traceback is produced in the shared transcript.
            return source

        if compiled is not None:
            return source

        prompt = "... "


def join_session():
    """Human interactive mode. Connects to the same persistent Python globals."""
    if not os.path.exists(SOCKET_PATH):
        print("Server not running.")
        return

    print("Connected to Agent REPL. You share the same variables.")
    print("Enter complete Python blocks. Type 'exit' or 'quit' to leave join mode.")

    compiler = codeop.CommandCompiler()

    while True:
        try:
            code = read_interactive_block(compiler)
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if code is None:
            break

        result = run_command(code)
        print_result(result)


def usage():
    print(
        """Usage:
  replmux start
  replmux run <code_string>
  replmux run < script.py
  replmux join
  replmux stop

Examples:
  replmux start

  replmux run 'x = 41'
  replmux run 'x + 1'

  replmux run <<'PY'
  import math
  radius = 3
  math.pi * radius ** 2
  PY
"""
    )


def main(argv=None):
    if argv is None:
        argv = sys.argv
    if len(argv) < 2:
        usage()
        return 1

    action = argv[1]

    if action == "start":
        start_session()
        return 0

    if action == "run":
        if len(argv) >= 3:
            code = " ".join(argv[2:])
        else:
            code = sys.stdin.read()

        if not code.strip():
            print("Error: missing code. Pass a code string or pipe code on stdin.")
            return 1

        result = run_command(code)
        print_result(result)
        return 0

    if action == "join":
        join_session()
        return 0

    if action == "stop":
        result = run_command(EXIT_COMMAND)
        print_result(result)
        return 0

    usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
