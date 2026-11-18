# Build and verify the Windows ZIP

## Build the candidate

Check out the candidate commit and use Node.js 24.18.1 and Python 3.13 or newer. From the repository root, run these commands.

```cmd
npm ci
npm run typecheck
npm run build
python -m unittest discover -s tests -v
npm run test:edge
python scripts/package_windows.py Warehouse-Studio-v0.1.0-windows.zip
```

Record `git rev-parse HEAD`, the Node and Python versions, and the SHA-256 printed by the packager. The packager writes an explicit runtime file list in sorted order with fixed ZIP timestamps and normalized text line endings. Build again from the same locked inputs and compare SHA-256. The ZIP contains the built interface, the Python runtime scripts, the Windows scripts, quick-start instructions and the applicable license texts. The Windows CI job attaches a copy to the PR workflow run as the **Windows-ZIP** artifact. Download and unpack the Actions artifact to get the candidate ZIP inside it.

## Verify the exact extracted candidate

1. On the intended managed Windows device, sign in as a standard user. Record the Windows build, Edge version, approved Python and SQLite versions, Tk availability, and the applied PowerShell restriction. Disconnect the network. Extract the candidate ZIP into a writable local application folder.
2. Double-click **Start Warehouse Studio.cmd** and confirm the launcher opens in an Edge app window. Paste an absolute path from File Explorer into **Project folder path**. List existing projects and create two synthetic projects. Confirm both SQLite files are in the selected local data directory and the application opens two separate Edge windows.
3. Use the valid [synthetic CSV](../tests/fixtures/README.md) in the first project and leave the second project open for the isolation check. Use a third project for the invalid fixture. Check the valid result, the expected conversion error and retention of the previous result after a failed Apply. Reopen the projects and check that the saved steps and results load. Confirm the second project and its database are unaffected.
4. Run **Create Warehouse Studio Shortcut.cmd** and launch the same extracted copy from the current user's Start menu. Then run **Remove Warehouse Studio Shortcut.cmd**. Confirm the entry is gone and the direct script and project data still work. Repeat the project flow with Tk unavailable and PowerShell unavailable or blocked by the target policy.
5. Record observed results, any substitutions or simulated restrictions, and the remaining acceptance steps in the PR or [Issue #8](https://github.com/SaikoAS/Warehouse-Studio/issues/8). Keep automated results and native device observations distinct. See [Windows compatibility](windows-compatibility.md) for runtime diagnostics.

The Start menu scripts operate on the current user's **Warehouse Studio** entry. An entry pointing to a different extracted copy is preserved. Run the removal script from that copy before moving it, or inspect the entry in File Explorer. The shortcut uses the same user environment as the direct launcher to find the approved Python installation.
