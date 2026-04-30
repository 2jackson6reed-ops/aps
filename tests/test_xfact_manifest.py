import json
import tempfile
import unittest
from pathlib import Path

from xfact.manifest import XFactManifest, load_manifest, write_seed_files
from xfact.os_build import create_live_build_tree


class XFactManifestTests(unittest.TestCase):
    def test_manifest_generates_linux_identity_files(self) -> None:
        manifest = XFactManifest.from_mapping(
            {
                "name": "xFact",
                "version": "0.1.0",
                "codename": "axiom",
                "architecture": "x86_64",
                "base": "Debian stable",
                "edition": "core",
                "terminal": "aps-terminal",
                "goals": ["fact-first operations"],
                "packages": ["vim", "bash", "systemd"],
            }
        )

        self.assertIn('PRETTY_NAME="xFact 0.1.0 (axiom)"', manifest.os_release)
        self.assertIn("xFact 0.1.0 (axiom) x86_64", manifest.issue_banner)
        self.assertEqual(manifest.package_seed, "bash\nsystemd\nvim\n")

    def test_load_manifest_rejects_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(json.dumps({"name": "xFact"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Missing required xFact manifest fields"):
                load_manifest(manifest_path)

    def test_write_seed_files_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest_path = root / "manifest.json"
            output_dir = root / "seed"
            manifest_path.write_text(
                json.dumps(
                    {
                        "name": "xFact",
                        "version": "0.1.0",
                        "codename": "axiom",
                        "architecture": "x86_64",
                        "base": "Debian stable",
                        "edition": "core",
                        "terminal": "aps-terminal",
                        "goals": ["fact-first operations"],
                        "packages": ["sudo", "bash"],
                    }
                ),
                encoding="utf-8",
            )

            written_files = write_seed_files(manifest_path, output_dir)

            self.assertEqual(
                {path.name for path in written_files},
                {"issue", "os-release", "package-seed.txt"},
            )
            self.assertEqual(
                (output_dir / "package-seed.txt").read_text(encoding="utf-8"),
                "bash\nsudo\n",
            )

    def test_create_live_build_tree_for_bootable_os(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest_path = root / "manifest.json"
            output_dir = root / "xfact-live"
            manifest_path.write_text(
                json.dumps(
                    {
                        "name": "xFact",
                        "version": "0.1.0",
                        "codename": "axiom",
                        "architecture": "x86_64",
                        "base": "Debian GNU/Linux",
                        "edition": "core",
                        "terminal": "aps-terminal",
                        "goals": ["fact-first operations"],
                        "packages": ["sudo", "bash"],
                    }
                ),
                encoding="utf-8",
            )

            tree = create_live_build_tree(manifest_path, output_dir)

            self.assertEqual(tree.root, output_dir)
            auto_config = output_dir / "auto" / "config"
            auto_build = output_dir / "auto" / "build"
            self.assertTrue(auto_config.exists())
            self.assertTrue(auto_config.stat().st_mode & 0o111)
            auto_config_text = auto_config.read_text(encoding="utf-8")
            self.assertIn("--binary-images iso-hybrid", auto_config_text)
            self.assertIn("--debian-installer false", auto_config_text)
            self.assertIn("--firmware-chroot false", auto_config_text)
            self.assertIn("--initsystem systemd", auto_config_text)
            self.assertIn("--mode debian", auto_config_text)
            self.assertIn("--security false", auto_config_text)
            self.assertIn('--mirror-bootstrap "http://deb.debian.org/debian/"', auto_config_text)
            self.assertIn("lb build noauto", auto_build.read_text(encoding="utf-8"))
            package_list = output_dir / "config" / "package-lists" / "xfact.list.chroot"
            packages = package_list.read_text(encoding="utf-8").splitlines()
            self.assertIn("live-boot", packages)
            self.assertIn("isolinux", packages)
            self.assertIn("network-manager", packages)
            self.assertIn("libnss-systemd", packages)
            self.assertIn("live-config-systemd", packages)
            self.assertIn("sudo", packages)
            self.assertIn("syslinux-utils", packages)
            bootloader = output_dir / "config" / "bootloaders" / "isolinux"
            self.assertTrue((bootloader / "isolinux.bin").is_symlink())
            self.assertEqual(
                (bootloader / "isolinux.bin").readlink(),
                Path("/usr/lib/ISOLINUX/isolinux.bin"),
            )
            self.assertEqual(
                (bootloader / "vesamenu.c32").readlink(),
                Path("/usr/lib/syslinux/modules/bios/vesamenu.c32"),
            )
            self.assertEqual(
                (bootloader / "ldlinux.c32").readlink(),
                Path("/usr/lib/syslinux/modules/bios/ldlinux.c32"),
            )
            self.assertEqual(
                (bootloader / "libcom32.c32").readlink(),
                Path("/usr/lib/syslinux/modules/bios/libcom32.c32"),
            )
            self.assertEqual(
                (bootloader / "libutil.c32").readlink(),
                Path("/usr/lib/syslinux/modules/bios/libutil.c32"),
            )
            self.assertFalse((bootloader / "splash.svg.in").exists())
            live_template = (bootloader / "live.cfg.in").read_text(encoding="utf-8")
            self.assertIn("label live", live_template)
            self.assertIn("kernel /live/vmlinuz", live_template)
            self.assertIn("append initrd=/live/initrd.img", live_template)
            self.assertIn("include live.cfg", (bootloader / "menu.cfg").read_text(encoding="utf-8"))
            self.assertFalse((bootloader / "stdmenu.cfg").exists())
            self.assertFalse((bootloader / "install.cfg").exists())
            bootlogo = (bootloader / "bootlogo").read_bytes()
            self.assertTrue(bootlogo.startswith(b"070701"))
            self.assertIn(b"TRAILER!!!", bootlogo)
            isolinux_config = (bootloader / "isolinux.cfg").read_text(encoding="utf-8")
            self.assertIn("default live", isolinux_config)
            self.assertIn("serial 0 115200", isolinux_config)
            self.assertIn("console=ttyS0,115200", auto_config_text)
            self.assertEqual(
                (output_dir / "config" / "includes.chroot" / "etc" / "os-release").read_text(
                    encoding="utf-8"
                ),
                XFactManifest.from_mapping(json.loads(manifest_path.read_text(encoding="utf-8"))).os_release,
            )
            self.assertTrue(
                (output_dir / "config" / "includes.chroot" / "usr" / "local" / "bin" / "xfact-info")
                .read_text(encoding="utf-8")
                .startswith("#!/bin/sh")
            )
            self.assertTrue((output_dir / "config" / "includes.chroot" / "opt" / "aps-terminal").exists())


if __name__ == "__main__":
    unittest.main()
