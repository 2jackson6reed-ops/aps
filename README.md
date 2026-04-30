# APS Terminal and xFact

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

## xFact Linux OS

This repository also includes **xFact**, a bootable Debian-based Linux live OS
focused on fact-first diagnostics, a small auditable base image, and
Python-friendly recovery tooling.

The xFact build uses Debian `live-build` to produce a hybrid ISO that can boot on
bare metal or a virtual machine. The generated OS includes systemd, networking,
the package seed in `xfact/manifest.json`, xFact identity files under `/etc`,
and this Python terminal emulator under `/opt/aps-terminal`.

- `xfact/manifest.json`: canonical xFact name, release, goals, and package seed.
- `python3 -m xfact manifest`: validates the manifest and writes `os-release`,
  `issue`, and `package-seed.txt` under `build/xfact/`.
- `python3 -m xfact os configure`: writes a complete Debian live-build project
  under `build/xfact-live/`.
- `./build-xfact.sh`: generates the live-build project and runs `sudo lb build`
  to produce the bootable xFact ISO.

Install ISO build prerequisites on Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install live-build xorriso squashfs-tools syslinux-utils
```

Generate the live OS build tree:

```bash
python3 -m xfact os configure
```

Build the bootable ISO:

```bash
./build-xfact.sh
```

Build if needed and boot xFact in the terminal:

```bash
./run-xfact.sh
```

Useful run options:

```bash
./run-xfact.sh --rebuild
./run-xfact.sh --display
./run-xfact.sh --memory 2048
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
- `xfact.manifest`: validates xFact distro metadata and generates seed identity
  files.
- `xfact.os_build`: generates the Debian live-build project used to build the
  bootable xFact OS ISO.
