"""PTY process management for Linux shells."""

from __future__ import annotations

import fcntl
import os
import pty
import select
import signal
import struct
import termios
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass
class PtyProcess:
    """A child process attached to a pseudo-terminal."""

    pid: int
    fd: int
    _returncode: int | None = None

    @classmethod
    def spawn(
        cls,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
        rows: int = 24,
        cols: int = 80,
    ) -> "PtyProcess":
        if not argv:
            raise ValueError("argv must contain at least one executable")

        pid, fd = pty.fork()
        if pid == 0:
            child_env = os.environ.copy()
            if env:
                child_env.update(env)
            child_env.setdefault("TERM", "xterm-256color")
            if cwd:
                os.chdir(cwd)
            os.execvpe(argv[0], list(argv), child_env)

        process = cls(pid=pid, fd=fd)
        process.resize(rows, cols)
        set_nonblocking(fd)
        return process

    def resize(self, rows: int, cols: int) -> None:
        winsize = struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    def read(self, timeout: float = 0.0, max_bytes: int = 8192) -> bytes:
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return b""
        try:
            return os.read(self.fd, max_bytes)
        except (BlockingIOError, OSError):
            return b""

    def write(self, data: bytes) -> None:
        if data:
            os.write(self.fd, data)

    def poll(self) -> int | None:
        if self._returncode is not None:
            return self._returncode
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            self._returncode = 0
            return self._returncode
        if pid == 0:
            return None
        self._returncode = decode_wait_status(status)
        return self._returncode

    def is_running(self) -> bool:
        return self.poll() is None

    def wait(self) -> int:
        if self._returncode is not None:
            return self._returncode
        try:
            _, status = os.waitpid(self.pid, 0)
        except ChildProcessError:
            self._returncode = 0
        else:
            self._returncode = decode_wait_status(status)
        return self._returncode

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass

    def terminate(self) -> None:
        if self.poll() is None:
            try:
                os.kill(self.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        self.close()


def decode_wait_status(status: int) -> int:
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return status


def set_nonblocking(fd: int) -> None:
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
