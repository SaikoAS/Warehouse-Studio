"""Smoke tests against a runtime-only copy of the actual Vite build."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from http.client import HTTPConnection
from html.parser import HTMLParser
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from runtime import server


ROOT = Path(__file__).resolve().parents[1]
START = "Start Warehouse Studio.cmd"


class PageAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script":
            self.urls.append(attributes["src"])
        elif tag == "link" and attributes.get("rel") == "stylesheet":
            self.urls.append(attributes["href"])


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="Warehouse Studio ")
        self.addCleanup(folder.cleanup)
        self.app = Path(folder.name)
        (self.app / "runtime").mkdir()
        self.script = self.app / "runtime/server.py"
        shutil.copyfile(ROOT / "runtime/server.py", self.script)
        shutil.copytree(ROOT / "dist", self.app / "dist")
        shutil.copyfile(ROOT / START, self.app / START)

    def run_service(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(self.script), *args],
            cwd=self.app.parent, capture_output=True, text=True, timeout=10,
        )

    def test_serves_built_page_and_only_approved_assets(self):
        (self.app / "dist/project.sqlite").write_bytes(b"private fixture")
        (self.app / "dist/assets/extra.js").write_text("private fixture")
        with subprocess.Popen(
            [sys.executable, "-I", str(self.script), "--port", "0", "--no-browser"],
            cwd=self.app.parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ) as process, ThreadPoolExecutor(max_workers=1) as reader:
            try:
                line = reader.submit(process.stdout.readline).result(timeout=10)
                self.assertIn("http://127.0.0.1:", line)
                url = urlsplit(line.split()[3])
                with closing(HTTPConnection(url.hostname, url.port, timeout=5)) as conn:
                    conn.request("GET", "/")
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    page = PageAssets()
                    page.feed(response.read().decode("utf-8"))
                    self.assertCountEqual(page.urls, ["/assets/studio.js", "/assets/index.css"])
                    for path in page.urls:
                        conn.request("GET", path)
                        response = conn.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers.get_content_type(), server.ASSETS[path[1:]].split(";")[0])
                        self.assertEqual(response.read(), (self.app / "dist" / path[1:]).read_bytes())
                    for path in ("/runtime/server.py", "/src/main.tsx", "/project.sqlite", "/assets/extra.js", "/assets/"):
                        with self.subTest(path=path):
                            conn.request("GET", path)
                            response = conn.getresponse()
                            self.assertEqual(response.status, 404)
                            response.read()
            finally:
                process.terminate()
                process.wait(timeout=5)

    def test_busy_port(self):
        with socket.socket() as occupied:
            occupied.bind((server.HOST, 0))
            occupied.listen()
            port = str(occupied.getsockname()[1])
            result = self.run_service("--port", port)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"Cannot listen on 127.0.0.1:{port}", result.stderr)
        self.assertIn("--port", result.stderr)

    def test_incomplete_build(self):
        (self.app / "dist/assets/studio.js").unlink()
        result = self.run_service("--port", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Restore the built application files", result.stderr)

    def test_missing_edge(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Edge was not found"):
                server.open_edge("http://127.0.0.1/")

    def test_missing_sqlite(self):
        with patch.dict(sys.modules, {"sqlite3": None}):
            with self.assertRaisesRegex(RuntimeError, "sqlite3 is missing"):
                server.check_python()

    @unittest.skipUnless(os.name == "nt", "Windows start script")
    def test_launcher_missing_python(self):
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", START], cwd=self.app, input="\n",
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "WAREHOUSE_STUDIO_PYTHON": str(self.app / "missing.exe")},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("full path of your approved python.exe", result.stdout)
