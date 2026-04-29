import unittest

from terminal_emulator.screen import Screen


class ScreenTests(unittest.TestCase):
    def test_printing_wraps_and_scrolls(self) -> None:
        screen = Screen(rows=2, cols=4)

        screen.write_text("abcdefghi")

        self.assertEqual(screen.text_lines(), ["efgh", "i   "])
        self.assertEqual((screen.cursor_row, screen.cursor_col), (1, 1))

    def test_backspace_overwrites_previous_cell(self) -> None:
        screen = Screen(rows=1, cols=5)

        screen.write_text("abc")
        screen.backspace()
        screen.write_text("Z")

        self.assertEqual(screen.text_lines(), ["abZ  "])

    def test_insert_blank_lines_scroll_region(self) -> None:
        screen = Screen(rows=3, cols=4)
        for row_index, value in enumerate(("1111", "2222", "3333")):
            screen.move_to(row_index, 0)
            screen.write_text(value)
        screen.move_to(1, 0)

        screen.insert_lines(1)

        self.assertEqual(screen.text_lines(), ["1111", "    ", "2222"])

    def test_delete_characters_shifts_line_left(self) -> None:
        screen = Screen(rows=1, cols=6)
        screen.write_text("abcdef")
        screen.move_to(0, 2)

        screen.delete_chars(2)

        self.assertEqual(screen.text_lines(), ["abef  "])


if __name__ == "__main__":
    unittest.main()
