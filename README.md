# APS Terminal

APS Terminal is a small Linux terminal emulator implemented in Python. It runs
interactive programs through a pseudoterminal, parses common VT/ANSI escape
sequences, keeps an in-memory terminal screen, and renders that screen with a
curses frontend.

The project is intentionally dependency-free so it can run on a standard Linux
Python installation.

## Features

- Linux PTY backend for interactive shells and full-screen terminal programs.
- Curses frontend with keyboard input, terminal resizing, alternate screen
  support, and configurable shell command.
- VT/ANSI parser for printable text, C0 controls, CSI cursor movement, erase
  commands, scroll regions, SGR styling, cursor visibility, and alternate screen
  mode.
- Scrollback-aware screen model with autowrap and line insertion/deletion.
- Unit tests for parser and screen behavior.

This is a practical terminal emulator foundation, not a complete replacement for
mature projects such as xterm, VTE, Alacritty, or Kitty. Terminal compatibility
is broad enough for common shells and many TUI programs, while advanced features
such as sixel graphics, ligatures, complex shaping, and OSC clipboard protocols
are outside the current scope.

## Requirements

- Linux
- Python 3.10+

## Run

```bash
python3 -m terminal_emulator
```

Run a specific command:

```bash
python3 -m terminal_emulator /bin/bash
python3 -m terminal_emulator python3 -q
```

After installing the package, you can also run:

```bash
aps-terminal
```

## Keyboard shortcuts

- `Ctrl+Q`: quit the emulator.

Most other keys are forwarded to the child PTY.

## Test

```bash
python3 -m unittest discover -s tests
```

## Architecture

- `terminal_emulator.pty_backend`: starts and manages the child process in a
  pseudoterminal.
- `terminal_emulator.parser`: parses UTF-8 byte streams and VT/ANSI escape
  sequences.
- `terminal_emulator.screen`: stores the current terminal grid, cursor, styles,
  scrollback, and alternate-screen state.
- `terminal_emulator.frontend`: renders the screen with curses and forwards
  keyboard input to the PTY.
