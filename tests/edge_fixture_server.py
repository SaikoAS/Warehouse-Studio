"""Open a synthetic project on a dedicated local service for the Edge UI test."""

from functools import partial
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import server
from runtime.projects import ProjectStore


if __name__ == "__main__":
    projects = ProjectStore(ROOT)
    folder = projects.choose(Path(sys.argv[1]))["folder"]
    project, = projects.create(folder, "Synthetic CSV filters")["projects"]
    handler = partial(server.AssetHandler, assets=server.read_assets(ROOT / "dist"))
    with server.LocalServer((server.HOST, 0), handler) as http:
        http.projects = projects
        print(f"http://{server.HOST}:{http.server_port}/#project={project['key']}", flush=True)
        http.serve_forever()
