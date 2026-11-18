"""Serve the prebuilt Warehouse Studio shell on this PC."""

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

# The Windows launcher uses -I, which excludes the script directory.
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime import preparation

HOST = "127.0.0.1"
PORT = 8765
DIST = Path(__file__).resolve().parents[1] / "dist"
ASSETS = {
    "index.html": "text/html; charset=utf-8",
    "assets/studio.js": "text/javascript; charset=utf-8",
    "assets/index.css": "text/css; charset=utf-8",
}
PREPARATION_REQUESTS = {
    "/api/preparation": (preparation.state, False),
    "/api/csv-import": (preparation.import_source, True),
    "/api/csv-page": (preparation.page, False),
    "/api/csv-apply": (preparation.apply, True),
}
BODY_LIMITS = {
    "/api/csv-import": 4 * ((preparation.MAX_SOURCE_BYTES + 2) // 3) + 65_536,
    "/api/csv-page": 512 * 1024,
    "/api/csv-apply": 512 * 1024,
}


def read_assets(directory):
    assets = {}
    for name, content_type in ASSETS.items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory):
            raise RuntimeError(f"Asset outside the build folder: {name}. Restore the application files.")
        try:
            assets["/" + name] = content_type, path.read_bytes()
        except OSError as error:
            raise RuntimeError(f"Cannot read dist/{name}. Restore the built application files.") from error
    assets["/"] = assets["/index.html"]
    return assets


class AssetHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, assets, **kwargs):
        self.assets = assets
        super().__init__(*args, **kwargs)

    def do_HEAD(self):
        self.serve_asset()

    def do_GET(self):
        self.serve_asset()

    def do_POST(self):
        host = f"{HOST}:{self.server.server_port}"
        origin = f"http://{host}"
        if self.headers.get("Host") != host or self.headers.get("Origin") != origin:
            self.send_error(403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= BODY_LIMITS.get(self.path, 4096):
                raise ValueError("Invalid request size.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Expected a project request.")
            result = self.project_request(data, origin)
        except (ValueError, OSError, RuntimeError) as error:
            self.send_json(400, {"error": str(error)})
        else:
            self.send_json(200, result)

    def project_request(self, data, origin):
        store = self.server.projects
        key = data.get("key", "")
        if not isinstance(key, str):
            raise ValueError("Invalid project reference.")
        if self.path in PREPARATION_REQUESTS:
            operation, write = PREPARATION_REQUESTS[self.path]
            with store.open_database(key, write=write) as (db, _, _):
                return operation(db, data)
        match self.path:
            case "/api/choose-folder":
                folder = choose_folder()
                return store.choose(folder) if folder else None
            case "/api/list":
                return store.listing(key)
            case "/api/create":
                return store.create(key, data.get("name"))
            case "/api/open":
                store.project(key)
                open_edge(f"{origin}/#project={key}")
                return None
            case "/api/project":
                return store.project(key)
            case "/api/save":
                return store.project(key, update=data)
            case _:
                raise ValueError("Unknown project operation.")

    def send_json(self, status, payload):
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        try:
            self.wfile.write(content)
        except ConnectionError:
            # Switching steps can cancel an in-flight preview.
            pass

    def log_message(self, format, *args):
        # A launcher can detach its output pipe while the browser is still loading.
        try:
            super().log_message(format, *args)
        except OSError:
            pass

    def serve_asset(self):
        asset = self.assets.get(self.path.partition("?")[0])
        if asset is None:
            self.send_error(404)
            return
        content_type, data = asset
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        if self.command == "GET":
            self.wfile.write(data)


class LocalServer(ThreadingHTTPServer):
    def server_bind(self):
        # Windows SO_REUSEADDR can let a second service bind the occupied port.
        if os.name == "nt":
            self.allow_reuse_address = False
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def check_python():
    if sys.version_info < (3, 13):
        raise RuntimeError("Use the approved Python 3.13 or newer installation.")
    try:
        import sqlite3
    except ImportError as error:
        raise RuntimeError("sqlite3 is missing. Select a Python installation with sqlite3 support.") from error
    return f"Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}"


def open_edge(url):
    for location in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        if location in os.environ:
            edge = Path(os.environ[location]) / "Microsoft/Edge/Application/msedge.exe"
            if edge.is_file():
                try:
                    subprocess.Popen([str(edge), f"--app={url}"])
                except OSError as error:
                    raise RuntimeError(f"Edge could not start. Check that Microsoft Edge opens normally: {error}") from error
                return
    raise RuntimeError("Microsoft Edge was not found. Check the installed Edge application and try again.")


def choose_folder():
    picker = Path(__file__).with_name("choose_folder.py")
    result = subprocess.run([sys.executable, "-I", str(picker)], capture_output=True)
    if result.returncode:
        raise RuntimeError("The Windows folder picker could not open. Check that your Python installation includes Tk.")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="serve the interface without launching Edge")
    parser.add_argument("--port", type=int, default=PORT, help=f"IPv4 loopback port (default {PORT})")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("choose a port between 0 and 65535")
    try:
        versions = check_python()
        from runtime.projects import ProjectStore

        handler = partial(AssetHandler, assets=read_assets(DIST))
        try:
            server = LocalServer((HOST, args.port), handler)
        except OSError as error:
            raise RuntimeError(f"Cannot listen on {HOST}:{args.port}. Close the other service or choose a free port with --port.") from error
        with server:
            server.projects = ProjectStore(DIST.parent)
            url = f"http://{HOST}:{server.server_port}/"
            if not args.no_browser:
                open_edge(url)
            print(f"Warehouse Studio at {url} ({versions}). Press Ctrl+C to stop.", flush=True)
            server.serve_forever()
    except RuntimeError as error:
        print(f"Warehouse Studio: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
