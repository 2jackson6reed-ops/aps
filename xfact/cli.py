"""Unified xFact command line interface."""

from __future__ import annotations

import argparse

from . import manifest, os_build


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xfact",
        description="Build and inspect the xFact Linux distribution.",
    )
    subparsers = parser.add_subparsers(dest="command")

    manifest_parser = subparsers.add_parser(
        "manifest",
        help="Validate xFact metadata and generate identity seed files.",
    )
    manifest.add_arguments(manifest_parser)

    os_parser = subparsers.add_parser(
        "os",
        help="Generate or validate the bootable xFact live OS build tree.",
    )
    os_build.add_arguments(os_parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "manifest":
        return manifest.run(args)
    if args.command == "os":
        return os_build.run(args)
    parser.print_help()
    return 0
