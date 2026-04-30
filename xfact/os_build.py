"""Generate a bootable xFact live OS build tree."""

from __future__ import annotations

import argparse
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from .manifest import DEFAULT_MANIFEST_PATH, REPO_ROOT, XFactManifest, load_manifest


DEFAULT_LIVE_BUILD_DIR = REPO_ROOT / "build" / "xfact-live"
REQUIRED_TOOLS = ("lb", "xorriso", "mksquashfs", "isohybrid")


@dataclass(frozen=True)
class LiveBuildTree:
    """Paths produced for an xFact live-build project."""

    root: Path
    files: tuple[Path, ...]


def create_live_build_tree(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    output_dir: Path = DEFAULT_LIVE_BUILD_DIR,
) -> LiveBuildTree:
    """Create a Debian live-build tree capable of producing xFact ISO images."""
    manifest = load_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    written.extend(_write_auto_scripts(output_dir, manifest))
    written.extend(_write_live_build_config(output_dir, manifest))
    written.extend(_write_bootloader_template(output_dir))
    written.extend(_write_chroot_includes(output_dir, manifest, manifest_path))
    written.extend(_copy_python_sources(output_dir))
    return LiveBuildTree(output_dir, tuple(written))


def missing_required_tools() -> tuple[str, ...]:
    """Return live-build tools missing from PATH."""
    return tuple(tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xfact-os",
        description="Generate a bootable xFact Debian live-build project.",
    )
    add_arguments(parser)
    return parser


def add_arguments(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="os_command")

    configure = subparsers.add_parser("configure", help="Generate the xFact live-build project files.")
    configure.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to the xFact JSON manifest.",
    )
    configure.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_LIVE_BUILD_DIR,
        help="Directory where live-build files are written.",
    )

    subparsers.add_parser(
        "check-prereqs",
        help="Check whether local ISO build tools are installed.",
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    if args.os_command == "check-prereqs":
        missing = missing_required_tools()
        if missing:
            print("Missing xFact OS build tools: " + ", ".join(missing))
            return 1
        print("All xFact OS build tools are available.")
        return 0

    if args.os_command in (None, "configure"):
        output_dir = getattr(args, "output_dir", DEFAULT_LIVE_BUILD_DIR)
        manifest_path = getattr(args, "manifest", DEFAULT_MANIFEST_PATH)
        tree = create_live_build_tree(manifest_path, output_dir)
        for path in tree.files:
            print(path)
        print(f"Run 'cd {tree.root} && sudo lb build' to build the xFact ISO.")
        return 0

    return 2


def _write_auto_scripts(output_dir: Path, manifest: XFactManifest) -> list[Path]:
    auto_dir = output_dir / "auto"
    auto_dir.mkdir(parents=True, exist_ok=True)
    distribution = _debian_distribution(manifest)
    architecture = _debian_architecture(manifest)
    scripts = {
        "config": f"""#!/bin/sh
set -eu
lb config noauto \\
  --architectures {architecture} \\
  --archive-areas "main contrib non-free-firmware" \\
  --binary-images iso-hybrid \\
  --bootappend-live "boot=live components hostname=xfact username=xfact locales=en_US.UTF-8" \\
  --debian-installer false \\
  --distribution {distribution} \\
  --firmware-binary false \\
  --firmware-chroot false \\
  --initsystem systemd \\
  --mirror-binary "http://deb.debian.org/debian/" \\
  --mirror-bootstrap "http://deb.debian.org/debian/" \\
  --mirror-chroot "http://deb.debian.org/debian/" \\
  --mode debian \\
  --parent-distribution {distribution} \\
  --parent-mirror-bootstrap "http://deb.debian.org/debian/" \\
  --security false \\
  --iso-application "xFact Linux" \\
  --iso-publisher "xFact" \\
  --iso-volume "xFact {manifest.version}" \\
  "${{@}}"
""",
        "build": """#!/bin/sh
set -eu
lb build noauto "${@}"
""",
        "clean": """#!/bin/sh
set -eu
lb clean noauto --purge "${@}"
""",
    }

    written: list[Path] = []
    for filename, contents in scripts.items():
        path = auto_dir / filename
        _write_text(path, contents)
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written.append(path)
    return written


def _write_live_build_config(output_dir: Path, manifest: XFactManifest) -> list[Path]:
    package_dir = output_dir / "config" / "package-lists"
    package_dir.mkdir(parents=True, exist_ok=True)
    hooks_dir = output_dir / "config" / "hooks" / "normal"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    packages = sorted(
        {
            *manifest.packages,
            "ca-certificates",
            "dbus",
            "initramfs-tools",
            "isolinux",
            "libnss-systemd",
            "live-boot",
            "live-config",
            "live-config-systemd",
            "locales",
            "network-manager",
            "python3",
            "systemd-sysv",
        }
    )
    package_list = package_dir / "xfact.list.chroot"
    _write_text(package_list, "\n".join(packages) + "\n")

    hook = hooks_dir / "0100-xfact-branding.hook.chroot"
    _write_text(
        hook,
        """#!/bin/sh
set -eu
printf 'xFact\\n' > /etc/hostname
ln -sf /lib/systemd/system/multi-user.target /etc/systemd/system/default.target
chmod +x /usr/local/bin/aps-terminal /usr/local/bin/xfact-info
""",
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    readme = output_dir / "README.md"
    _write_text(
        readme,
        f"""# xFact live OS build

This directory is generated by `python3 -m xfact.os_build configure`.

Build prerequisites on Debian/Ubuntu:

- live-build
- xorriso
- squashfs-tools
- sudo/root privileges for `lb build`

Build the bootable ISO:

```bash
sudo lb clean --purge || true
sudo lb build
```

The top-level `build-xfact.sh` wrapper renames the generated ISO to
`xfact-{manifest.version}-{_debian_architecture(manifest)}.hybrid.iso`.
""",
    )
    return [package_list, hook, readme]


def _write_chroot_includes(
    output_dir: Path,
    manifest: XFactManifest,
    manifest_path: Path,
) -> list[Path]:
    includes = output_dir / "config" / "includes.chroot"
    etc = includes / "etc"
    bin_dir = includes / "usr" / "local" / "bin"
    opt_dir = includes / "opt" / "xfact"
    for directory in (etc, bin_dir, opt_dir):
        directory.mkdir(parents=True, exist_ok=True)

    files = {
        etc / "os-release": manifest.os_release,
        etc / "issue": manifest.issue_banner,
        etc / "motd": _motd(manifest),
        etc / "hosts": "127.0.0.1 localhost\n127.0.1.1 xfact\n",
        bin_dir / "aps-terminal": _aps_terminal_wrapper(),
        bin_dir / "xfact-info": _xfact_info_script(manifest),
    }

    written: list[Path] = []
    for path, contents in files.items():
        _write_text(path, contents)
        written.append(path)

    for path in (bin_dir / "aps-terminal", bin_dir / "xfact-info"):
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    manifest_copy = opt_dir / "manifest.json"
    shutil.copyfile(manifest_path, manifest_copy)
    written.append(manifest_copy)
    return written


def _write_bootloader_template(output_dir: Path) -> list[Path]:
    source_dir = Path("/usr/share/live/build/bootloaders/isolinux")
    target_dir = output_dir / "config" / "bootloaders" / "isolinux"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir, symlinks=True)

    links = {
        "isolinux.bin": "/usr/lib/ISOLINUX/isolinux.bin",
        "vesamenu.c32": "/usr/lib/syslinux/modules/bios/vesamenu.c32",
    }
    written: list[Path] = []
    for filename, destination in links.items():
        path = target_dir / filename
        if path.exists() or path.is_symlink():
            path.unlink()
        path.symlink_to(destination)
        written.append(path)

    splash = target_dir / "splash.svg.in"
    if splash.exists() or splash.is_symlink():
        splash.unlink()
    bootlogo = target_dir / "bootlogo"
    # cpio's "newc" end-of-archive marker with no payload files.
    bootlogo.write_bytes(_empty_newc_archive())
    written.append(bootlogo)
    return written


def _empty_newc_archive() -> bytes:
    name = b"TRAILER!!!\x00"
    fields = (
        "070701",  # c_magic
        "00000000",  # c_ino
        "00000000",  # c_mode
        "00000000",  # c_uid
        "00000000",  # c_gid
        "00000001",  # c_nlink
        "00000000",  # c_mtime
        "00000000",  # c_filesize
        "00000000",  # c_devmajor
        "00000000",  # c_devminor
        "00000000",  # c_rdevmajor
        "00000000",  # c_rdevminor
        f"{len(name):08x}",  # c_namesize
        "00000000",  # c_check
    )
    archive = "".join(fields).encode("ascii") + name
    return archive + (b"\x00" * ((4 - (len(archive) % 4)) % 4))


def _copy_python_sources(output_dir: Path) -> list[Path]:
    app_dir = output_dir / "config" / "includes.chroot" / "opt" / "aps-terminal"
    app_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for source_name in ("terminal_emulator", "xfact"):
        source = REPO_ROOT / source_name
        destination = app_dir / source_name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
        copied.append(destination)

    for filename in ("README.md", "pyproject.toml"):
        source = REPO_ROOT / filename
        destination = app_dir / filename
        shutil.copyfile(source, destination)
        copied.append(destination)
    return copied


def _write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _debian_distribution(manifest: XFactManifest) -> str:
    if "debian" not in manifest.base.lower():
        raise ValueError("xFact live OS builds currently require a Debian base")
    return "trixie"


def _debian_architecture(manifest: XFactManifest) -> str:
    architectures = {"x86_64": "amd64", "aarch64": "arm64"}
    try:
        return architectures[manifest.architecture]
    except KeyError as exc:
        raise ValueError(f"Unsupported xFact live OS architecture: {manifest.architecture}") from exc


def _motd(manifest: XFactManifest) -> str:
    goals = "\n".join(f"- {goal}" for goal in manifest.goals)
    return f"""Welcome to {manifest.name} {manifest.version} ({manifest.codename})

Goals:
{goals}

Run `xfact-info` for release details or `aps-terminal` to start the bundled terminal emulator.
"""


def _aps_terminal_wrapper() -> str:
    return """#!/bin/sh
set -eu
export PYTHONPATH=/opt/aps-terminal
exec python3 -m terminal_emulator "$@"
"""


def _xfact_info_script(manifest: XFactManifest) -> str:
    package_count = len(manifest.packages)
    return f"""#!/bin/sh
set -eu
printf '%s\\n' 'xFact {manifest.version} ({manifest.codename})'
printf '%s\\n' 'Architecture: {manifest.architecture}'
printf '%s\\n' 'Edition: {manifest.edition}'
printf '%s\\n' 'Terminal: {manifest.terminal}'
printf '%s\\n' 'Seed packages: {package_count}'
printf '%s\\n' 'Manifest: /opt/xfact/manifest.json'
"""
