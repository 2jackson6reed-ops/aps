"""Command line entry point for APS Terminal."""

from __future__ import annotations

import argparse
import os
import sys

from .frontend import CursesTerminalApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aps-terminal",
        description="Run a Linux shell inside the APS terminal emulator.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Optional command to run instead of the user's shell.",
    )
    parser.add_argument(
        "--scrollback",
        type=int,
        default=2000,
        help="Number of off-screen rows to keep for page-up/page-down scrolling.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    shell = command or [os.environ.get("SHELL") or "/bin/sh"]
    try:
        CursesTerminalApp(shell, scrollback=args.scrollback).run()
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(f"aps-terminal: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
