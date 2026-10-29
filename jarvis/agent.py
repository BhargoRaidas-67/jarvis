"""
agent.py — The "brain" of your assistant.

This talks to a local Ollama server, gives the model a list of tools it may
use, runs whatever it asks for, feeds the results back, and loops until the
model produces a final spoken/written answer.
"""

import json
import os
import platform
import re

import requests

import tools as T

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL

# Bigger context = the model keeps its footing for longer. qwen2.5 supports 32k;
# 16k is a safe middle ground for an 8 GB machine.
NUM_CTX = int(os.environ.get("JARVIS_NUM_CTX", "16384"))

# How much conversation to replay to the model. Long histories are the main reason a
# small model starts parroting the user instead of answering.
MAX_TURNS = int(os.environ.get("JARVIS_MAX_TURNS", "6"))
MAX_MSG_CHARS = 1200          # per replayed message
MAX_TOOL_RESULT_CHARS = 1500  # tool output fed back into the context


# --------------------------------------------------------------------------
# Tool descriptions handed to the model (JSON-schema "function calling")
# --------------------------------------------------------------------------
def _fn(name, desc, props=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props or {},
                "required": required or [],
            },
        },
    }


SAFE_SCHEMAS = [
    _fn("open_app", "Launch an application on the PC by name (e.g. 'chrome', 'notepad', 'calculator', 'spotify', 'vs code').",
        {"name": {"type": "string", "description": "Application name"}}, ["name"]),
    _fn("open_url", "Open a website in the default browser.",
        {"url": {"type": "string", "description": "URL to open"}}, ["url"]),
    _fn("web_search", "Open a web search for a query in the browser (use when the user wants you to search something online).",
        {"query": {"type": "string", "description": "Search terms"}}, ["query"]),
    _fn("list_files", "List files and folders inside a directory.",
        {"path": {"type": "string", "description": "Folder path or shortcuts like 'desktop', 'downloads', 'documents'. Default is the home folder."}},
        ["path"]),
    _fn("read_file", "Read the text contents of a file.",
        {"path": {"type": "string", "description": "File path"}}, ["path"]),
    _fn("write_file", "Create or update a text file with the given content.",
        {"path": {"type": "string", "description": "File path, e.g. 'desktop/notes.txt'"},
         "content": {"type": "string", "description": "Text to write"},
         "mode": {"type": "string", "enum": ["overwrite", "append"], "description": "Default overwrite"}},
        ["path", "content"]),
    _fn("make_folder", "Create a new folder.",
        {"path": {"type": "string", "description": "Folder path to create"}}, ["path"]),
    _fn("copy_folder", "Copy a folder and everything inside it to another location. "
        "Use when the user says copy, duplicate, or back up a folder.",
        {"source": {"type": "string", "description": "Folder to copy, e.g. 'desktop/photos'"},
         "destination": {"type": "string", "description": "New folder path, or an existing folder to copy into"},
         "overwrite": {"type": "boolean", "description": "Set true only if the user clearly agreed to replace an existing folder"}},
        ["source", "destination"]),
    _fn("move_folder", "Move a folder to a new location (cut and paste). Use for move or relocate.",
        {"source": {"type": "string", "description": "Folder to move"},
         "destination": {"type": "string", "description": "Where it should go"},
         "overwrite": {"type": "boolean", "description": "Set true only if the user agreed to replace an existing folder"}},
        ["source", "destination"]),
    _fn("copy_file", "Copy a single file to another location.",
        {"source": {"type": "string", "description": "File to copy"},
         "destination": {"type": "string", "description": "New path, or an existing folder to copy into"},
         "overwrite": {"type": "boolean", "description": "Set true only if the user agreed to replace an existing file"}},
        ["source", "destination"]),
    _fn("search_files", "Search for files by name across the disk (starting from a root folder).",
        {"name": {"type": "string", "description": "Part of the file name"},
         "root": {"type": "string", "description": "Where to start searching, default home folder"}},
        ["name"]),
    _fn("screenshot", "Capture the screen and save it as an image file.",
        {"save_path": {"type": "string", "description": "Optional path to save to"}}, []),
    _fn("type_text", "Type text into whatever window currently has focus. Only use when the user explicitly asks you to type something for them.",
        {"text": {"type": "string", "description": "Text to type"}}, ["text"]),
    _fn("press_keys", "Press a key or keyboard shortcut, e.g. 'enter', 'ctrl+s', 'alt+tab', 'win+d'.",
        {"keys": {"type": "string", "description": "Key or combo"}}, ["keys"]),
    _fn("volume", "Change the system volume.",
        {"action": {"type": "string", "enum": ["up", "down", "mute"], "description": "What to do"},
         "steps": {"type": "integer", "description": "How many steps (default 4)"}}, ["action"]),
    _fn("media", "Control music/video playback: playpause, next, prev.",
        {"action": {"type": "string", "enum": ["playpause", "next", "prev"], "description": "Playback action"}}, ["action"]),
    _fn("clipboard_read", "Read the current clipboard contents.", {}, []),
    _fn("clipboard_write", "Copy text to the clipboard.",
        {"text": {"type": "string", "description": "Text to copy"}}, ["text"]),
    _fn("system_info", "Get CPU, RAM, disk, battery and uptime information about this PC.", {}, []),
    _fn("get_datetime", "Get the current local date and time.", {}, []),
    _fn("remember", "Save a lasting fact about the user (name, preferences, projects) to long-term memory.",
        {"fact": {"type": "string", "description": "Short factual sentence"}}, ["fact"]),
    _fn("recall", "Read back everything saved in long-term memory.", {}, []),
]

DANGEROUS_SCHEMAS = [
    _fn("run_command", "Run a Windows shell command and return its output. Use only when the user clearly asked for it.",
        {"command": {"type": "string", "description": "Command to execute"}}, ["command"]),
    _fn("lock_pc", "Lock the Windows session.", {}, []),
    _fn("shutdown_pc", "Shut down the PC, optionally after N minutes.",
        {"minutes": {"type": "integer", "description": "Delay in minutes, default 0"}}, []),
    _fn("restart_pc", "Restart the PC, optionally after N minutes.",
        {"minutes": {"type": "integer", "description": "Delay in minutes, default 0"}}, []),
]


def tool_schemas(allow_dangerous: bool) -> list:
    return SAFE_SCHEMAS + (DANGEROUS_SCHEMAS if allow_dangerous else [])


# --------------------------------------------------------------------------
# System prompt
# --------------------------------------------------------------------------
def system_prompt(allow_dangerous: bool) -> str:
    facts = T.recall().get("facts", [])
    memory_block = ("\nThings you already know about the user:\n- " + "\n- ".join(facts)) if facts else ""
    control = (
        "PC control is ON: you may run shell commands, lock, restart and shut down the PC."
        if allow_dangerous else
        "PC control is OFF: shell commands, locking, shutdown and restart are unavailable. "
        "If the user asks for one of those, tell them to switch on 'Allow PC control' in the app."
    )
    return f"""You are Jarvis, a personal AI assistant living on the user's Windows PC.
Today is {{today}}. The machine runs {platform.system()} and the user's home folder is {T.HOME}.

Personality:
- Warm, quick and competent. Talk like a smart friend, not a corporate chatbot.
- Keep answers short and natural: 1-3 sentences unless the user asks for detail or you are writing something for them.
- Never mention tool names, JSON or internal mechanics. Just say what you did ("Done — Chrome is open").

How to behave:
- Use your tools to actually DO things instead of telling the user to do them.
- If a request is ambiguous, make the most reasonable assumption and act, or ask one short question.
- Do the smallest number of tool calls needed. Never repeat a tool call that already succeeded.
- Never invent results. If a tool failed, say what went wrong in plain words.
- Do not use emojis in spoken replies. Keep numbers and times exact.

{control}{memory_block}"""


# --------------------------------------------------------------------------
# Ollama plumbing
# --------------------------------------------------------------------------
def ollama_status():
    """Return (is_running, models, error)."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return True, models, None
    except Exception as e:  # noqa: BLE001
        return False, [], str(e)


def _ollama_chat(model: str, messages: list, schemas: list, temperature: float = 0.4) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": NUM_CTX},
    }
    if schemas:
        payload["tools"] = schemas
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"Ollama returned {r.status_code}: {r.text[:300]}")
    return r.json().get("message", {})


def _normalise_tool_calls(msg: dict) -> list:
    """Ollama returns arguments as a dict, but some versions send a JSON string."""
    calls = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {}) if isinstance(tc, dict) else {}
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:  # noqa: BLE001
                args = {}
        calls.append({"name": fn.get("name", ""), "arguments": args or {}})
    return calls


def _clean_history(convo: list) -> list:
    """Keep only real dialogue turns — no empty tool-request placeholders."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in convo
        if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()
    ]


def _trim_history(history: list) -> list:
    """
    Send only the recent past to the model. A 3B model that is handed too much
    history — especially old tool output — stops reasoning and just echoes.
    """
    clean = [m for m in history if m.get("role") in ("user", "assistant")]
    # keep only the last MAX_TURNS messages, always starting with a user message
    recent = clean[-MAX_TURNS * 2:]
    while recent and recent[0].get("role") != "user":
        recent.pop(0)
    out = []
    for m in recent:
        content = (m.get("content") or "")[:MAX_MSG_CHARS]
        out.append({"role": m["role"], "content": content})
    return out


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", (text or "").lower()).strip()


def _looks_degenerate(reply: str, user_text: str) -> bool:
    """
    Catch the failure the user hit: the model hands back the user's own sentence
    (or an empty/stub answer) instead of doing the work.
    """
    r, u = _normalise(reply), _normalise(user_text)
    if not r or len(r) < 2:
        return True
    if r == u:
        return True
    # one is a near-copy of the other
    if u and (r in u or u in r) and abs(len(r) - len(u)) < 12:
        return True
    # a single word repeated many times
    words = r.split()
    if len(words) > 6 and len(set(words)) <= max(2, len(words) // 4):
        return True
    return False


def _force_answer(model: str, convo: list, user_text: str) -> str:
    """
    Last resort: ask once more with tools switched off and a blunt instruction,
    so the model has to produce prose rather than more tool chatter.
    """
    nudge = list(convo) + [{
        "role": "user",
        "content": ("Answer the user directly in one or two sentences. Do not repeat their "
                    "sentence back. If you already did what they asked, say what you did."),
    }]
    try:
        msg = _ollama_chat(model, nudge, [], temperature=0.2)
        text = (msg.get("content") or "").strip()
        if text and not _looks_degenerate(text, user_text):
            return text
    except Exception:  # noqa: BLE001
        pass
    return ("My thoughts got tangled on that one — the model lost track. "
            "Try asking again in a shorter sentence, or run \"ollama pull qwen2.5:7b\" "
            "for a model that holds up better on long conversations.")


def run_turn(history: list, model: str, allow_dangerous: bool = False,
             max_steps: int = 6, on_action=None):
    """
    history: [{"role": "user"/"assistant", "content": "..."}] without tool messages.
    on_action: optional callback(action_dict) called the moment a tool finishes,
               so a terminal UI can show progress live.
    Returns: {"reply": str, "actions": [...], "history": [...]}
    """
    from datetime import datetime
    sys_msg = {
        "role": "system",
        "content": system_prompt(allow_dangerous).replace(
            "{today}", datetime.now().strftime("%A, %d %B %Y")
        ),
    }
    convo = [sys_msg] + _trim_history(history)
    schemas = tool_schemas(allow_dangerous)
    actions = []
    user_text = next((m["content"] for m in reversed(history)
                      if m.get("role") == "user"), "")

    for _ in range(max_steps):
        msg = _ollama_chat(model, convo, schemas)
        calls = _normalise_tool_calls(msg)

        if not calls:
            reply = (msg.get("content") or "").strip()
            # The model parroted the user or produced nothing: retry without tools.
            if _looks_degenerate(reply, user_text):
                reply = _force_answer(model, convo, user_text)
            convo.append({"role": "assistant", "content": reply})
            return {"reply": reply, "actions": actions, "history": _clean_history(convo)}

        # Record the assistant's tool request, then run each tool
        convo.append({"role": "assistant", "content": msg.get("content") or "",
                      "tool_calls": msg.get("tool_calls")})

        for call in calls:
            result = T.execute(call["name"], call["arguments"], allow_dangerous)
            action = {
                "tool": call["name"],
                "arguments": call["arguments"],
                "ok": bool(result.get("ok")),
                "result": result,
            }
            actions.append(action)
            if on_action:
                try:
                    on_action(action)
                except Exception:  # noqa: BLE001
                    pass
            convo.append({
                "role": "tool",
                "tool_name": call["name"],
                "content": json.dumps(result, ensure_ascii=False)[:MAX_TOOL_RESULT_CHARS],
            })

    # Ran out of steps — force a plain-language summary instead of looping forever
    reply = _force_answer(model, convo, user_text)
    if "lost track" in reply:
        done = ", ".join(a["tool"] for a in actions) or "nothing"
        reply = (f"I tried {len(actions)} step(s) ({done}) but could not finish. "
                 f"Could you rephrase, or give me a bit more detail?")
    convo.append({"role": "assistant", "content": reply})
    return {"reply": reply, "actions": actions, "history": _clean_history(convo)}
