"""
app.py — Runs your assistant: a tiny local web server + the UI in your browser.

Run it with run.bat (Windows) or:  python app.py
Then open http://127.0.0.1:5000  (it opens by itself).
"""

import os
import socket
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import agent
import tools as T

BASE = Path(__file__).parent
app = Flask(__name__, static_folder=str(BASE / "static"), static_url_path="/static")


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/status")
def status():
    running, models, error = agent.ollama_status()
    facts = T.recall().get("facts", [])
    default = ""
    for preferred in ("qwen2.5:7b", "qwen2.5:3b", "llama3.1:8b", "llama3.2:3b"):
        if preferred in models:
            default = preferred
            break
    if not default and models:
        default = models[0]
    return jsonify({
        "ollama_running": running,
        "models": models,
        "default_model": default,
        "error": error,
        "memory": facts,
        "platform": T.platform.system(),
    })


@app.post("/api/chat")
def chat():
    data = request.get_json(force=True, silent=True) or {}
    messages = data.get("messages") or []
    model = data.get("model") or ""
    allow_dangerous = bool(data.get("allow_dangerous"))

    if not messages:
        return jsonify({"error": "No messages."}), 400
    if not model:
        return jsonify({"error": "No model selected."}), 400

    try:
        result = agent.run_turn(messages, model, allow_dangerous=allow_dangerous)
        return jsonify(result)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "Connection" in msg or "Max retries" in msg or "refused" in msg:
            msg = ("I can't reach Ollama. Make sure the Ollama app is running "
                   "(look for the llama icon in your system tray).")
        return jsonify({"error": msg, "reply": msg, "actions": []}), 200


@app.get("/api/memory")
def get_memory():
    return jsonify({"facts": T.recall().get("facts", [])})


@app.post("/api/memory")
def post_memory():
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")
    if action == "clear":
        T.forget_all()
        return jsonify({"ok": True, "facts": []})
    if action == "add":
        T.remember(data.get("fact", ""))
        return jsonify({"ok": True, "facts": T.recall().get("facts", [])})
    return jsonify({"ok": False, "error": "Unknown action"}), 400


def _free_port(start=5000):
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return start


if __name__ == "__main__":
    host = os.environ.get("JARVIS_HOST", "127.0.0.1")
    port = _free_port(int(os.environ.get("JARVIS_PORT", "5000")))
    running, models, _ = agent.ollama_status()

    print("\n" + "=" * 58)
    print("  JARVIS - your local AI assistant")
    print("=" * 58)
    print(f"  Ollama   : {'connected' if running else 'NOT RUNNING (start the Ollama app!)'}")
    if models:
        print(f"  Models   : {', '.join(models)}")
    print(f"  Open     : http://127.0.0.1:{port}")
    print("  Close this window to stop the assistant.")
    print("=" * 58 + "\n")

    if os.environ.get("JARVIS_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host=host, port=port, threaded=True)
