# Build and verify the Windows ZIP

## Build the candidate

Check out the candidate commit and use Node.js 24.18.1 and Python 3.13 or newer. From the repository root, run these commands.

```cmd
npm ci
npm run typecheck
npm run build
python -m unittest discover -s tests -v
npm run test:edge
python scripts/package_windows.py Warehouse-Studio-v0.1.1-windows.zip
```

Record `git rev-parse HEAD`, the Node and Python versions, and the SHA-256 printed by the packager. The packager writes an explicit runtime file list in sorted order with fixed ZIP timestamps and normalized text line endings. Build again from the same locked inputs and compare SHA-256. The ZIP contains the built interface, the Python runtime scripts, the Windows scripts, quick-start instructions and the applicable license texts. The Windows CI job attaches a copy to the PR workflow run as the **Windows-ZIP** artifact. Download and unpack the Actions artifact to get the candidate ZIP inside it.

## Verify the exact extracted candidate

Use a documented Windows and Edge reference environment for the general offline compatibility check. Before restricting network access for the test, save the candidate ZIP and a local copy of this walkthrough. Record the source commit and verify the SHA-256 of the inner ZIP against the packager output. From the same commit, copy [csv-valid.csv](../tests/fixtures/csv-valid.csv), [csv-invalid-decimal.csv](../tests/fixtures/csv-invalid-decimal.csv) and their [README.md with the expected results](../tests/fixtures/README.md) into a local test folder.

1. Run with standard-user permissions. Record the Windows build and the Edge, Python and SQLite versions. Use Python without `tkinter` and keep PowerShell outside the application's executable search path. Restrict the application's web requests to loopback and record how the restriction was verified. Extract the candidate ZIP into a writable local application folder.
2. Run **Start Warehouse Studio.cmd** and confirm the launcher opens in a native Edge app window. Paste an absolute path from File Explorer into **Project folder path** and select **Use folder**. Create three synthetic projects. Confirm their SQLite files are in the selected local data directory and the projects open in separate Edge windows.
3. Follow the steps in the local fixture README. Import `csv-valid.csv` into the first project and leave the second project open for the isolation check. Import `csv-invalid-decimal.csv` into a third project. Compare the saved rows and the conversion error with the expected results in the README, then check that a failed Apply preserves the previous result. Reopen the projects and check that the saved steps and results load. Confirm the second project and its database are unaffected.
4. Run **Create Warehouse Studio Shortcut.cmd** and stop the running service. Launch the same extracted copy from the current user's Start menu and reopen the saved projects. Run **Remove Warehouse Studio Shortcut.cmd**. Confirm the entry is gone and the direct script and project data still work.
5. Record the automated checks, the native Edge observations and the limits of the test environment. See [Windows compatibility](windows-compatibility.md) for runtime diagnostics. The same walkthrough can be used for organization-specific rollout checks where relevant.

The Start menu scripts operate on the current user's **Warehouse Studio** entry. An entry pointing to a different extracted copy is preserved. Run the removal script from that copy before moving it, or inspect the entry in File Explorer. The shortcut uses the same user environment as the direct launcher to find the approved Python installation.

## v0.1.0 acceptance record

The general offline reference check is complete. The [tested Windows ZIP](https://github.com/SaikoAS/Warehouse-Studio/actions/runs/44409560122/artifacts/14475887933) was built from `678a8957bbef7aa1db52d0061339b7fc19b1cc2e`. Its SHA-256 is `d5cd364a64dfde687d66af9746ab5370591787ca6848767a8db8e98b3a206f6f`. The tested versions, offline setup, and observed results are recorded in [Issue #8](https://github.com/SaikoAS/Warehouse-Studio/issues/8).
