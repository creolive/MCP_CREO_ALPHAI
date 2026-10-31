"""BUG-092: stdio MCP server bounded-exit lifecycle (offline).

A minimal stdio client (raw pipes, no SDK client) starts server.py, performs
only initialize + tools/list, then exercises a lifecycle edge and asserts the
server process exits within the idle budget (10 s), preserving evidence on
failure. No creo_* tool is ever called: no Toolkit connection and no
toolkit.lock interaction from the test side.

Scenarios: normal stdin EOF, abrupt client death, unconsumed stdout/stderr,
server subprocess start failure, and an accepted background runner that must
survive the server exit and still record its terminal state. The runner is an
offline stand-in spawned exactly like ``bridge.py run-job`` runners (detached
console, stdio to a log): real accepted jobs are only created through the
Toolkit channel, which is out of scope for this offline round (P02).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server.py"
PYTHON = sys.executable

#: Idle-service exit budget fixed by the P02 test spec (seconds).
EXIT_BUDGET_SECONDS = 10.0

#: How long to wait for the initialize/tools/list responses (seconds).
HANDSHAKE_BUDGET_SECONDS = 60.0

_TERMINAL_JOB_STATES = {"succeeded", "failed", "unknown_outcome"}

#: Standalone driver for the abrupt-client-death scenario: handshakes, reports
#: the server pid, then blocks forever holding the pipes until it is killed.
_DRIVER_SOURCE = """
import json, subprocess, sys, time
from pathlib import Path

root, pid_file = sys.argv[1], sys.argv[2]
proc = subprocess.Popen(
    [sys.executable, str(Path(root) / "server.py")],
    cwd=root,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
Path(pid_file).write_text(str(proc.pid), encoding="utf-8")


def send(message):
    proc.stdin.write((json.dumps(message) + "\\n").encode("utf-8"))
    proc.stdin.flush()


send({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "bug092-abrupt-driver", "version": "0"},
    },
})
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
time.sleep(3600)  # killed by the test; never closes stdin on purpose
"""

#: Offline stand-in for a ``bridge.py run-job`` runner: records a terminal
#: job state once it is told the run is over (go file), like the real runner
#: writes terminal ``job.json`` status by itself after its work finishes.
_RUNNER_SOURCE = """
import json, sys, time
from pathlib import Path

go, job_json = Path(sys.argv[1]), Path(sys.argv[2])
deadline = time.monotonic() + 120
while not go.exists() and time.monotonic() < deadline:
    time.sleep(0.05)
job_json.write_text(
    json.dumps({"status": "succeeded", "synthetic": "p02-offline-runner"}),
    encoding="utf-8",
)
"""


class MinimalStdioClient:
    """Raw-pipe MCP stdio client: initialize + tools/list only.

    This is the offline repro client for BUG-092: it deliberately bypasses the
    SDK client's job-object kill so a lingering server.py subprocess is
    observable, exactly like the residual seen after live drivers ended.
    """

    def __init__(self, *, consume_output: bool = True, server_path: Path = SERVER):
        self.consume_output = consume_output
        self.proc = subprocess.Popen(
            [PYTHON, str(server_path)],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._out_lines: list[bytes] = []
        self._err_chunks: list[bytes] = []
        self._lock = threading.Lock()
        if consume_output:
            threading.Thread(target=self._pump_stdout, daemon=True).start()
            threading.Thread(target=self._pump_stderr, daemon=True).start()

    def _pump_stdout(self) -> None:
        try:
            for line in self.proc.stdout:
                with self._lock:
                    self._out_lines.append(line)
        finally:
            pass

    def _pump_stderr(self) -> None:
        try:
            for chunk in self.proc.stderr:
                with self._lock:
                    self._err_chunks.append(chunk)
        finally:
            pass

    def send(self, message: dict) -> None:
        self.proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def handshake(self) -> dict:
        try:
            self.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test_stdio_lifecycle", "version": "0"},
                    },
                }
            )
        except OSError:
            return {"initialize": None, "tools": None}
        init = self._wait_message(lambda m: m.get("id") == 1)
        try:
            self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            self.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        except OSError:
            return {"initialize": init, "tools": None}
        tools = self._wait_message(lambda m: m.get("id") == 2)
        return {"initialize": init, "tools": tools}

    def _parsed_lines(self) -> list[dict]:
        with self._lock:
            raw = list(self._out_lines)
        messages = []
        for line in raw:
            try:
                messages.append(json.loads(line))
            except ValueError:
                continue
        return messages

    def _wait_message(self, predicate, budget: float = HANDSHAKE_BUDGET_SECONDS):
        deadline = time.monotonic() + budget
        while time.monotonic() < deadline:
            for message in self._parsed_lines():
                if predicate(message):
                    return message
            if self.proc.poll() is not None:
                break
            time.sleep(0.05)
        return None

    def close_stdin(self) -> None:
        try:
            self.proc.stdin.close()
        except OSError:
            pass

    def wait_exit(self, budget: float = EXIT_BUDGET_SECONDS) -> float | None:
        """Returns seconds until exit, or None when still alive after budget."""
        start = time.monotonic()
        deadline = start + budget
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                return time.monotonic() - start
            time.sleep(0.05)
        return None

    def scene(self) -> str:
        """Diagnostic snapshot preserved when a bounded-exit assertion fails."""
        parts = [f"server pid={self.proc.pid} returncode={self.proc.poll()}"]
        pids = {self.proc.pid} | self._descendant_pids()
        try:
            listing = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*python*' } "
                    "| Select-Object ProcessId,Name,ParentProcessId,CommandLine | Format-List",
                ],
                capture_output=True,
                timeout=30,
            )
            parts.append(listing.stdout.decode("utf-8", "replace"))
        except Exception as exc:  # pragma: no cover - diagnostic only
            parts.append(f"<process listing failed: {exc!r}>")
        spy = Path(sys.executable).with_name("py-spy.exe")
        for pid in sorted(pids):
            if not spy.exists():
                continue
            try:
                dump = subprocess.run(
                    [str(spy), "dump", "--pid", str(pid)],
                    capture_output=True,
                    timeout=30,
                )
                parts.append(f"--- py-spy dump pid={pid} ---")
                parts.append(dump.stdout.decode("utf-8", "replace"))
            except Exception as exc:  # pragma: no cover - diagnostic only
                parts.append(f"<py-spy dump failed for {pid}: {exc!r}>")
        with self._lock:
            parts.append("stdout lines: " + repr(b"".join(self._out_lines[:40])[:2000]))
            parts.append("stderr tail: " + repr(b"".join(self._err_chunks)[-2000:]))
        text = "\n".join(parts)
        scene_path = Path(tempfile.gettempdir()) / f"bug092_scene_{self.proc.pid}.txt"
        try:
            scene_path.write_text(text, encoding="utf-8")
        except OSError:  # pragma: no cover - diagnostic only
            return text
        return f"scene saved to {scene_path}\n" + text[:4000]

    def _descendant_pids(self) -> set[int]:
        try:
            listing = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-CimInstance Win32_Process | Where-Object {{ $_.ParentProcessId -eq {self.proc.pid} }}).ProcessId",
                ],
                capture_output=True,
                timeout=30,
            )
            return {
                int(line)
                for line in listing.stdout.decode("utf-8", "replace").split()
                if line.strip().isdigit()
            }
        except Exception:  # pragma: no cover - diagnostic only
            return set()

    def terminate(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass


def _process_alive(pid: int) -> bool:
    """Windows-safe liveness check; never signals the target process."""
    import ctypes

    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


class StdioLifecycleTests(unittest.TestCase):
    """Bounded-exit regression for BUG-092 (offline, no Toolkit)."""

    def tearDown(self) -> None:
        client = getattr(self, "client", None)
        if client is not None:
            client.terminate()
        runner = getattr(self, "runner", None)
        if runner is not None and runner.poll() is None:
            runner.kill()
            try:
                runner.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass

    def _spawn(self, **kwargs) -> MinimalStdioClient:
        self.client = MinimalStdioClient(**kwargs)
        return self.client

    def test_stdin_eof_exits_within_budget(self) -> None:
        """Normal EOF after initialize/tools/list: idle server exits within 10 s."""
        client = self._spawn()
        try:
            handshake = client.handshake()
        except Exception as exc:
            self.fail(f"handshake failed: {exc}\n{client.scene()}")
        self.assertIsNotNone(handshake["initialize"], f"no initialize response\n{client.scene()}")
        self.assertIsNotNone(handshake["tools"], f"no tools/list response\n{client.scene()}")
        tools = handshake["tools"].get("result", {}).get("tools", [])
        self.assertGreater(len(tools), 0, f"empty tool list\n{client.scene()}")
        client.close_stdin()
        elapsed = client.wait_exit()
        self.assertIsNotNone(
            elapsed,
            f"server.py still alive {EXIT_BUDGET_SECONDS}s after stdin EOF\n{client.scene()}",
        )

    def test_unconsumed_stdout_stderr_still_exits(self) -> None:
        """Client never reads stdout/stderr: server must still exit after EOF.

        This is the reproduced BUG-092 residual path: the large tools/list
        response fills the stdout pipe, the wire writer blocks in WriteFile and
        (before the fix) the server kept the pipes forever.
        """
        client = self._spawn(consume_output=False)
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test_stdio_lifecycle", "version": "0"},
                },
            }
        )
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        client.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        time.sleep(1.0)  # let the server come up and start filling the pipe
        self.assertIsNone(
            client.proc.poll(),
            f"server.py died before EOF; the exit assertion would be vacuous\n{client.scene()}",
        )
        client.close_stdin()
        elapsed = client.wait_exit()
        self.assertIsNotNone(
            elapsed,
            f"server.py still alive {EXIT_BUDGET_SECONDS}s after EOF with unconsumed output\n{client.scene()}",
        )

    def test_abrupt_client_death_still_exits(self) -> None:
        """Driver killed without closing stdin: server must exit within budget."""
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            driver_script = tmp / "driver.py"
            driver_script.write_text(_DRIVER_SOURCE, encoding="utf-8")
            pid_file = tmp / "server_pid.txt"
            driver = subprocess.Popen(
                [PYTHON, str(driver_script), str(ROOT), str(pid_file)],
                cwd=str(ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 30
                while not pid_file.exists() and time.monotonic() < deadline:
                    self.assertIsNone(driver.poll(), "driver exited before reporting pid")
                    time.sleep(0.05)
                self.assertTrue(pid_file.exists(), "driver never reported the server pid")
                server_pid = int(pid_file.read_text(encoding="utf-8"))
            finally:
                driver.kill()
                try:
                    driver.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            start = time.monotonic()
            deadline = start + EXIT_BUDGET_SECONDS
            while time.monotonic() < deadline and _process_alive(server_pid):
                time.sleep(0.05)
            self.assertFalse(
                _process_alive(server_pid),
                f"server pid {server_pid} still alive {EXIT_BUDGET_SECONDS}s after "
                f"the driver was killed\n{self._pid_scene(server_pid)}",
            )

    def test_server_subprocess_start_failure_is_bounded(self) -> None:
        """A server subprocess that fails to start must fail fast, never hang."""
        missing = Path(tempfile.gettempdir()) / "bug092_no_such_server.py"
        client = self._spawn(server_path=missing)
        handshake = client.handshake()
        self.assertIsNone(
            handshake["initialize"], f"unexpected response from a failed start\n{client.scene()}"
        )
        elapsed = client.wait_exit()
        self.assertIsNotNone(
            elapsed,
            f"failed server start left a residual process\n{client.scene()}",
        )
        self.assertNotEqual(client.proc.returncode, 0, client.scene())

    def test_accepted_background_job_survives_and_registers_terminal_state(self) -> None:
        """Server exit must not kill accepted background work.

        The runner stands in for an accepted ``bridge.py run-job`` job and is
        spawned with the same detached flags. It must survive the server's
        bounded exit (no global Python tree kill) and still record its terminal
        job state afterwards.
        """
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            runner_script = tmp / "runner.py"
            runner_script.write_text(_RUNNER_SOURCE, encoding="utf-8")
            go_file = tmp / "go"
            job_json = tmp / "job.json"
            client = self._spawn()
            try:
                handshake = client.handshake()
            except Exception as exc:
                self.fail(f"handshake failed: {exc}\n{client.scene()}")
            self.assertIsNotNone(
                handshake["initialize"], f"no initialize response\n{client.scene()}"
            )
            # Accept the background task mid-session, like bridge.create_job.
            runner_log = (tmp / "runner.log").open("ab")
            self.runner = subprocess.Popen(
                [PYTHON, str(runner_script), str(go_file), str(job_json)],
                cwd=str(ROOT),
                stdin=subprocess.DEVNULL,
                stdout=runner_log,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
            runner_log.close()
            client.close_stdin()
            elapsed = client.wait_exit()
            self.assertIsNotNone(
                elapsed,
                f"server.py still alive {EXIT_BUDGET_SECONDS}s after stdin EOF\n{client.scene()}",
            )
            self.assertIsNone(
                self.runner.poll(),
                "the accepted background runner did not survive the server exit; "
                "the exit path must never kill the Python process tree",
            )
            go_file.write_text("go", encoding="utf-8")
            deadline = time.monotonic() + EXIT_BUDGET_SECONDS
            while not job_json.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(
                job_json.exists(),
                "accepted background task never recorded its terminal state",
            )
            manifest = json.loads(job_json.read_text(encoding="utf-8"))
            self.assertIn(
                manifest.get("status"),
                _TERMINAL_JOB_STATES,
                f"non-terminal job state recorded: {manifest}",
            )

    @staticmethod
    def _pid_scene(pid: int) -> str:
        try:
            listing = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-CimInstance Win32_Process | Where-Object {{ $_.ProcessId -eq {pid} }} "
                    "| Select-Object ProcessId,Name,CommandLine | Format-List",
                ],
                capture_output=True,
                timeout=30,
            )
            return listing.stdout.decode("utf-8", "replace")
        except Exception as exc:  # pragma: no cover - diagnostic only
            return f"<process listing failed: {exc!r}>"


if __name__ == "__main__":
    unittest.main()
