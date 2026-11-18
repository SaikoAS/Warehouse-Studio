"""Session-scoped project references and version 1 SQLite metadata."""

from contextlib import closing, contextmanager
from pathlib import Path
import os
import sqlite3
import tempfile
import uuid


SUFFIX = ".warehouse.sqlite3"
APPLICATION_ID = 0x57535455  # WSTU
VERSION = 1


def project_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120:
        raise ValueError("Enter a project name between 1 and 120 characters.")
    return value.strip()


@contextmanager
def database(path, mode):
    if path.resolve() != path:
        raise ValueError("This project path has changed. Choose the folder again.")
    try:
        with closing(sqlite3.connect(f"{path.as_uri()}?mode={mode}", uri=True, timeout=2)) as db:
            db.execute("PRAGMA trusted_schema=OFF")
            db.row_factory = sqlite3.Row
            yield db
    except sqlite3.Error as error:
        raise ValueError(f"Cannot access {path.name}. Check that the project exists, is readable and permits the requested operation.") from error


def metadata(db, *, include_revision=True):
    if (db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
            or db.execute("PRAGMA user_version").fetchone()[0] != VERSION):
        raise ValueError("Unsupported Warehouse Studio project format.")
    columns = "id, name, revision" if include_revision else "id, name"
    row = db.execute(f"SELECT {columns} FROM project WHERE singleton = 1").fetchone()
    if row is None or not isinstance(row["id"], str):
        raise ValueError("Project metadata is incomplete.")
    if include_revision and not isinstance(row["revision"], int):
        raise ValueError("The project revision is invalid.")
    project_name(row["name"])
    return dict(row)


class ProjectStore:
    def __init__(self, app_folder):
        self.app_folder = app_folder.resolve()
        self.session = uuid.uuid4()
        self.folders = {}
        self.projects = {}

    def choose(self, path):
        path = Path(path).resolve(strict=True)
        if os.name == "nt":
            from ctypes import windll
            if path.drive.startswith("\\\\") or windll.kernel32.GetDriveTypeW(path.anchor) == 4:
                raise ValueError("Choose a folder on a local drive.")
        if not path.is_dir() or path.is_relative_to(self.app_folder):
            raise ValueError("Choose a data folder outside the application folder.")
        try:
            with tempfile.TemporaryFile(dir=path):
                pass
        except OSError as error:
            raise ValueError("Choose a writable data folder.") from error
        key = uuid.uuid5(self.session, str(path)).hex
        self.folders[key] = path
        return self.listing(key)

    def folder(self, key):
        path = self.folders.get(key)
        if path is None or not path.is_dir() or path.resolve() != path:
            raise ValueError("The data folder is unavailable. Choose the folder again.")
        return path

    def listing(self, folder):
        path = self.folder(folder)
        projects, warnings = [], []
        for file in path.iterdir():
            if not file.name.lower().endswith(SUFFIX):
                continue
            try:
                with database(file, "ro") as db:
                    row = metadata(db, include_revision=False)
                token = uuid.uuid5(self.session, str(file) + "\0" + row["id"]).hex
                self.projects[token] = (file, row["id"])
                projects.append({"key": token, "name": row["name"], "file": file.name})
            except (OSError, ValueError) as error:
                warnings.append(f"{file.name}: {error}")
        projects.sort(key=lambda item: (item["name"].casefold(), item["file"]))
        return {"folder": folder, "path": str(path), "projects": projects, "warnings": sorted(warnings)}

    def create(self, folder, name):
        path = self.folder(folder)
        name = project_name(name)
        identity = uuid.uuid4().hex
        target = path / (identity + SUFFIX)
        # Publish the database only after its schema and metadata commit together.
        with tempfile.NamedTemporaryFile(dir=path, suffix=".tmp", delete=False) as scratch:
            temporary = Path(scratch.name)
        try:
            with database(temporary, "rw") as db, db:
                db.execute("BEGIN")
                db.execute(f"PRAGMA application_id={APPLICATION_ID}")
                db.execute(f"PRAGMA user_version={VERSION}")
                db.execute("""CREATE TABLE project (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    id TEXT NOT NULL, name TEXT NOT NULL, revision INTEGER NOT NULL
                )""")
                db.execute("INSERT INTO project VALUES (1, ?, ?, 1)", (identity, name))
            temporary.rename(target)
        finally:
            temporary.unlink(missing_ok=True)
        return self.listing(folder)

    def project(self, key, *, update=None):
        reference = self.projects.get(key)
        if reference is None:
            raise ValueError("This project window has expired. Reopen the project from the launcher.")
        path, identity = reference
        with database(path, "rw" if update is not None else "ro") as db, db:
            if update is not None:
                db.execute("BEGIN IMMEDIATE")
            row = metadata(db)
            if row["id"] != identity:
                raise ValueError("The project file was replaced. Refresh the launcher and reopen the project.")
            if update is not None:
                name = project_name(update.get("name"))
                if type(update.get("revision")) is not int or row["revision"] != update["revision"]:
                    raise ValueError("Another window saved this project. Reload the saved name before editing again.")
                db.execute("UPDATE project SET name = ?, revision = revision + 1 WHERE singleton = 1", (name,))
                row = metadata(db)
        return {"name": row["name"], "revision": row["revision"], "file": path.name}
