"""
Launch Jarvis.pyw - double-click this to start the assistant.

Why a .pyw?  Windows runs it with pythonw.exe, so there is no console window
and nothing that antivirus tends to flag (unlike a .bat file).
It simply starts app.py, which opens your browser.

If something goes wrong, a file called jarvis-error.log appears next to this
file - send me its contents.
"""

import os
import runpy
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE))

LOG = HERE / "jarvis-error.log"


def fail(message: str):
    """Show the error in a pop-up (falling back to the log file)."""
    try:
        LOG.write_text(message, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Jarvis could not start", message[:1500])
        root.destroy()
    except Exception:  # noqa: BLE001
        print(message)


def main():
    # 1. Are we in a complete copy of the folder?
    missing = [f for f in ("app.py", "agent.py", "tools.py", "static") if not (HERE / f).exists()]
    if missing:
        fail(
            "Some files are missing from this folder:\n  "
            + "\n  ".join(missing)
            + "\n\nThis usually means the zip was run without extracting it first.\n"
            "Right-click the zip -> 'Extract All...' and use the extracted folder."
        )
        return

    # 2. Are the Python packages installed?
    try:
        import flask  # noqa: F401
        import requests  # noqa: F401
    except ImportError as e:
        fail(
            f"A required Python package is missing ({e.name}).\n\n"
            "Open a Command Prompt in this folder and run:\n\n"
            "    pip install -r requirements.txt\n\n"
            "Then double-click this file again."
        )
        return

    # 3. Hand over to the real app
    try:
        runpy.run_path(str(HERE / "app.py"), run_name="__main__")
    except SystemExit:
        pass
    except Exception:  # noqa: BLE001
        fail("Jarvis crashed while starting:\n\n" + traceback.format_exc())


if __name__ == "__main__":
    main()
