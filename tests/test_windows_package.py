"""Package manifest and Windows Shell link behavior."""

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from zipfile import ZipFile

from runtime.shortcuts import shortcut_target, update_shortcut
from scripts.package_windows import build_zip


class WindowsPackageTests(unittest.TestCase):
    def test_zip_is_reproducible_and_contains_only_the_runtime(self):
        with TemporaryDirectory() as directory:
            first, second = (Path(directory) / name for name in ("first.zip", "second.zip"))
            self.assertEqual(build_zip(first), build_zip(second))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.namelist(), sorted([
                    "Create Warehouse Studio Shortcut.cmd", "Remove Warehouse Studio Shortcut.cmd",
                    "Start Warehouse Studio.cmd", "README.txt", "LICENSE",
                    "dist/index.html", "dist/assets/index.css", "dist/assets/studio.js",
                    "licenses/react.txt", "licenses/react-dom.txt", "licenses/scheduler.txt",
                    "runtime/server.py", "runtime/projects.py", "runtime/preparation.py",
                    "runtime/choose_folder.py", "runtime/shortcuts.py",
                ]))
                for name in archive.namelist():
                    if name.endswith(".cmd"):
                        self.assertNotIn(b"\n", archive.read(name).replace(b"\r\n", b""))
                        self.assertTrue(archive.read(name).endswith(b"\r\n"))

    @unittest.skipUnless(os.name == "nt", "Windows Shell links")
    def test_create_and_remove_only_the_shortcut_to_this_copy(self):
        with TemporaryDirectory(prefix="Warehouse Studio ") as directory:
            root = Path(directory).resolve()
            source = root / "Start Warehouse Studio.cmd"
            source.write_text("@echo off\n", encoding="ascii")
            project = root / "sample.warehouse.sqlite3"
            project.write_bytes(b"synthetic data")
            link = root / "Warehouse Studio.lnk"

            self.assertIn("Created", update_shortcut("create", link, source))
            self.assertEqual(Path(shortcut_target(link)), source)
            contents = link.read_bytes()
            self.assertIn("already", update_shortcut("create", link, source))
            for action in ("create", "remove"):
                with self.subTest(action=action), self.assertRaisesRegex(ValueError, "another location"):
                    update_shortcut(action, link, root / "somewhere else" / source.name)
            self.assertEqual(link.read_bytes(), contents)
            self.assertIn("Removed", update_shortcut("remove", link, source))
            self.assertFalse(link.exists())
            self.assertIn("no Warehouse Studio shortcut", update_shortcut("remove", link, source))
            self.assertTrue(source.is_file())
            self.assertEqual(project.read_bytes(), b"synthetic data")
