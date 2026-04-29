import unittest

from terminal_emulator.parser import VTParser
from terminal_emulator.screen import Screen


class ParserTests(unittest.TestCase):
    def test_parser_prints_utf8_text(self) -> None:
        screen = Screen(rows=3, cols=10)
        parser = VTParser(screen)

        parser.feed("hé".encode())

        self.assertTrue(screen.display_lines()[0].startswith("hé"))

    def test_parser_handles_cursor_position_sequence(self) -> None:
        screen = Screen(rows=3, cols=10)
        parser = VTParser(screen)

        parser.feed(b"\x1b[2;4HX")

        self.assertEqual((screen.cursor_row, screen.cursor_col), (1, 4))
        self.assertEqual(screen.display_lines()[1][3], "X")

    def test_parser_handles_text_attributes(self) -> None:
        screen = Screen(rows=3, cols=10)
        parser = VTParser(screen)

        parser.feed(b"\x1b[31;42;1mA\x1b[0mB")
        cells = screen.snapshot()[0]

        self.assertEqual(cells[0].char, "A")
        self.assertEqual(cells[0].style.fg, 1)
        self.assertEqual(cells[0].style.bg, 2)
        self.assertTrue(cells[0].style.bold)
        self.assertEqual(cells[1].char, "B")
        self.assertEqual(cells[1].style.fg, 7)
        self.assertEqual(cells[1].style.bg, 0)
        self.assertFalse(cells[1].style.bold)

    def test_parser_handles_alternate_screen_buffer(self) -> None:
        screen = Screen(rows=3, cols=10)
        parser = VTParser(screen)

        parser.feed(b"main\x1b[?1049halt\x1b[2Jalt\x1b[?1049l")

        self.assertTrue(screen.display_lines()[0].startswith("main"))


if __name__ == "__main__":
    unittest.main()
