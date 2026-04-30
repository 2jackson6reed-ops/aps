"""xFact Linux distribution metadata utilities."""

from __future__ import annotations

import json
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "xfact" / "manifest.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "build" / "xfact"


@dataclass(frozen=True)
class XFactManifest:
    """Validated description of the xFact distro seed image."""

    name: str
    version: str
    codename: str
    architecture: str
    base: str
    edition: str
    terminal: str
    goals: tuple[str, ...]
    packages: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "XFactManifest":
        required_fields = (
            "name",
            "version",
            "codename",
            "architecture",
            "base",
            "edition",
            "terminal",
            "goals",
            "packages",
        )
        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValueError(f"Missing required xFact manifest fields: {', '.join(missing)}")

        manifest = cls(
            name=_require_text(data, "name"),
            version=_require_text(data, "version"),
            codename=_require_text(data, "codename"),
            architecture=_require_text(data, "architecture"),
            base=_require_text(data, "base"),
            edition=_require_text(data, "edition"),
            terminal=_require_text(data, "terminal"),
            goals=_require_text_list(data, "goals"),
            packages=_require_text_list(data, "packages"),
        )
        if manifest.name != "xFact":
            raise ValueError("xFact manifest name must be 'xFact'")
        return manifest

    @property
    def os_release(self) -> str:
        fields = {
            "NAME": self.name,
            "VERSION": self.version,
            "ID": self.name.lower(),
            "ID_LIKE": self.base.split()[0].lower(),
            "PRETTY_NAME": f"{self.name} {self.version} ({self.codename})",
            "ANSI_COLOR": "1;36",
            "HOME_URL": "https://example.invalid/xfact",
            "SUPPORT_URL": "https://example.invalid/xfact/support",
        }
        return "\n".join(f'{key}="{value}"' for key, value in fields.items()) + "\n"

    @property
    def issue_banner(self) -> str:
        return f"{self.name} {self.version} ({self.codename}) {self.architecture}\\n\\l\n"

    @property
    def package_seed(self) -> str:
        return "\n".join(sorted(self.packages)) + "\n"


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> XFactManifest:
    with path.open(encoding="utf-8") as manifest_file:
        data = json.load(manifest_file)
    if not isinstance(data, dict):
        raise ValueError("xFact manifest must be a JSON object")
    return XFactManifest.from_mapping(data)


def write_seed_files(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    manifest = load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "os-release": manifest.os_release,
        "issue": manifest.issue_banner,
        "package-seed.txt": manifest.package_seed,
    }
    written_paths: list[Path] = []
    for filename, contents in files.items():
        path = output_dir / filename
        path.write_text(contents, encoding="utf-8")
        written_paths.append(path)
    return written_paths


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to the xFact JSON manifest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where generated seed files are written.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xfact-manifest",
        description="Validate the xFact distro manifest and generate seed identity files.",
    )
    add_arguments(parser)
    return parser


def run(args: argparse.Namespace) -> int:
    written_paths = write_seed_files(args.manifest, args.output_dir)
    for path in written_paths:
        print(path)
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def _require_text(data: dict[str, Any], field: str) -> str:
    value = data[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"xFact manifest field '{field}' must be a non-empty string")
    return value


def _require_text_list(data: dict[str, Any], field: str) -> tuple[str, ...]:
    value = data[field]
    if not isinstance(value, list) or not value:
        raise ValueError(f"xFact manifest field '{field}' must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"xFact manifest field '{field}' must contain only non-empty strings")
    return tuple(value)
