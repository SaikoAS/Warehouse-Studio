"""Serve synthetic data on a dedicated local service for Edge UI tests."""

from functools import partial
from pathlib import Path
from subprocess import Popen
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import server
from runtime.projects import ProjectStore


def serve(projects, fragment=""):
    handler = partial(server.AssetHandler, assets=server.read_assets(ROOT / "dist"))
    with server.LocalServer((server.HOST, 0), handler) as http:
        http.projects = projects
        print(f"http://{server.HOST}:{http.server_port}/{fragment}", flush=True)
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
    project, = projects.create(folder, "Existing local project")["projects"]
    if sys.argv[2:] == ["--launcher"]:
        # Use the actual picker script with an unavailable Tk module. Edge uses its test profile.
        with (patch.object(server.subprocess, "Popen", new=start_picker_without_tk),
              patch.object(server, "open_edge", side_effect=lambda url: print(url, flush=True))):
            serve(projects)
    else:
        serve(projects, f"#project={project['key']}")
