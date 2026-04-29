"""Terminal screen buffer and SGR rendition state."""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_FG = 7
DEFAULT_BG = 0


@dataclass(frozen=True)
class Style:
    """Visual attributes for a cell using ANSI 0-255 palette indexes."""

    fg: int = DEFAULT_FG
    bg: int = DEFAULT_BG
    bold: bool = False
    italic: bool = False
    underline: bool = False
    inverse: bool = False

    def with_sgr(self, params: list[int]) -> "Style":
        if not params:
            params = [0]

        style = self
        i = 0
        while i < len(params):
            code = params[i]
            if code == 0:
                style = Style()
            elif code == 1:
                style = replace_style(style, bold=True)
            elif code == 3:
                style = replace_style(style, italic=True)
            elif code == 4:
                style = replace_style(style, underline=True)
            elif code == 7:
                style = replace_style(style, inverse=True)
            elif code == 22:
                style = replace_style(style, bold=False)
            elif code == 23:
                style = replace_style(style, italic=False)
            elif code == 24:
                style = replace_style(style, underline=False)
            elif code == 27:
                style = replace_style(style, inverse=False)
            elif code == 39:
                style = replace_style(style, fg=DEFAULT_FG)
            elif code == 49:
                style = replace_style(style, bg=DEFAULT_BG)
            elif 30 <= code <= 37:
                style = replace_style(style, fg=code - 30)
            elif 40 <= code <= 47:
                style = replace_style(style, bg=code - 40)
            elif 90 <= code <= 97:
                style = replace_style(style, fg=code - 90 + 8)
            elif 100 <= code <= 107:
                style = replace_style(style, bg=code - 100 + 8)
            elif code in (38, 48) and i + 1 < len(params):
                target = "fg" if code == 38 else "bg"
                mode = params[i + 1]
                if mode == 5 and i + 2 < len(params):
                    style = replace_style(style, **{target: max(0, min(255, params[i + 2]))})
                    i += 2
                elif mode == 2 and i + 4 < len(params):
                    color = rgb_to_ansi256(*params[i + 2 : i + 5])
                    style = replace_style(style, **{target: color})
                    i += 4
                else:
                    i += 1
            i += 1
        return style


def replace_style(style: Style, **changes: object) -> Style:
    values = {
        "fg": style.fg,
        "bg": style.bg,
        "bold": style.bold,
        "italic": style.italic,
        "underline": style.underline,
        "inverse": style.inverse,
    }
    values.update(changes)
    return Style(**values)


def rgb_to_ansi256(red: int, green: int, blue: int) -> int:
    red = max(0, min(255, red))
    green = max(0, min(255, green))
    blue = max(0, min(255, blue))
    if red == green == blue:
        if red < 8:
            return 16
        if red > 248:
            return 231
        return round(((red - 8) / 247) * 24) + 232
    return 16 + 36 * round(red / 255 * 5) + 6 * round(green / 255 * 5) + round(blue / 255 * 5)


@dataclass
class Cell:
    char: str = " "
    style: Style = field(default_factory=Style)


class Screen:
    """A VT-like terminal screen buffer with scrollback and alternate screen."""

    def __init__(self, rows: int = 24, cols: int = 80, scrollback_limit: int = 5000) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("screen dimensions must be positive")
        self.rows = rows
        self.cols = cols
        self.scrollback_limit = scrollback_limit
        self.scrollback: list[list[Cell]] = []
        self.style = Style()
        self.buffer = self._blank_buffer(rows)
        self.primary_buffer = self.buffer
        self.alternate_buffer: list[list[Cell]] | None = None
        self.in_alternate_screen = False
        self.cursor_row = 0
        self.cursor_col = 0
        self.saved_cursor = (0, 0)
        self.pending_wrap = False
        self.auto_wrap = True
        self.cursor_visible = True
        self.origin_mode = False
        self.scroll_top = 0
        self.scroll_bottom = rows - 1
        self.tab_stops = set(range(8, cols, 8))
        self.title = ""
        self.bracketed_paste = False

    def resize(self, rows: int, cols: int) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("screen dimensions must be positive")

        def resized(buffer: list[list[Cell]]) -> list[list[Cell]]:
            new = [row[:cols] + [Cell() for _ in range(max(0, cols - len(row)))] for row in buffer[:rows]]
            while len(new) < rows:
                new.append([Cell() for _ in range(cols)])
            return new

        self.rows = rows
        self.cols = cols
        self.buffer = resized(self.buffer)
        if self.in_alternate_screen:
            self.alternate_buffer = self.buffer
            self.primary_buffer = resized(self.primary_buffer)
        else:
            self.primary_buffer = self.buffer
            if self.alternate_buffer is not None:
                self.alternate_buffer = resized(self.alternate_buffer)
        self.cursor_row = min(self.cursor_row, rows - 1)
        self.cursor_col = min(self.cursor_col, cols - 1)
        self.pending_wrap = False
        self.scroll_top = 0
        self.scroll_bottom = rows - 1
        self.tab_stops = set(range(8, cols, 8))

    def write_text(self, text: str) -> None:
        for char in text:
            self.put_char(char)

    def put_char(self, char: str) -> None:
        if char == "\n":
            self.line_feed()
        elif char == "\r":
            self.carriage_return()
        elif char == "\b":
            self.backspace()
        elif char == "\t":
            self.tab()
        elif char == "\x07":
            self.bell()
        elif char >= " ":
            self._put_printable(char)

    def _put_printable(self, char: str) -> None:
        if self.pending_wrap:
            self.cursor_col = 0
            self.line_feed()
            self.pending_wrap = False
        self.buffer[self.cursor_row][self.cursor_col] = Cell(char[:1], self.style)
        if self.cursor_col == self.cols - 1:
            self.pending_wrap = self.auto_wrap
        else:
            self.cursor_col += 1

    def line_feed(self) -> None:
        self.pending_wrap = False
        if self.cursor_row == self.scroll_bottom:
            self.scroll_up(1)
        else:
            self.cursor_row = min(self.rows - 1, self.cursor_row + 1)

    def reverse_index(self) -> None:
        if self.cursor_row == self.scroll_top:
            self.scroll_down(1)
        else:
            self.cursor_row = max(0, self.cursor_row - 1)

    def carriage_return(self) -> None:
        self.pending_wrap = False
        self.cursor_col = 0

    def backspace(self) -> None:
        self.pending_wrap = False
        self.cursor_backward(1)

    def bell(self) -> None:
        return

    def tab(self) -> None:
        self.pending_wrap = False
        stops = sorted(stop for stop in self.tab_stops if stop > self.cursor_col)
        self.cursor_col = min(stops[0] if stops else self.cols - 1, self.cols - 1)

    def back_tab(self, count: int = 1) -> None:
        for _ in range(max(1, count)):
            stops = sorted(stop for stop in self.tab_stops if stop < self.cursor_col)
            self.cursor_col = stops[-1] if stops else 0

    def set_tab_stop(self) -> None:
        self.tab_stops.add(self.cursor_col)

    def clear_tab_stop(self, mode: int = 0) -> None:
        if mode == 0:
            self.tab_stops.discard(self.cursor_col)
        elif mode == 3:
            self.tab_stops.clear()

    def cursor_up(self, count: int = 1) -> None:
        self.cursor_row = max(self.scroll_top if self.origin_mode else 0, self.cursor_row - max(1, count))

    def cursor_down(self, count: int = 1) -> None:
        bottom = self.scroll_bottom if self.origin_mode else self.rows - 1
        self.cursor_row = min(bottom, self.cursor_row + max(1, count))

    def cursor_forward(self, count: int = 1) -> None:
        self.cursor_col = min(self.cols - 1, self.cursor_col + max(1, count))

    def cursor_backward(self, count: int = 1) -> None:
        self.cursor_col = max(0, self.cursor_col - max(1, count))

    def cursor_next_line(self, count: int = 1) -> None:
        self.cursor_down(count)
        self.carriage_return()

    def cursor_previous_line(self, count: int = 1) -> None:
        self.cursor_up(count)
        self.carriage_return()

    def set_cursor(self, row: int = 1, col: int = 1) -> None:
        base = self.scroll_top if self.origin_mode else 0
        row_index = base + max(1, row) - 1
        col_index = max(1, col) - 1
        self.move_to(row_index, col_index)

    def move_to(self, row: int, col: int) -> None:
        self.pending_wrap = False
        self.cursor_row = max(0, min(self.rows - 1, row))
        self.cursor_col = max(0, min(self.cols - 1, col))

    def move_relative(self, rows: int, cols: int) -> None:
        self.move_to(self.cursor_row + rows, self.cursor_col + cols)

    def save_cursor(self) -> None:
        self.saved_cursor = (self.cursor_row, self.cursor_col)

    def restore_cursor(self) -> None:
        self.cursor_row, self.cursor_col = self.saved_cursor
        self.cursor_row = max(0, min(self.rows - 1, self.cursor_row))
        self.cursor_col = max(0, min(self.cols - 1, self.cursor_col))

    def erase_display(self, mode: int = 0) -> None:
        self.erase_in_display(mode)

    def erase_in_display(self, mode: int = 0) -> None:
        if mode == 0:
            self.erase_in_line(0)
            for row in range(self.cursor_row + 1, self.rows):
                self.buffer[row] = self._blank_line()
        elif mode == 1:
            for row in range(0, self.cursor_row):
                self.buffer[row] = self._blank_line()
            self.erase_in_line(1)
        elif mode in (2, 3):
            self.buffer = self._blank_buffer(self.rows)
            if self.in_alternate_screen:
                self.alternate_buffer = self.buffer
            else:
                self.primary_buffer = self.buffer
            if mode == 3:
                self.scrollback.clear()

    def erase_line(self, mode: int = 0) -> None:
        self.erase_in_line(mode)

    def erase_in_line(self, mode: int = 0) -> None:
        row = self.buffer[self.cursor_row]
        if mode == 0:
            start, end = self.cursor_col, self.cols
        elif mode == 1:
            start, end = 0, self.cursor_col + 1
        elif mode == 2:
            start, end = 0, self.cols
        else:
            return
        for col in range(start, end):
            row[col] = Cell(style=self.style)

    def insert_blank_chars(self, count: int = 1) -> None:
        self.insert_chars(count)

    def insert_chars(self, count: int = 1) -> None:
        count = min(max(1, count), self.cols - self.cursor_col)
        row = self.buffer[self.cursor_row]
        for _ in range(count):
            row.insert(self.cursor_col, Cell(style=self.style))
            row.pop()

    def delete_chars(self, count: int = 1) -> None:
        count = min(max(1, count), self.cols - self.cursor_col)
        row = self.buffer[self.cursor_row]
        for _ in range(count):
            row.pop(self.cursor_col)
            row.append(Cell(style=self.style))

    def erase_chars(self, count: int = 1) -> None:
        for col in range(self.cursor_col, min(self.cols, self.cursor_col + max(1, count))):
            self.buffer[self.cursor_row][col] = Cell(style=self.style)

    def insert_lines(self, count: int = 1) -> None:
        if not (self.scroll_top <= self.cursor_row <= self.scroll_bottom):
            return
        count = min(max(1, count), self.scroll_bottom - self.cursor_row + 1)
        for _ in range(count):
            self.buffer.insert(self.cursor_row, self._blank_line())
            self.buffer.pop(self.scroll_bottom + 1)

    def delete_lines(self, count: int = 1) -> None:
        if not (self.scroll_top <= self.cursor_row <= self.scroll_bottom):
            return
        count = min(max(1, count), self.scroll_bottom - self.cursor_row + 1)
        for _ in range(count):
            self.buffer.pop(self.cursor_row)
            self.buffer.insert(self.scroll_bottom, self._blank_line())

    def scroll_up(self, count: int = 1) -> None:
        for _ in range(max(1, count)):
            removed = self.buffer.pop(self.scroll_top)
            if self.scroll_top == 0 and not self.in_alternate_screen:
                self.scrollback.append(removed)
                if len(self.scrollback) > self.scrollback_limit:
                    self.scrollback = self.scrollback[-self.scrollback_limit :]
            self.buffer.insert(self.scroll_bottom, self._blank_line())

    def scroll_down(self, count: int = 1) -> None:
        for _ in range(max(1, count)):
            self.buffer.pop(self.scroll_bottom)
            self.buffer.insert(self.scroll_top, self._blank_line())

    def set_scroll_region(self, top: int | None, bottom: int | None) -> None:
        top_index = 0 if top is None else max(0, top)
        bottom_index = self.rows - 1 if bottom is None else min(self.rows - 1, bottom)
        if top_index < bottom_index:
            self.scroll_top = top_index
            self.scroll_bottom = bottom_index
            self.set_cursor(1, 1)

    def reset_scroll_region(self) -> None:
        self.scroll_top = 0
        self.scroll_bottom = self.rows - 1

    def set_mode(self, mode: int, enabled: bool, private: bool = False) -> None:
        if private:
            if mode in (47, 1047, 1049):
                self.use_alternate_screen(enabled, clear=mode == 1049)
            elif mode == 6:
                self.origin_mode = enabled
                self.set_cursor(1, 1)
            elif mode == 7:
                self.auto_wrap = enabled
            elif mode == 25:
                self.cursor_visible = enabled
            elif mode == 2004:
                self.bracketed_paste = enabled

    def use_alternate_screen(self, enabled: bool = True, clear: bool = True) -> None:
        if enabled and not self.in_alternate_screen:
            self.primary_buffer = self.buffer
            self.alternate_buffer = self._blank_buffer(self.rows) if clear else [row[:] for row in self.buffer]
            self.buffer = self.alternate_buffer
            self.in_alternate_screen = True
            self.set_cursor(1, 1)
        elif not enabled and self.in_alternate_screen:
            self.alternate_buffer = self.buffer
            self.buffer = self.primary_buffer
            self.in_alternate_screen = False
            self.set_cursor(1, 1)

    def use_primary_buffer(self) -> None:
        self.use_alternate_screen(False)

    def reset(self) -> None:
        self.buffer = self._blank_buffer(self.rows)
        self.primary_buffer = self.buffer
        self.alternate_buffer = None
        self.in_alternate_screen = False
        self.cursor_row = 0
        self.cursor_col = 0
        self.saved_cursor = (0, 0)
        self.pending_wrap = False
        self.style = Style()
        self.auto_wrap = True
        self.cursor_visible = True
        self.origin_mode = False
        self.bracketed_paste = False
        self.reset_scroll_region()
        self.tab_stops = set(range(8, self.cols, 8))

    def snapshot(self) -> list[list[Cell]]:
        return [[Cell(cell.char, cell.style) for cell in row] for row in self.buffer]

    def text_lines(self) -> list[str]:
        return ["".join(cell.char for cell in row) for row in self.buffer]

    def display_lines(self) -> list[str]:
        return self.text_lines()

    def visible_text(self) -> list[str]:
        return self.text_lines()

    def _blank_buffer(self, rows: int) -> list[list[Cell]]:
        return [self._blank_line() for _ in range(rows)]

    def _blank_line(self) -> list[Cell]:
        return [Cell(style=self.style) for _ in range(self.cols)]
