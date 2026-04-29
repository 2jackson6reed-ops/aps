"""Curses frontend for the terminal emulator."""

from __future__ import annotations

import curses
import os
import selectors
import signal
import sys
from dataclasses import dataclass

from .parser import VTParser
from .pty_backend import PtyProcess
from .screen import Cell, Screen, Style


@dataclass(frozen=True)
class TerminalOptions:
    command: list[str]
    scrollback: int = 2000


class CursesTerminalApp:
    """Interactive terminal app backed by a Linux PTY."""

    def __init__(self, command: list[str], *, scrollback: int = 2000) -> None:
        self.options = TerminalOptions(command=command, scrollback=scrollback)
        self.screen: Screen | None = None
        self.parser: VTParser | None = None
        self.proc: PtyProcess | None = None
        self.selector: selectors.DefaultSelector | None = None
        self.scroll_offset = 0
        self._color_pairs: dict[tuple[int, int], int] = {}

    def run(self) -> int:
        return curses.wrapper(self._run)

    def _run(self, stdscr: curses.window) -> int:
        rows, cols = stdscr.getmaxyx()
        self.screen = Screen(max(1, rows), max(1, cols), scrollback_limit=self.options.scrollback)
        self.parser = VTParser(self.screen)
        self.proc = PtyProcess.spawn(self.options.command, rows=self.screen.rows, cols=self.screen.cols)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.fd, selectors.EVENT_READ, "pty")
        self.selector.register(sys.stdin.fileno(), selectors.EVENT_READ, "stdin")
        self._configure_curses(stdscr)

        previous_handler = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, lambda _sig, _frame: self._resize(stdscr))
        try:
            while self.proc.poll() is None:
                for key, _ in self.selector.select(timeout=0.03):
                    if key.data == "pty":
                        self._read_pty()
                    else:
                        self._read_keyboard()
                self._draw(stdscr)
            self._read_pty()
            self._draw(stdscr)
            status = self.proc.poll()
            return 0 if status is None else status
        finally:
            signal.signal(signal.SIGWINCH, previous_handler)
            if self.selector is not None:
                self.selector.close()
            if self.proc is not None:
                self.proc.terminate()

    def _configure_curses(self, stdscr: curses.window) -> None:
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        stdscr.nodelay(True)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
        if hasattr(curses, "set_escdelay"):
            curses.set_escdelay(25)

    def _resize(self, stdscr: curses.window) -> None:
        if self.screen is None or self.proc is None:
            return
        curses.update_lines_cols()
        rows, cols = stdscr.getmaxyx()
        self.screen.resize(max(1, rows), max(1, cols))
        self.proc.resize(self.screen.rows, self.screen.cols)

    def _read_pty(self) -> None:
        if self.proc is None or self.parser is None:
            return
        data = self.proc.read(timeout=0)
        if data:
            self.parser.feed_bytes(data)
            self.scroll_offset = 0

    def _read_keyboard(self) -> None:
        if self.proc is None or self.screen is None:
            return
        try:
            data = os.read(sys.stdin.fileno(), 4096)
        except BlockingIOError:
            return
        if data == b"\x11":
            self.proc.terminate()
            return
        if data == b"\x1b[5~":
            self.scroll_offset = min(len(self.screen.scrollback), self.scroll_offset + self.screen.rows)
            return
        if data == b"\x1b[6~":
            self.scroll_offset = max(0, self.scroll_offset - self.screen.rows)
            return
        if data:
            self.proc.write(data)

    def _draw(self, stdscr: curses.window) -> None:
        if self.screen is None:
            return
        stdscr.erase()
        rows, cols = stdscr.getmaxyx()
        rows = max(1, rows)
        cols = max(1, cols)
        visible = self._visible_cells(rows)
        for row_index, row in enumerate(visible[:rows]):
            for col_index, cell in enumerate(row[:cols]):
                try:
                    stdscr.addstr(row_index, col_index, cell.char, self._attributes(cell.style))
                except curses.error:
                    pass
        if self.screen.cursor_visible and self.scroll_offset == 0:
            try:
                curses.curs_set(1)
                stdscr.move(min(self.screen.cursor_row, rows - 1), min(self.screen.cursor_col, cols - 1))
            except curses.error:
                pass
        else:
            try:
                curses.curs_set(0)
            except curses.error:
                pass
        stdscr.refresh()

    def _visible_cells(self, rows: int) -> list[list[Cell]]:
        if self.screen is None:
            return []
        if self.scroll_offset == 0:
            return self.screen.snapshot()
        history = self.screen.scrollback + self.screen.snapshot()
        start = max(0, len(history) - rows - self.scroll_offset)
        end = start + rows
        return history[start:end]

    def _attributes(self, style: Style) -> int:
        attrs = 0
        if style.bold:
            attrs |= curses.A_BOLD
        if style.underline:
            attrs |= curses.A_UNDERLINE
        if style.inverse:
            attrs |= curses.A_REVERSE
        if not curses.has_colors():
            return attrs
        fg, bg = style.fg, style.bg
        if style.inverse:
            fg, bg = bg, fg
        return attrs | curses.color_pair(self._pair(fg, bg))

    def _pair(self, fg: int, bg: int) -> int:
        key = (fg % 256, bg % 256)
        existing = self._color_pairs.get(key)
        if existing is not None:
            return existing
        if len(self._color_pairs) + 1 >= curses.COLOR_PAIRS:
            return 0
        pair = len(self._color_pairs) + 1
        curses.init_pair(pair, self._curses_color(key[0]), self._curses_color(key[1]))
        self._color_pairs[key] = pair
        return pair

    @staticmethod
    def _curses_color(color: int) -> int:
        if curses.COLORS >= 256:
            return color
        return color % max(1, curses.COLORS)
