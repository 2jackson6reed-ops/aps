"""A compact VT/ANSI parser for the terminal screen model."""

from __future__ import annotations

from .screen import Screen


class VTParser:
    """Parse UTF-8 text and common terminal escape sequences."""

    def __init__(self, screen: Screen) -> None:
        self.screen = screen
        self._state = "ground"
        self._params = ""
        self._osc = ""

    def feed_bytes(self, data: bytes) -> None:
        self.feed(data.decode("utf-8", errors="replace"))

    def feed(self, data: bytes | str) -> None:
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        for char in data:
            self._process(char)

    def _process(self, char: str) -> None:
        code = ord(char)
        if self._state == "ground":
            if char == "\x1b":
                self._state = "escape"
            elif code >= 0x20 and char != "\x7f":
                self.screen.put_char(char)
            else:
                self.screen.put_char(char)
            return

        if self._state == "escape":
            if char == "[":
                self._params = ""
                self._state = "csi"
            elif char == "]":
                self._osc = ""
                self._state = "osc"
            elif char == "7":
                self.screen.save_cursor()
                self._state = "ground"
            elif char == "8":
                self.screen.restore_cursor()
                self._state = "ground"
            elif char == "c":
                self.screen.reset()
                self._state = "ground"
            elif char == "D":
                self.screen.line_feed()
                self._state = "ground"
            elif char == "E":
                self.screen.carriage_return()
                self.screen.line_feed()
                self._state = "ground"
            elif char == "M":
                self.screen.reverse_index()
                self._state = "ground"
            elif char == "H":
                self.screen.set_tab_stop()
                self._state = "ground"
            elif char in "=>()#%":
                self._state = "charset"
            else:
                self._state = "ground"
            return

        if self._state == "charset":
            self._state = "ground"
            return

        if self._state == "osc":
            if char == "\x07":
                self._finish_osc()
                self._state = "ground"
            elif char == "\x1b":
                self._state = "osc_escape"
            else:
                self._osc += char
            return

        if self._state == "osc_escape":
            if char == "\\":
                self._finish_osc()
                self._state = "ground"
            else:
                self._osc += "\x1b" + char
                self._state = "osc"
            return

        if self._state == "csi":
            if 0x40 <= code <= 0x7E:
                self._handle_csi(char, self._params)
                self._state = "ground"
            else:
                self._params += char

    def _finish_osc(self) -> None:
        command, _, payload = self._osc.partition(";")
        if command in {"0", "1", "2"}:
            self.screen.title = payload

    def _handle_csi(self, final: str, raw: str) -> None:
        private = False
        while raw and raw[0] in "?=>!":
            private = private or raw[0] == "?"
            raw = raw[1:]

        params = _parse_params(raw)
        first = _value(params, 0, 1)

        if final in "hl":
            for mode in _mode_params(params):
                self.screen.set_mode(mode, final == "h", private=private)
            return

        if final == "A":
            self.screen.cursor_up(first)
        elif final == "B":
            self.screen.cursor_down(first)
        elif final == "C":
            self.screen.cursor_forward(first)
        elif final == "D":
            self.screen.cursor_backward(first)
        elif final == "E":
            self.screen.cursor_next_line(first)
        elif final == "F":
            self.screen.cursor_previous_line(first)
        elif final == "G":
            self.screen.set_cursor(self.screen.cursor_row + 1, first)
        elif final in "Hf":
            self.screen.set_cursor(_value(params, 0, 1), _value(params, 1, 1))
        elif final == "J":
            self.screen.erase_in_display(_value(params, 0, 0))
        elif final == "K":
            self.screen.erase_in_line(_value(params, 0, 0))
        elif final == "L":
            self.screen.insert_lines(first)
        elif final == "M":
            self.screen.delete_lines(first)
        elif final == "P":
            self.screen.delete_chars(first)
        elif final == "@":
            self.screen.insert_chars(first)
        elif final == "S":
            self.screen.scroll_up(first)
        elif final == "T":
            self.screen.scroll_down(first)
        elif final == "X":
            self.screen.erase_chars(first)
        elif final == "Z":
            self.screen.back_tab(first)
        elif final == "d":
            self.screen.set_cursor(first, self.screen.cursor_col + 1)
        elif final == "g":
            self.screen.clear_tab_stop(_value(params, 0, 0))
        elif final == "m":
            self.screen.style = self.screen.style.with_sgr([0 if p is None else p for p in params])
        elif final == "r":
            top = _value(params, 0, 1)
            bottom = _value(params, 1, self.screen.rows)
            self.screen.set_scroll_region(top, bottom)
        elif final == "s":
            self.screen.save_cursor()
        elif final == "u":
            self.screen.restore_cursor()


def _parse_params(raw: str) -> list[int | None]:
    if not raw:
        return []
    params: list[int | None] = []
    for part in raw.replace(":", ";").split(";"):
        if part == "":
            params.append(None)
        else:
            try:
                params.append(int(part))
            except ValueError:
                params.append(None)
    return params


def _value(params: list[int | None], index: int, default: int) -> int:
    if index >= len(params):
        return default
    value = params[index]
    return default if value is None or value == 0 else value


def _mode_params(params: list[int | None]) -> list[int]:
    return [param for param in params if param is not None] or [0]


TerminalParser = VTParser
