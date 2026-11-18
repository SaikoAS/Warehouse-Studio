# Windows compatibility for v0.1.0

## Runtime and build requirements

| Component | Role | Requirement |
| --- | --- | --- |
| Windows and Command Processor | Runtime | The approved Windows installation must allow the user to run **Start Warehouse Studio.cmd** in the extracted application folder. |
| Approved Python 3.13 or newer with standard-library `sqlite3` | Runtime | Start the local Python service and use one SQLite file per project. The startup check opens an in-memory SQLite database and runs a query. |
| Microsoft Edge | Runtime | Open the launcher and project windows on IPv4 loopback. The browser's regular file dialog selects individual CSV files. |
| Local writable folder and loopback port | Runtime | Store projects in a user-writable local folder outside the application folder. The default service address is `127.0.0.1:8765`. |
| Tcl/Tk and Python `tkinter` | Optional | **Browse (optional)** uses the folder picker. **Project folder path** remains available if the picker fails, is unavailable, or waits for a response. |
| Current-user Start menu shortcut | Optional | The shortcut launches the extracted copy. **Start Warehouse Studio.cmd** is the direct launch method and remains available if shortcut setup is unavailable. |
| Node.js 24 and npm | Build and test | `npm ci` installs the versions in `package-lock.json`. `npm run build` produces the static assets. Playwright Core uses the installed Edge for browser tests. |
| Python test tools | Build and test | The application tests use `unittest`. The repository configuration check uses the version pinned in `.github/requirements-ci.txt`. |

The launcher starts Python directly through the Windows Command Processor. Manual folder selection sends the path to the local service. Python checks the local directory and its access permissions. This path supports offline operation under a standard user account without Tk, PowerShell, application installation, or runtime downloads.

Manual path entry gives Python the absolute Windows path it needs to open a project database in SQLite. Browser folder pickers expose selected files with relative paths or a directory handle scoped to the browser. The Edge CSV picker works because the import needs only the file contents. The existing Tk picker is optional because managed Python installations can omit Tcl/Tk. The PowerShell picker used by OpenSlotting requires the managed Windows policy to allow its script. See [the decision and alternatives in Issue #12](https://github.com/SaikoAS/Warehouse-Studio/issues/12#decision-and-rationale).

## Startup and folder diagnostics

| Problem | Action |
| --- | --- |
| Python is missing or older than 3.13 | Point `WAREHOUSE_STUDIO_PYTHON` at the existing, IT-approved `python.exe` and restart. |
| SQLite is missing or the startup query fails | Ask for an approved Python installation with working standard-library `sqlite3`. |
| Edge is unavailable or fails to start | Open Edge normally and check with IT that the application and its local app windows are permitted. |
| Port 8765 is occupied | Close the previous Warehouse Studio service or [start on a different port](#start-on-a-different-port). |
| Folder path is invalid or inaccessible | Paste the absolute local path from File Explorer. Use a directory outside the application folder that your account can read and write. The launcher identifies a missing directory, a file path, a network folder, and read or write failures separately. |
| The optional Tk dialog fails | Paste the path into **Project folder path** and select **Use folder**. |

Managed PCs can apply application allowlists, restrict `.cmd` files and child processes, disable Edge capabilities, or limit loopback and local filesystem access. Organization-specific rollout checks can use the [ZIP walkthrough](windows-zip.md#verify-the-exact-extracted-candidate) to verify the applicable policies and record the observed behavior.

### Start on a different port

Open Command Prompt in the application folder. Run the following command with the full path to the same approved `python.exe` used by the start script. If you set `WAREHOUSE_STUDIO_PYTHON`, use that executable path. Replace `8766` if that port is also occupied.

```cmd
"C:\Path\To\Approved\python.exe" -I runtime\server.py --port 8766
```

## Future dependencies and packaging

Propose a new runtime dependency in its own reviewed change. Explain the user need, why the approved baseline is insufficient, and how the component affects licensing, supported Windows and Python versions, installation privileges, and offline use. The maintainer approves additions before they become required. Pin the version and record its source, update owner, and any transitive dependencies. Keep optional components isolated and test core behavior when they are unavailable. Preserve loopback and per-project storage isolation.

Build the package from a recorded Git commit with the approved Node line and lockfile. Include the built `dist` assets, the Python `runtime` directory and the Windows start script. Document the tooling versions and candidate archive in the acceptance record. The runtime uses those packaged files and the approved Edge and Python installations. [Issue #8](https://github.com/SaikoAS/Warehouse-Studio/issues/8) records acceptance of the exact extracted candidate.

## Validation in a Windows reference environment

Run `npm run test:edge` against a built tree. The automated tests use a headless Edge profile and allow page requests only to its local test server. For the missing Tk case, the harness blocks the `tkinter` import in the optional picker's Python subprocess. The tests cover the picker fallback, manual selection while the picker response is delayed, project creation, CSV preparation and reopening, and isolation of a second project's database. [CI results for the tested candidate](https://github.com/SaikoAS/Warehouse-Studio/actions/runs/44409560122)

The extracted Windows ZIP passed the reference check on Windows 11 Pro build 26300 with Microsoft Edge 157.0.4341.60 in native app mode, CPython 3.13.14 x64 embeddable and SQLite 3.50.4. The application ran without elevation. The interpreter lacked `tkinter`. PowerShell was outside the application's executable search path. A test-only harness restricted the isolated Edge profile's web requests to loopback, and an external-address probe failed at the local proxy. These observations cover browser-level network isolation and a restricted executable search path.

The native walkthrough verified direct launch, manual path entry, separate project windows, both CSV fixtures, preservation of the last valid result after a failed Apply, reopening after restart, project isolation, and creation, launch and removal of the optional Start menu shortcut. [Completed acceptance record](https://github.com/SaikoAS/Warehouse-Studio/issues/8)
