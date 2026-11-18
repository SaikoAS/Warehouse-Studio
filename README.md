# Warehouse-Studio

Warehouse Studio is an open-source warehouse software project. Its Windows launcher opens local SQLite projects in dedicated Microsoft Edge windows. Each project can import a CSV, prepare it in steps, and save a result.

## Start on Windows

Double-click **Start Warehouse Studio.cmd** in a writable folder containing the script, the complete `runtime` folder and the `dist` build. Edge opens the launcher at `http://127.0.0.1:8765/`. Keep the start window open while working. Press Ctrl+C there to stop the service.

See [Build and verify the Windows ZIP](docs/windows-zip.md) for the distributable package, optional Start menu shortcut and offline acceptance steps.

Use an existing Python 3.13 or newer with the standard-library `sqlite3` module. The Windows 11 startup check used Python 3.13.14 with SQLite 3.50.4. The script uses `python.exe` from your environment. To select another approved installation, set `WAREHOUSE_STUDIO_PYTHON` to its full executable path. If port 8765 is occupied, close the previous service or [start on a free port with the same approved Python executable](docs/windows-compatibility.md#start-on-a-different-port).

### Work with projects

In File Explorer, copy the absolute path of a writable local folder outside the application folder. Paste it into **Project folder path** and select **Use folder**. Paths copied with the surrounding quotes from **Copy as path** also work. **Browse (optional)** opens the Windows folder picker when Tk is available. If the picker fails, enter the path directly.

**New project** creates a versioned `.warehouse.sqlite3` file in the selected folder. **Open project** opens a separate Edge window. The launcher can switch folders while existing project windows continue using their original files. See [Windows compatibility and runtime dependencies](docs/windows-compatibility.md) for diagnostics and the managed-PC acceptance procedure.

Each project window can edit and save its project's name. The filename stays stable when the display name changes. Use **Refresh** in the launcher to see changes made in another window. Opening the same project twice creates two windows on the same database. If one window saves first, the other must reload the saved name before it can save a new change. After restarting the service, select the data folder again and reopen projects from the launcher.

### Prepare a CSV

1. Open a project and choose a UTF-8, semicolon-delimited CSV. Use the first record for column names, or enter names for a headerless file. **Import CSV** stores the exact file bytes in the project's SQLite database. **Source** shows the original values, including text identifiers such as `0007`.
2. Add, edit, reorder or remove steps. Select a step to preview the output through that step. You can rename a column, keep or remove rows by exact value, and convert columns to Text or Decimal. The column selector uses the source names so steps still refer to the same column after you reorder them.
3. Select **Apply** to save the steps and result together. A conversion error points to the original CSV line and column. If Apply fails, **Saved result** still shows the last valid result. Reopen the project to see the saved steps and result, or select **Apply** again to rerun them on the original source.

The prototype supports one CSV per project, up to **1 MiB (1,048,576 bytes)**, 64 columns, 4,096 Unicode code points per data field or filter value, 120 characters per column name, and 20 steps. All data records must have the same number of fields. A decimal step requires a locale. Choose German (Germany) for `12,50` or English (United States) for `12.50`. Use signed or unsigned digits with an optional fractional part, without digit grouping. Results preserve exact decimal digits and use a decimal point. Exact filters compare the current cell value at their position in the step list. For comparisons, CRLF, CR, and LF are equivalent line breaks. Stored and displayed cell values retain their original line endings.

The [synthetic CSV examples](tests/fixtures/README.md) include the expected prepared rows and an error case.

### Build and test

With Node 24, run these commands from the repository root. Only development and CI need npm.

```sh
npm ci
npm run typecheck
npm run build
python -m unittest discover -s tests -v
```

With Microsoft Edge installed, run `npm run test:edge` after the build to exercise manual folder selection and CSV preparation in separate headless browser profiles.

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
