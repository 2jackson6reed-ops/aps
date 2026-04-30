import json
import tempfile
import unittest
from pathlib import Path

from xfact.manifest import XFactManifest, load_manifest, write_seed_files


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


if __name__ == "__main__":
    unittest.main()
