"""Project metadata, window bindings and the local HTTP contract."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from functools import partial
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from runtime import server
from runtime.navigation import ProjectSession
from runtime.projects import APPLICATION_ID, ProjectStore, SUFFIX, VERSION


class ProjectTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.app = root / "Application"
        self.data = root / "Data"
        self.other = root / "Other"
        for folder in (self.app, self.data, self.other):
            folder.mkdir()
        self.store = ProjectStore(self.app)
        self.folder = self.store.choose(self.data)["folder"]

    def test_isolation_folder_switch_and_reopen(self):
        a, = self.store.create(self.folder, "North")["projects"]
        _, b = self.store.create(self.folder, "South")["projects"]
        original = (self.data / a["file"]).read_bytes()
        second = self.store.choose(self.other)
        self.assertEqual(second["projects"], [])
        other_b, = self.store.create(second["folder"], "South")["projects"]
        self.store.project(b["key"], update={"name": "South saved", "revision": 1})
        self.assertEqual(self.store.project(a["key"])["name"], "North")
        self.assertEqual((self.data / a["file"]).read_bytes(), original)
        self.assertEqual(self.store.project(other_b["key"])["revision"], 1)

        restarted = ProjectStore(self.app)
        self.assertEqual([p["name"] for p in restarted.choose(self.data)["projects"]], ["North", "South saved"])
        with closing(sqlite3.connect(self.data / b["file"])) as db:
            self.assertEqual(db.execute("PRAGMA application_id").fetchone()[0], APPLICATION_ID)
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], VERSION)

    def test_same_revision_has_one_winner(self):
        project, = self.store.create(self.folder, "North")["projects"]

        def save(name):
            try:
                return self.store.project(project["key"], update={"name": name, "revision": 1})["name"]
            except ValueError as error:
                self.assertIn("Another window saved", str(error))
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            winners = [name for name in pool.map(save, ["First", "Second"]) if name]
        self.assertEqual(len(winners), 1)
        current = self.store.project(project["key"])
        self.assertEqual((current["revision"], current["name"]), (2, winners[0]))

    def test_missing_replaced_or_invalid_project_does_not_break_listing(self):
        first, = self.store.create(self.folder, "First")["projects"]
        _, second = self.store.create(self.folder, "Second")["projects"]
        original = self.data / first["file"]
        original.unlink()
        with self.assertRaisesRegex(ValueError, "Cannot access"):
            self.store.project(first["key"])
        self.assertFalse(original.exists())
        (self.data / second["file"]).rename(original)
        with self.assertRaisesRegex(ValueError, "replaced"):
            self.store.project(first["key"], update={"name": "Wrong file", "revision": 1})
        (self.data / ("damaged" + SUFFIX)).write_bytes(b"Invalid file")
        (self.data / "unrelated.sqlite").write_bytes(b"Other data")
        listing = self.store.listing(self.folder)
        self.assertEqual([p["name"] for p in listing["projects"]], ["Second"])
        self.assertEqual(len(listing["warnings"]), 1)
        self.assertIn("damaged", listing["warnings"][0])

    def test_future_version_and_invalid_inputs(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            self.store.choose(self.app)
        with self.assertRaisesRegex(ValueError, "project name"):
            self.store.create(self.folder, "  ")
        self.assertEqual(list(self.data.iterdir()), [])
        project, = self.store.create(self.folder, "North")["projects"]
        with closing(sqlite3.connect(self.data / project["file"])) as db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            self.store.project(project["key"])
        self.assertEqual(self.store.listing(self.folder)["projects"], [])

    def test_select_folder_validates_the_path_and_preserves_existing_selection(self):
        selected, = self.store.create(self.folder, "Existing project")["projects"]
        quoted = self.data / "Project data with spaces"
        quoted.mkdir()
        self.assertEqual(self.store.choose(f'  "{quoted}"  ')["path"], str(quoted.resolve()))
        file = self.other / "file.txt"
        file.touch()
        known_folders = self.store.folders.copy()
        for path, message in [
            (None, "absolute local folder path"), ("relative", "absolute local folder path"),
            (str(self.data / "absent"), "does not exist"), (str(file), "points to a file"),
            (str(self.app), "outside the application folder"),
        ]:
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, message):
                self.store.choose(path)
        with patch("runtime.projects.tempfile.TemporaryFile", side_effect=PermissionError):
            with self.assertRaisesRegex(ValueError, "Cannot write"):
                self.store.choose(str(self.other))
        with patch.object(Path, "iterdir", side_effect=PermissionError):
            with self.assertRaisesRegex(ValueError, "Cannot list"):
                self.store.choose(str(self.other))
        self.assertEqual(self.store.folders, known_folders)
        self.assertEqual(self.store.listing(self.folder)["projects"], [selected])
        self.assertEqual(self.store.project(selected["key"])["name"], "Existing project")

    @unittest.skipUnless(os.name == "nt", "Windows network path rules")
    def test_rejects_network_and_drive_relative_paths_before_resolving(self):
        from ctypes import windll

        with patch.object(Path, "resolve") as resolve:
            with self.assertRaisesRegex(ValueError, "absolute local folder path"):
                self.store.choose(r"C:relative")
            with self.assertRaisesRegex(ValueError, "Network folders"):
                self.store.choose(r"\\workspace-server\projects\sample")
            with patch.object(windll.kernel32, "GetDriveTypeW", return_value=4):
                with self.assertRaisesRegex(ValueError, "Network folders"):
                    self.store.choose(r"Z:\projects")
            resolve.assert_not_called()

    def test_launcher_and_project_http_requests(self):
        handler = partial(server.AssetHandler, assets={})
        with server.LocalServer((server.HOST, 0), handler) as http:
            http.projects = self.store
            thread = Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                origin = f"http://{server.HOST}:{http.server_port}"

                def post(action, body, from_origin=origin):
                    with closing(HTTPConnection(server.HOST, http.server_port, timeout=3)) as conn:
                        conn.request("POST", "/api/" + action, json.dumps(body), {
                            "Origin": from_origin, "Content-Type": "application/json",
                        })
                        response = conn.getresponse()
                        raw = response.read()
                        return response.status, json.loads(raw) if response.status != 403 else None

                with patch.object(server, "choose_folder", return_value=self.data) as picker:
                    self.assertEqual(post("choose-folder", {}, "null")[0], 403)
                    picker.assert_not_called()
                    status, folder = post("choose-folder", {})
                self.assertEqual(status, 200)
                with patch.object(server, "choose_folder", side_effect=AssertionError("Manual entry invoked the picker")):
                    self.assertEqual(post("select-folder", {"path": str(self.data)}, "null")[0], 403)
                    self.assertEqual(post("select-folder", {"path": 3})[0], 400)
                    self.assertEqual(post("select-folder", {"path": str(self.data)}), (200, folder))
                status, listing = post("create", {"key": folder["folder"], "name": "North"})
                self.assertEqual(status, 200)
                project, = listing["projects"]
                with patch.object(http.navigation, "open") as open_project:
                    self.assertEqual(post("open", {"key": project["key"], "folder": folder["folder"]}), (200, None))
                    open_project.assert_called_once_with(project["key"], folder["folder"], origin)
                self.assertEqual(post("project", {"key": project["key"]})[0], 400)
                http.navigation.active = ProjectSession(project["key"], folder["folder"])
                reference = {"key": project["key"], "session": http.navigation.active.id}
                self.assertEqual(post("project", reference)[1]["name"], "North")
                status, saved = post("save", {**reference, "revision": 1, "name": "North saved"})
                self.assertEqual((status, saved["revision"]), (200, 2))
                self.assertEqual(post("list", {"key": folder["folder"]})[1]["projects"][0]["name"], "North saved")
                (self.data / project["file"]).unlink()
                self.assertEqual(post("open", {"key": project["key"]})[0], 400)
                self.assertEqual(post("list", {"key": folder["folder"]})[1]["projects"], [])
                with patch.object(server, "choose_folder", return_value=None):
                    self.assertEqual(post("choose-folder", {}), (200, None))
            finally:
                http.shutdown()
                thread.join()
