import io
import os
import socket
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from replmux import cli


class ReplmuxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace_tmp = Path(__file__).resolve().parents[1] / ".tmp-tests"
        cls.workspace_tmp.mkdir(exist_ok=True)

    def test_execute_code_preserves_state_and_prints_final_expression(self):
        session_globals = {}
        stream = io.StringIO()

        with redirect_stdout(stream):
            cli.execute_code("x = 41\nx + 1", session_globals)

        self.assertEqual(stream.getvalue(), "42\n")
        self.assertEqual(session_globals["x"], 41)
        self.assertEqual(session_globals["_"], 42)

    def test_usage_mentions_replmux_command(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            cli.usage()

        output = stream.getvalue()
        self.assertIn("replmux start", output)
        self.assertNotIn("repl_tool.py", output)

    def test_run_command_reports_replmux_start_when_server_is_missing(self):
        with tempfile.TemporaryDirectory(dir=self.workspace_tmp) as tmpdir:
            socket_path = os.path.join(tmpdir, "missing.sock")
            old_socket_path = cli.SOCKET_PATH
            cli.SOCKET_PATH = socket_path

            try:
                result = cli.run_command("x = 1")
            finally:
                cli.SOCKET_PATH = old_socket_path

        self.assertEqual(
            result,
            "Error: session not started. Run 'replmux start' first.\n",
        )

    def test_start_run_and_stop_session(self):
        with tempfile.TemporaryDirectory(dir=self.workspace_tmp) as tmpdir:
            socket_path = os.path.join(tmpdir, "replmux.sock")
            old_socket_path = cli.SOCKET_PATH
            cli.SOCKET_PATH = socket_path

            try:
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    probe.bind(socket_path)
                except PermissionError:
                    self.skipTest("sandbox does not permit AF_UNIX socket bind")
                finally:
                    probe.close()

                if os.path.exists(socket_path):
                    os.remove(socket_path)

                thread = threading.Thread(target=cli.start_session, daemon=True)
                thread.start()

                deadline = time.time() + 5
                while not os.path.exists(socket_path):
                    if time.time() > deadline:
                        self.fail("timed out waiting for server socket")
                    time.sleep(0.05)

                self.assertEqual(
                    cli.run_command("x = 41"),
                    "",
                )
                self.assertEqual(cli.run_command("x + 1"), "42\n")

                stop_output = cli.run_command(cli.EXIT_COMMAND)
                self.assertIn("Shutdown signal received", stop_output)

                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
            finally:
                cli.SOCKET_PATH = old_socket_path
