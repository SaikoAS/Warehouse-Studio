"""Serve synthetic data on a dedicated local service for Edge UI tests."""

from functools import partial
from pathlib import Path
from subprocess import Popen
import sys
from threading import Event
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import server
from runtime.projects import ProjectStore


class FixtureProcess:
    def __init__(self):
        self.closed = Event()

    def wait(self):
        self.closed.wait()
        return 0

    def poll(self):
        return 0 if self.closed.is_set() else None

    def terminate(self):
        self.closed.set()


class FixtureHandler(server.AssetHandler):
    def project_request(self, data, origin):
        if self.path == "/api/fixture-project-ended":
            self.server.browser.terminate()
            return None
        return super().project_request(data, origin)


def serve(projects):
    handler = partial(FixtureHandler, assets=server.read_assets(ROOT / "dist"))
    with server.LocalServer((server.HOST, 0), handler) as http:
        http.projects = projects

        def launch(url):
            http.browser = FixtureProcess()
            print(url, flush=True)
            return http.browser

        http.navigation.launch = launch
        print(f"http://{server.HOST}:{http.server_port}/", flush=True)
        http.serve_forever()


def start_picker_without_tk(args, *popen_args, **options):
    picker = Path(server.__file__).with_name("choose_folder.py")
    if args != [sys.executable, "-I", str(picker)]:
        raise AssertionError("The fixture permits only the optional Python folder picker.")
    block_tk = "import runpy, sys; sys.modules['tkinter'] = None; runpy.run_path(sys.argv[1], run_name='__main__')"
    return Popen([sys.executable, "-I", "-c", block_tk, str(picker)], *popen_args, **options)


if __name__ == "__main__":
    projects = ProjectStore(ROOT)
    folder = projects.choose(Path(sys.argv[1]))["folder"]
    projects.create(folder, "Existing local project")
    if sys.argv[2:] == ["--launcher"]:
        # Use the actual picker script with an unavailable Tk module. Edge uses its test profile.
        with patch.object(server.subprocess, "Popen", new=start_picker_without_tk):
            serve(projects)
    else:
        serve(projects)
