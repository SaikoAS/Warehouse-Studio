# Warehouse-Studio

Warehouse Studio is an open-source warehouse software project. Its Windows launcher opens local SQLite projects in dedicated Microsoft Edge windows. CSV preparation is planned for the first prototype.

## Start on Windows

Double-click **Start Warehouse Studio.cmd** in a writable folder containing the script, the complete `runtime` folder and the `dist` build. Edge opens the launcher at `http://127.0.0.1:8765/`. Keep the start window open while working. Press Ctrl+C there to stop the service.

Use an existing Python 3.13 or newer with the standard-library `sqlite3` module. The Windows 11 startup check used Python 3.13.14 with SQLite 3.50.4. The script uses `python.exe` from your environment. To select another approved installation, set `WAREHOUSE_STUDIO_PYTHON` to its full executable path. If port 8765 is occupied, close the previous service or run `python -I runtime/server.py --port 8766` from the application folder with a free port.

### Work with projects

With the build available, **Choose folder** opens the Windows directory picker through Python's standard Tk module. Select a writable local data folder outside the application folder. **New project** creates a versioned `.warehouse.sqlite3` file. **Open project** opens a separate Edge window. The launcher can switch folders while existing project windows continue using their original files.

Each project window can edit and save its project's name. The filename stays stable when the display name changes. Use **Refresh** in the launcher to see changes made in another window. Opening the same project twice creates two windows on the same database. If one window saves first, the other must reload the saved name before it can save a new change. After restarting the service, select the data folder again and reopen projects from the launcher.

### Build and test

With Node 24, run these commands from the repository root. Only development and CI need npm.

```sh
npm ci
npm run typecheck
npm run build
python -m unittest discover -s tests -v
```

Vite writes the interface and its local JavaScript and stylesheet to `dist`. The Python service exposes only those three build files. For a browser-free check, run `python -I runtime/server.py --no-browser`.

## Project status

- Initial target: **v0.1.0 – Initial Prototype**. See the [architecture decision and planned acceptance checks](docs/adr/0001-v0.1.0-architecture.md).
- Stack: TypeScript, React and Vite for the interface. A local Python service and one SQLite file per project support offline use in Edge on Windows.
- Development model: GitHub Issues and pull requests, with manually launched Codex tasks and human approval of every merge and release.
- License: [MIT](LICENSE), retained from the initial repository.

## Participate

Use the [issue forms](https://github.com/SaikoAS/Warehouse-Studio/issues/new/choose) for bugs, features and technical tasks. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md) before contributing. Report vulnerabilities through the private process in [SECURITY.md](SECURITY.md).

## Development and planning

- [Public development Project](https://github.com/users/SaikoAS/projects/6)
- [Verified Phase 1 setup and remaining owner actions](docs/phase-1-status.md)
- [Agent working rules](AGENTS.md)
- [Project fields, labels and workflow](docs/project-management.md)
- [Codex Cloud setup and manual task handoff](docs/codex-cloud.md)
- [Versioning and release checklist](docs/releases.md)
- [Phase 1 administration checklist](docs/phase-1-setup.md)

CI checks repository documents and configuration, type-checks and builds the frontend, and runs the runtime smoke tests on Windows.
