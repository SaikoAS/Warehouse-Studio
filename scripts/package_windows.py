"""Package the built Warehouse Studio runtime as a reproducible Windows ZIP."""

import argparse
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "Create Warehouse Studio Shortcut.cmd": "Create Warehouse Studio Shortcut.cmd",
    "LICENSE": "LICENSE",
    "README.txt": "docs/windows-quickstart.txt",
    "Remove Warehouse Studio Shortcut.cmd": "Remove Warehouse Studio Shortcut.cmd",
    "Start Warehouse Studio.cmd": "Start Warehouse Studio.cmd",
    "dist/assets/index.css": "dist/assets/index.css",
    "dist/assets/studio.js": "dist/assets/studio.js",
    "dist/index.html": "dist/index.html",
    "licenses/react-dom.txt": "node_modules/react-dom/LICENSE",
    "licenses/react.txt": "node_modules/react/LICENSE",
    "licenses/scheduler.txt": "node_modules/scheduler/LICENSE",
    "runtime/choose_folder.py": "runtime/choose_folder.py",
    "runtime/preparation.py": "runtime/preparation.py",
    "runtime/projects.py": "runtime/projects.py",
    "runtime/server.py": "runtime/server.py",
    "runtime/shortcuts.py": "runtime/shortcuts.py",
}


def build_zip(destination, root=ROOT):
    if destination.suffix.lower() != ".zip":
        raise ValueError("Choose a destination with a .zip extension.")
    inputs = {}
    for name, source in FILES.items():
        try:
            content = (root / source).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ValueError(f"Cannot read {source}. Check out the package files, run npm ci, and build the frontend.") from error
        if name.endswith((".cmd", ".txt")):
            content = content.replace("\n", "\r\n")
        inputs[name] = content.encode("utf-8")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as scratch:
        temporary = Path(scratch.name)
    try:
        with ZipFile(temporary, "w") as archive:
            for name in sorted(inputs):
                entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 0
                archive.writestr(entry, inputs[name])
        digest = sha256(temporary.read_bytes()).hexdigest()
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="destination ZIP file")
    args = parser.parse_args()
    try:
        digest = build_zip(args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Windows ZIP: {error}\n")
    print(f"SHA256 {digest}  {args.output}")


if __name__ == "__main__":
    main()
