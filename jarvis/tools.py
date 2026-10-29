"""
tools.py — The "hands" of your assistant.

Every function here is something the AI is allowed to DO on your PC.
The AI never runs code directly; it asks for one of these tools by name,
and this file decides whether to allow it and how to run it safely.

Safety notes (read these, they matter):
  * File writes are blocked inside C:\\Windows, Program Files, etc.
  * "Dangerous" tools (shell commands, shutdown, lock) are OFF by default.
    They only become available when you flip the "Allow PC control" switch
    in the app UI. That switch is your permission slip.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"

HOME = Path.home()
JARVIS_DIR = HOME / ".jarvis"
SHOTS_DIR = JARVIS_DIR / "screenshots"
MEMORY_FILE = JARVIS_DIR / "memory.json"

for d in (JARVIS_DIR, SHOTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Folders the assistant is never allowed to write into / delete from
PROTECTED_DIRS = [
    os.environ.get("SystemRoot", r"C:\Windows"),
    os.environ.get("ProgramFiles", r"C:\Program Files"),
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    r"C:\ProgramData",
]

# Path fragments that are never writable, regardless of drive letter / OS
PROTECTED_MARKERS = ("\\windows\\", "/windows/", "\\program files", "/program files",
                     "\\programdata", "/programdata", "/system/", "\\system32")

# Friendly shortcuts -> real command for open_app()
APP_ALIASES = {
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "mspaint": "mspaint",
    "file explorer": "explorer",
    "explorer": "explorer",
    "files": "explorer",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "cmd": "cmd",
    "command prompt": "cmd",
    "terminal": "wt",
    "powershell": "powershell",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "settings": "ms-settings:",
    "control panel": "control",
    "snipping tool": "ms-screenclip:",
    "camera": "microsoft.windows.camera:",
    "spotify": "spotify:",
    "vs code": "code",
    "vscode": "code",
    "code": "code",
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _expand(path: str) -> Path:
    """Turn '~/Desktop/notes.txt' or 'desktop\\notes.txt' into a real Path."""
    if not path:
        return HOME
    p = os.path.expandvars(os.path.expanduser(str(path))).strip().strip('"')
    low = p.lower()
    # let the AI say "desktop/thing.txt" or "documents/..."
    for known in ("desktop", "documents", "downloads", "pictures", "music", "videos"):
        if low == known or low.startswith(known + "\\") or low.startswith(known + "/"):
            rest = p[len(known):].lstrip("\\/")
            folder = HOME / known.capitalize()
            return (folder / rest) if rest else folder
    return Path(p)


def _is_protected(path: Path) -> bool:
    try:
        rp = str(path.resolve()).lower()
    except Exception:
        rp = str(path).lower()
    if any(rp.startswith(p.lower()) for p in PROTECTED_DIRS if p):
        return True
    padded = "\\" + rp.replace("/", "\\")
    return any(marker.replace("/", "\\") in padded for marker in PROTECTED_MARKERS)


def _truncate(text: str, limit: int = 6000) -> str:
    text = str(text)
    if len(text) > limit:
        return text[:limit] + f"\n... [truncated, {len(text)} characters total]"
    return text


def _run(cmd: str, timeout: int = 60):
    try:
        p = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        return -1, "", "Timed out."
    except Exception as e:  # noqa: BLE001
        return -1, "", str(e)


# --------------------------------------------------------------------------
# 1. Apps, websites, windows
# --------------------------------------------------------------------------
def open_app(name: str) -> dict:
    """Launch an application by friendly name."""
    if not IS_WINDOWS:
        return {"ok": False, "error": "PC control tools only work on Windows."}
    key = (name or "").strip().lower()
    target = APP_ALIASES.get(key, name.strip())

    if target.startswith(("ms-settings:", "ms-screenclip:", "microsoft.", "spotify:")):
        try:
            os.startfile(target)  # type: ignore[attr-defined]
            return {"ok": True, "message": f"Opened {name}."}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"Could not open {name}: {e}"}

    try:
        subprocess.Popen(f'start "" "{target}"', shell=True)
        return {"ok": True, "message": f"Opened {name}."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Could not open {name}: {e}"}


def open_url(url: str) -> dict:
    """Open a website in the default browser."""
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "No URL given."}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        if IS_WINDOWS:
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            import webbrowser
            webbrowser.open(url)
        return {"ok": True, "message": f"Opened {url} in the browser."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def web_search(query: str) -> dict:
    """Search the web (opens a Google/Bing search in the browser)."""
    from urllib.parse import quote_plus
    url = "https://www.google.com/search?q=" + quote_plus(query or "")
    return open_url(url)


# --------------------------------------------------------------------------
# 2. Files and folders
# --------------------------------------------------------------------------
def list_files(path: str = "~") -> dict:
    """List the contents of a folder."""
    p = _expand(path)
    if not p.exists():
        return {"ok": False, "error": f"Folder not found: {p}"}
    if not p.is_dir():
        return {"ok": False, "error": f"Not a folder: {p}"}
    items = []
    try:
        for entry in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))[:80]:
            try:
                size = entry.stat().st_size if entry.is_file() else 0
            except OSError:
                size = 0
            items.append({
                "name": entry.name,
                "type": "folder" if entry.is_dir() else "file",
                "size_kb": round(size / 1024, 1),
            })
    except PermissionError:
        return {"ok": False, "error": f"Permission denied: {p}"}
    return {"ok": True, "path": str(p), "count": len(items), "items": items}


def read_file(path: str) -> dict:
    """Read a text file."""
    p = _expand(path)
    if not p.exists():
        return {"ok": False, "error": f"File not found: {p}"}
    if p.is_dir():
        return {"ok": False, "error": f"{p} is a folder, not a file."}
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    return {"ok": True, "path": str(p), "content": _truncate(content)}


def write_file(path: str, content: str, mode: str = "overwrite") -> dict:
    """Create or modify a text file. mode: 'overwrite' or 'append'."""
    p = _expand(path)
    if _is_protected(p):
        return {"ok": False, "error": "That folder is protected. Pick a normal folder instead."}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append" and p.exists():
            with p.open("a", encoding="utf-8") as f:
                f.write(content)
        else:
            p.write_text(content, encoding="utf-8")
        return {"ok": True, "message": f"Saved {p} ({len(content)} characters).", "path": str(p)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def make_folder(path: str) -> dict:
    """Create a new folder (and parents)."""
    p = _expand(path)
    if _is_protected(p):
        return {"ok": False, "error": "That location is protected."}
    try:
        p.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "message": f"Created folder {p}."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def copy_folder(source: str, destination: str, overwrite: bool = False) -> dict:
    """
    Copy a folder (with everything inside it) to a new location.

    source      : the folder to copy, e.g. 'desktop/photos' or 'C:\\Users\\Me\\Projects\\app'
    destination : where it should go. Either the full new folder path
                  ('desktop/photos backup') or an existing folder to copy into.
    overwrite   : False by default — refuses to touch an existing destination.
    """
    src = _expand(source)
    dst = _expand(destination)

    if _is_protected(src):
        return {"ok": False, "error": f"{src} is in a protected system folder, so I will not copy it."}
    if not src.exists():
        return {"ok": False, "error": f"I could not find {src}."}
    if not src.is_dir():
        return {"ok": False, "error": f"{src} is a file, not a folder. I can still copy it if you want."}

    # If the destination already exists as a folder, copy INSIDE it (like Windows paste)
    if dst.exists() and dst.is_dir():
        dst = dst / src.name

    if _is_protected(dst):
        return {"ok": False, "error": "That destination is a protected system folder. Pick a normal folder."}
    if dst.exists() and not overwrite:
        return {"ok": False,
                "error": f"{dst} already exists. Say 'overwrite' if you really want to replace it."}

    # Refuse to copy a folder into itself (would loop forever)
    try:
        s_res, d_res = src.resolve(), dst.resolve()
        if str(d_res).lower().startswith(str(s_res).lower()):
            return {"ok": False, "error": "I can't copy a folder into itself. Choose a different destination."}
    except Exception:  # noqa: BLE001
        pass

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if sys.version_info >= (3, 8):
            shutil.copytree(src, dst, dirs_exist_ok=overwrite)
        else:
            shutil.copytree(src, dst)
    except PermissionError:
        return {"ok": False, "error": f"Permission denied. Close any program using {src} and try again."}
    except shutil.Error as e:
        return {"ok": False, "error": f"Some files could not be copied: {str(e)[:400]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    files = sum(len(f) for _, _, f in os.walk(dst))
    size = 0
    for dirpath, _, filenames in os.walk(dst):
        for f in filenames:
            try:
                size += (Path(dirpath) / f).stat().st_size
            except OSError:
                pass
    return {
        "ok": True,
        "message": f"Copied {src.name} to {dst} ({files} files, {round(size / 1048576, 1)} MB).",
        "source": str(src),
        "destination": str(dst),
        "files_copied": files,
        "size_mb": round(size / 1048576, 1),
    }


def move_folder(source: str, destination: str, overwrite: bool = False) -> dict:
    """Move (cut + paste) a folder to a new location. Same rules as copy_folder."""
    src = _expand(source)
    dst = _expand(destination)

    if _is_protected(src) or _is_protected(dst):
        return {"ok": False, "error": "That path is a protected system folder."}
    if not src.exists():
        return {"ok": False, "error": f"I could not find {src}."}
    if dst.exists() and dst.is_dir():
        dst = dst / src.name
    if dst.exists() and not overwrite:
        return {"ok": False, "error": f"{dst} already exists. Say 'overwrite' to replace it."}
    try:
        src_res, dst_res = src.resolve(), dst.resolve()
        if str(dst_res).lower().startswith(str(src_res).lower()):
            return {"ok": False, "error": "I can't move a folder inside itself."}
    except Exception:  # noqa: BLE001
        pass

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and overwrite:
            shutil.rmtree(dst, ignore_errors=True)
        shutil.move(str(src), str(dst))
        return {"ok": True, "message": f"Moved {src.name} to {dst}.", "destination": str(dst)}
    except PermissionError:
        return {"ok": False, "error": "Permission denied. A program may be using those files."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def copy_file(source: str, destination: str, overwrite: bool = False) -> dict:
    """Copy a single file (destination can be a full path or an existing folder)."""
    src = _expand(source)
    dst = _expand(destination)
    if not src.exists():
        return {"ok": False, "error": f"I could not find {src}."}
    if src.is_dir():
        return {"ok": False, "error": f"{src} is a folder — I'll use the copy_folder tool for that."}
    if dst.exists() and dst.is_dir():
        dst = dst / src.name
    if _is_protected(dst):
        return {"ok": False, "error": "That destination is protected."}
    if dst.exists() and not overwrite:
        return {"ok": False, "error": f"{dst} already exists. Say 'overwrite' to replace it."}
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return {"ok": True, "message": f"Copied {src.name} to {dst}."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def search_files(name: str, root: str = "~") -> dict:
    """Find files whose name contains `name`, starting from `root`."""
    base = _expand(root)
    needle = (name or "").lower()
    hits = []
    try:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in
                           ("AppData", "node_modules", ".git", "Windows", "__pycache__")]
            for f in filenames:
                if needle in f.lower():
                    full = Path(dirpath) / f
                    hits.append(str(full))
                    if len(hits) >= 40:
                        raise StopIteration
    except StopIteration:
        pass
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    return {"ok": True, "count": len(hits), "results": hits}


# --------------------------------------------------------------------------
# 3. Screen, keyboard, sound
# --------------------------------------------------------------------------
def screenshot(save_path: str = "") -> dict:
    """Take a screenshot and save it to a file."""
    out = _expand(save_path) if save_path else (
        SHOTS_DIR / f"shot_{datetime.now():%Y%m%d_%H%M%S}.png"
    )
    try:
        try:
            import pyautogui  # preferred
            img = pyautogui.screenshot()
            img.save(out)
        except Exception:
            from PIL import ImageGrab  # Windows fallback
            ImageGrab.grab().save(out)
        return {"ok": True, "message": f"Screenshot saved to {out}", "path": str(out)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Screenshot failed (pip install pillow pyautogui): {e}"}


def type_text(text: str) -> dict:
    """Type text at the current cursor position (types into the focused window)."""
    try:
        import pyautogui
        pyautogui.write(text, interval=0.01)
        return {"ok": True, "message": "Typed the text."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Typing failed (pip install pyautogui): {e}"}


def press_keys(keys: str) -> dict:
    """Press a key or shortcut, e.g. 'enter', 'ctrl+s', 'alt+tab', 'win+d'."""
    try:
        import pyautogui
        combo = [k.strip() for k in keys.replace("+", " ").split() if k.strip()]
        pyautogui.hotkey(*combo) if len(combo) > 1 else pyautogui.press(combo[0])
        return {"ok": True, "message": f"Pressed {keys}."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Key press failed (pip install pyautogui): {e}"}


def volume(action: str = "up", steps: int = 4) -> dict:
    """Change system volume: 'up', 'down', 'mute'."""
    try:
        import pyautogui
        key = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}.get(
            (action or "up").lower(), "volumeup"
        )
        for _ in range(max(1, min(int(steps), 15))):
            pyautogui.press(key)
        return {"ok": True, "message": f"Volume {action}."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Volume control failed (pip install pyautogui): {e}"}


def media(action: str = "playpause") -> dict:
    """Control media playback: playpause, next, prev."""
    try:
        import pyautogui
        key = {"playpause": "playpause", "play": "playpause", "pause": "playpause",
               "next": "nexttrack", "prev": "prevtrack", "previous": "prevtrack"}.get(
            (action or "playpause").lower(), "playpause"
        )
        pyautogui.press(key)
        return {"ok": True, "message": f"Media: {action}."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Media control failed: {e}"}


def clipboard_read() -> dict:
    """Read what is currently copied to the clipboard."""
    try:
        import pyperclip
        return {"ok": True, "text": _truncate(pyperclip.paste() or "")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Clipboard read failed (pip install pyperclip): {e}"}


def clipboard_write(text: str) -> dict:
    """Copy text to the clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return {"ok": True, "message": "Copied to clipboard."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Clipboard write failed (pip install pyperclip): {e}"}


# --------------------------------------------------------------------------
# 4. System information & power (power = dangerous)
# --------------------------------------------------------------------------
def system_info() -> dict:
    """Get CPU, RAM, disk, battery and uptime info for this PC."""
    info = {"os": f"{platform.system()} {platform.release()}", "machine": platform.machine(),
            "user": os.environ.get("USERNAME") or os.environ.get("USER", ""),
            "home": str(HOME)}
    try:
        import psutil
        vm = psutil.virtual_memory()
        du = psutil.disk_usage(str(HOME.anchor or "/"))
        info.update({
            "cpu_percent": psutil.cpu_percent(interval=0.4),
            "cpu_cores": psutil.cpu_count(logical=True),
            "ram_total_gb": round(vm.total / 1e9, 1),
            "ram_used_percent": vm.percent,
            "disk_total_gb": round(du.total / 1e9, 1),
            "disk_used_percent": du.percent,
            "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
        })
        bat = psutil.sensors_battery()
        if bat:
            info["battery_percent"] = round(bat.percent)
            info["battery_plugged_in"] = bat.power_plugged
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "info": info}


def get_datetime() -> dict:
    """Current local date and time."""
    now = datetime.now()
    return {"ok": True, "datetime": now.strftime("%A, %d %B %Y, %I:%M %p"),
            "date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M")}


def lock_pc() -> dict:
    """Lock the PC. (dangerous — needs PC control enabled)"""
    if not IS_WINDOWS:
        return {"ok": False, "error": "Windows only."}
    code, _, err = _run("rundll32.exe user32.dll,LockWorkStation")
    return {"ok": code == 0, "message": "PC locked."} if code == 0 else {"ok": False, "error": err}


def shutdown_pc(minutes: int = 0) -> dict:
    """Shut down the PC, optionally after N minutes. (dangerous)"""
    if not IS_WINDOWS:
        return {"ok": False, "error": "Windows only."}
    minutes = max(0, int(minutes or 0))
    cmd = "shutdown /s /t 0" if minutes == 0 else f"shutdown /s /t {minutes * 60}"
    code, _, err = _run(cmd)
    return {"ok": code == 0, "message": f"Shutting down in {minutes} minute(s)."} if code == 0 \
        else {"ok": False, "error": err}


def restart_pc(minutes: int = 0) -> dict:
    """Restart the PC, optionally after N minutes. (dangerous)"""
    if not IS_WINDOWS:
        return {"ok": False, "error": "Windows only."}
    minutes = max(0, int(minutes or 0))
    cmd = "shutdown /r /t 0" if minutes == 0 else f"shutdown /r /t {minutes * 60}"
    code, _, err = _run(cmd)
    return {"ok": code == 0, "message": f"Restarting in {minutes} minute(s)."} if code == 0 \
        else {"ok": False, "error": err}


def run_command(command: str) -> dict:
    """Run a Windows shell command and return its output. (dangerous)"""
    if not command:
        return {"ok": False, "error": "No command given."}
    code, out, err = _run(command, timeout=90)
    return {"ok": code == 0, "exit_code": code,
            "output": _truncate(out) or "(no output)",
            "error": _truncate(err) if err else ""}


# --------------------------------------------------------------------------
# 5. Memory (things the assistant should not forget between sessions)
# --------------------------------------------------------------------------
def _load_memory() -> list:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return []
    return []


def remember(fact: str) -> dict:
    """Store a fact about the user for future conversations."""
    facts = _load_memory()
    fact = (fact or "").strip()
    if not fact:
        return {"ok": False, "error": "Nothing to remember."}
    if fact not in facts:
        facts.append(fact)
        MEMORY_FILE.write_text(json.dumps(facts[-200:], indent=2, ensure_ascii=False),
                               encoding="utf-8")
    return {"ok": True, "message": f"Remembered: {fact}"}


def recall() -> dict:
    """List everything stored in memory."""
    return {"ok": True, "facts": _load_memory()}


def forget_all() -> dict:
    """Wipe the assistant's memory."""
    MEMORY_FILE.write_text("[]", encoding="utf-8")
    return {"ok": True, "message": "Memory cleared."}


# --------------------------------------------------------------------------
# Registry: name -> python function
# --------------------------------------------------------------------------
SAFE_TOOLS = {
    "open_app": open_app,
    "open_url": open_url,
    "web_search": web_search,
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "make_folder": make_folder,
    "copy_folder": copy_folder,
    "move_folder": move_folder,
    "copy_file": copy_file,
    "search_files": search_files,
    "screenshot": screenshot,
    "type_text": type_text,
    "press_keys": press_keys,
    "volume": volume,
    "media": media,
    "clipboard_read": clipboard_read,
    "clipboard_write": clipboard_write,
    "system_info": system_info,
    "get_datetime": get_datetime,
    "remember": remember,
    "recall": recall,
}

DANGEROUS_TOOLS = {
    "run_command": run_command,
    "lock_pc": lock_pc,
    "shutdown_pc": shutdown_pc,
    "restart_pc": restart_pc,
}


def available_tools(allow_dangerous: bool) -> dict:
    tools = dict(SAFE_TOOLS)
    if allow_dangerous:
        tools.update(DANGEROUS_TOOLS)
    return tools


def execute(name: str, arguments: dict, allow_dangerous: bool = False) -> dict:
    """Run one tool call requested by the model. Never raises."""
    fn = available_tools(allow_dangerous).get(name)
    if fn is None:
        return {"ok": False, "error": f"Tool '{name}' is not available or not permitted."}
    try:
        return fn(**(arguments or {}))
    except TypeError as e:
        return {"ok": False, "error": f"Bad arguments for {name}: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
