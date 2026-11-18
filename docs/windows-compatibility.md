# Windows compatibility for v0.1.0

## Runtime and build requirements

| Component | Role | Requirement |
| --- | --- | --- |
| Windows and Command Processor | Runtime | The approved Windows installation must allow the user to run **Start Warehouse Studio.cmd** in the extracted application folder. |
| Approved Python 3.13 or newer with standard-library `sqlite3` | Runtime | Start the local Python service and use one SQLite file per project. The startup check opens an in-memory SQLite database and runs a query. |
| Microsoft Edge | Runtime | Open the launcher and project windows on IPv4 loopback. The browser's regular file dialog selects individual CSV files. |
| Local writable folder and loopback port | Runtime | Store projects in a user-writable local folder outside the application folder. The default service address is `127.0.0.1:8765`. |
| Tcl/Tk and Python `tkinter` | Optional | **Browse (optional)** uses the folder picker. **Project folder path** is the standard selection method and works if the picker fails or is unavailable. |
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

Managed PCs can apply application allowlists, restrict `.cmd` files and child processes, disable Edge capabilities, or limit loopback and local filesystem access. The application can report failures it observes. A successful process launch alone cannot confirm whether policy allows the resulting Edge app window or whether a particular managed profile can complete the workflow. Record the effective restrictions when testing the target setup.

### Start on a different port

Open Command Prompt in the application folder. Run the following command with the full path to the same approved `python.exe` used by the start script. If you set `WAREHOUSE_STUDIO_PYTHON`, use that executable path. Replace `8766` if that port is also occupied.

```cmd
"C:\Path\To\Approved\python.exe" -I runtime\server.py --port 8766
```

## Future dependencies and packaging

Propose a new runtime dependency in its own reviewed change. Explain the user need, why the approved baseline is insufficient, and how the component affects licensing, supported Windows and Python versions, installation privileges, and offline use. The maintainer approves additions before they become required. Pin the version and record its source, update owner, and any transitive dependencies. Keep optional components isolated and test core behavior when they are unavailable. Preserve loopback and per-project storage isolation.

Build the package from a recorded Git commit with the approved Node line and lockfile. Include the built `dist` assets, the Python `runtime` directory and the Windows start script. Document the tooling versions and candidate archive in the acceptance record. The runtime uses those packaged files and the approved Edge and Python installations. [Issue #8](https://github.com/SaikoAS/Warehouse-Studio/issues/8) tracks ZIP creation and acceptance from the exact extracted candidate.

## Validation and remaining acceptance

Run `npm run test:edge` against a built tree. The test uses a separate headless Edge profile and allows page requests only to its local test server. The test harness runs the real optional picker script with the `tkinter` import blocked in that Python child process. It supplies project URLs to the test browser and permits only the Python picker as a runtime helper process. This exercises the failed picker, quoted path entry, listing, project creation, saved CSV results after reopening, and preservation of a second project's database.

The #12 implementation passed this regression on Windows 11 Pro build 26300 with Python 3.13.14, SQLite 3.50.4 and Edge 157.0.4341.60. The local run used a non-elevated process. It simulated the missing optional component and restricted subprocesses in the test harness.

For managed-PC acceptance, run the exact extracted ZIP as a standard user with the network disconnected, a Python installation without Tk, and PowerShell unavailable or blocked by the target policy. Start it from the Windows script, paste a local folder path from File Explorer, list existing projects, and create and reopen a project in Edge. Check the location of its SQLite file. Import the synthetic CSV, apply steps and reopen the saved result while another project window stays open. Record the Windows, Python, SQLite and Edge versions, the way Tk and PowerShell were unavailable, and the observed results in #8.
