"""Run Tk's native folder picker on its own main thread and return a JSON path."""

import json
import sys


def main():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.title("Warehouse Studio folder picker")
    root.geometry("1x1")
    try:
        root.attributes("-topmost", True)
        root.update()
        path = filedialog.askdirectory(parent=root, title="Choose a Warehouse Studio data folder", mustexist=True)
        print(json.dumps(path or None))
    finally:
        root.destroy()


if __name__ == "__main__":
    try:
        main()
    except (ImportError, RuntimeError) as error:
        sys.exit(f"The folder picker needs Python with Tk support: {error}")
