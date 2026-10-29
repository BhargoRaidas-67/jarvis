"""
cli.py — Jarvis in your terminal. No browser, no server.

Run it:
    python cli.py
    python cli.py --model qwen2.5:7b
    python cli.py --pc              start with PC control ON
    python cli.py --speak           read answers aloud (Windows voices, no extra installs)
    python cli.py --voice           talk to it with your mic (needs: pip install SpeechRecognition pyaudio)

Type /help inside for the command list. Type /quit or press Ctrl+C to leave.
"""

import argparse
import os
import platform
import subprocess
import sys
import threading
import time

import agent
import tools as T

# ---------------------------------------------------------------- colours
class C:
    on = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
    RESET = "\033[0m" if on else ""
    DIM = "\033[2m" if on else ""
    BOLD = "\033[1m" if on else ""
    CYAN = "\033[36m" if on else ""
    VIOLET = "\033[35m" if on else ""
    GREEN = "\033[32m" if on else ""
    RED = "\033[31m" if on else ""
    YELLOW = "\033[33m" if on else ""
    GREY = "\033[90m" if on else ""


BANNER = f"""{C.CYAN}{C.BOLD}
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝{C.RESET}
{C.GREY}   local AI assistant · runs on your machine · type /help{C.RESET}
"""

# ---------------------------------------------------------------- speaking
def speak(text: str):
    """Read text aloud using the built-in Windows voice (no pip packages needed)."""
    clean = (text or "").replace('"', "'").replace("\n", " ")
    if not clean.strip():
        return
    if platform.system() == "Windows":
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f'$s.Speak("{clean[:900]}")'
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, timeout=120)
            return
        except Exception:  # noqa: BLE001
            pass
    # macOS / Linux fallbacks
    try:
        if platform.system() == "Darwin":
            subprocess.run(["say", clean[:900]], timeout=120)
        else:
            subprocess.run(["espeak", clean[:900]], timeout=120)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- listening
def make_listener():
    """Return a callable that records one phrase and returns text, or None."""
    try:
        import speech_recognition as sr
    except ImportError:
        print(f"{C.YELLOW}Voice input needs two packages:{C.RESET}\n"
              f"   pip install SpeechRecognition pyaudio\n"
              f"{C.GREY}(On Windows, if pyaudio fails: pip install pipwin && pipwin install pyaudio){C.RESET}")
        return None

    rec = sr.Recognizer()
    rec.energy_threshold = 300
    rec.dynamic_energy_threshold = True

    def listen():
        try:
            with sr.Microphone() as source:
                print(f"{C.CYAN}🎤 listening…{C.RESET} {C.GREY}(speak now){C.RESET}")
                rec.adjust_for_ambient_noise(source, duration=0.3)
                audio = rec.listen(source, timeout=6, phrase_time_limit=15)
            print(f"{C.GREY}   transcribing…{C.RESET}")
            return rec.recognize_google(audio)
        except sr.WaitTimeoutError:
            print(f"{C.GREY}   (heard nothing){C.RESET}")
            return None
        except sr.UnknownValueError:
            print(f"{C.GREY}   (could not understand that){C.RESET}")
            return None
        except Exception as e:  # noqa: BLE001
            print(f"{C.RED}   mic error: {e}{C.RESET}")
            return None

    return listen


# ---------------------------------------------------------------- helpers
def spinner(stop_event, label="thinking"):
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r{C.GREY}{frames[i % len(frames)]} {label}…{C.RESET}")
        sys.stdout.flush()
        i += 1
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()


def pretty_action(a: dict) -> str:
    name, args, res = a["tool"], a.get("arguments") or {}, a.get("result") or {}
    detail = ""
    if name == "open_app":
        detail = args.get("name", "")
    elif name == "open_url":
        detail = args.get("url", "")
    elif name in ("write_file", "read_file", "copy_folder", "copy_file", "move_folder",
                  "list_files", "make_folder"):
        detail = args.get("path") or args.get("source") or ""
        if name in ("copy_folder", "move_folder", "copy_file") and args.get("destination"):
            detail = f"{detail} → {args['destination']}"
    elif name == "web_search":
        detail = args.get("query", "")
    elif name == "press_keys":
        detail = args.get("keys", "")
    elif name == "volume":
        detail = args.get("action", "")
    elif name == "run_command":
        detail = args.get("command", "")
    elif name == "remember":
        detail = args.get("fact", "")

    mark = f"{C.GREEN}✓{C.RESET}" if a["ok"] else f"{C.RED}✗{C.RESET}"
    body = f"{name}{C.GREY}({detail[:70]}){C.RESET}" if detail else name
    line = f"  {mark} {C.VIOLET}{body}{C.RESET}"
    if not a["ok"]:
        err = (res.get("error") or "")[:120]
        line += f"\n    {C.RED}{err}{C.RESET}"
    return line


HELP = f"""
{C.BOLD}Just type normally{C.RESET} — "open chrome", "what's my battery", "copy my documents to desktop".

{C.BOLD}Commands{C.RESET}
  {C.CYAN}/help{C.RESET}              this list
  {C.CYAN}/model <name>{C.RESET}      switch model (e.g. /model qwen2.5:7b)
  {C.CYAN}/models{C.RESET}            list installed models
  {C.CYAN}/pc{C.RESET}                toggle PC control (shell commands, shutdown, lock)
  {C.CYAN}/speak{C.RESET}             toggle spoken replies
  {C.CYAN}/voice{C.RESET}             toggle mic input (push Enter to talk)
  {C.CYAN}/memory{C.RESET}            show what Jarvis remembers
  {C.CYAN}/forget{C.RESET}            wipe its memory
  {C.CYAN}/tools{C.RESET}             list what it can do
  {C.CYAN}/clear{C.RESET}             start a fresh conversation
  {C.CYAN}/quit{C.RESET}              exit

{C.BOLD}Voice mode{C.RESET}: with /voice on, just press Enter on an empty line and speak.
"""


def print_tools(pc: bool):
    print(f"\n{C.BOLD}Always available{C.RESET}")
    for i, name in enumerate(sorted(T.SAFE_TOOLS), 1):
        print(f"  {C.GREY}{i:2d}.{C.RESET} {name}")
    status = f"{C.GREEN}ON{C.RESET}" if pc else f"{C.GREY}OFF (use /pc){C.RESET}"
    print(f"\n{C.BOLD}PC control{C.RESET} — {status}")
    for name in sorted(T.DANGEROUS_TOOLS):
        print(f"  {C.GREY} •{C.RESET} {name}")
    print()


def main():
    ap = argparse.ArgumentParser(description="Jarvis in your terminal")
    ap.add_argument("--model", "-m", default="", help="model to use (default: best installed)")
    ap.add_argument("--pc", action="store_true", help="start with PC control enabled")
    ap.add_argument("--speak", action="store_true", help="read replies aloud")
    ap.add_argument("--voice", action="store_true", help="enable mic input")
    args = ap.parse_args()

    print(BANNER)

    running, models, err = agent.ollama_status()
    if not running:
        print(f"{C.RED}Ollama is not running.{C.RESET} Start the Ollama app (llama icon in your "
              f"system tray) and try again.\n{C.GREY}{err}{C.RESET}")
        return 1
    if not models:
        print(f"{C.RED}No models installed.{C.RESET} Run:  ollama pull qwen2.5:3b")
        return 1

    model = args.model or next(
        (m for m in ("qwen2.5:7b", "qwen2.5:3b", "llama3.1:8b", "llama3.2:3b") if m in models),
        models[0],
    )
    if model not in models:
        print(f"{C.YELLOW}{model} is not installed. Available: {', '.join(models)}{C.RESET}")
        return 1

    history = []
    use_pc = args.pc
    use_speak = args.speak
    listen = make_listener() if args.voice else None
    if args.voice and listen is None:
        print(f"{C.GREY}Continuing without voice input.{C.RESET}")

    print(f"  {C.GREY}model{C.RESET}  {C.BOLD}{model}{C.RESET}")
    print(f"  {C.GREY}pc   {C.RESET}  {'ON' if use_pc else 'off'}   "
          f"{C.GREY}speak{C.RESET} {'on' if use_speak else 'off'}   "
          f"{C.GREY}voice{C.RESET} {'on' if listen else 'off'}")
    print(f"  {C.GREY}Type /help for commands. Ctrl+C to exit.{C.RESET}\n")

    def handle(text: str):
        nonlocal history
        stop = threading.Event()
        th = threading.Thread(target=spinner, args=(stop,), daemon=True)
        th.start()
        try:
            result = agent.run_turn(
                history, model, allow_dangerous=use_pc,
                on_action=lambda a: (stop.set(), print(pretty_action(a))),
            )
        except Exception as e:  # noqa: BLE001
            stop.set()
            th.join()
            msg = str(e)
            if "Connection" in msg or "refused" in msg:
                msg = "Lost connection to Ollama. Is the Ollama app still running?"
            print(f"{C.RED}{msg}{C.RESET}\n")
            return
        stop.set()
        th.join()

        history = result["history"]
        print(f"{C.CYAN}{C.BOLD}Jarvis{C.RESET}  {result['reply']}\n")
        if use_speak:
            speak(result["reply"])

    while True:
        try:
            if listen:
                prompt = f"{C.GREEN}you{C.RESET} {C.GREY}[Enter to talk, or type]{C.RESET} > "
            else:
                prompt = f"{C.GREEN}you{C.RESET} > "
            line = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C.GREY}bye.{C.RESET}")
            return 0

        if line == "" and listen:
            spoken = listen()
            if not spoken:
                continue
            line = spoken.strip()

        if not line:
            continue

        # -------- commands --------
        low = line.lower()
        if low in ("/quit", "/exit", "/q"):
            print(f"{C.GREY}bye.{C.RESET}")
            return 0
        if low == "/help":
            print(HELP)
            continue
        if low == "/tools":
            print_tools(use_pc)
            continue
        if low == "/clear":
            history = []
            print(f"{C.GREY}Fresh conversation.{C.RESET}\n")
            continue
        if low == "/pc":
            use_pc = not use_pc
            state = f"{C.GREEN}ON{C.RESET} — shell commands, lock, restart, shutdown allowed" \
                if use_pc else f"{C.GREY}OFF{C.RESET} — dangerous tools disabled"
            print(f"PC control {state}\n")
            continue
        if low == "/speak":
            use_speak = not use_speak
            print(f"Spoken replies {'on' if use_speak else 'off'}\n")
            continue
        if low == "/voice":
            if listen:
                listen = None
                print("Voice input off\n")
            else:
                listen = make_listener()
                print(f"Voice input {'on — press Enter on an empty line and speak' if listen else 'unavailable'}\n")
            continue
        if low == "/models":
            _, inst, _ = agent.ollama_status()
            print("  " + "\n  ".join(inst) + "\n")
            continue
        if low.startswith("/model"):
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                print(f"Current model: {C.BOLD}{model}{C.RESET}\n")
            else:
                want = parts[1].strip()
                _, inst, _ = agent.ollama_status()
                if want in inst:
                    model = want
                    print(f"Switched to {C.BOLD}{model}{C.RESET}\n")
                else:
                    print(f"{C.RED}{want} is not installed.{C.RESET} Available: {', '.join(inst)}\n")
            continue
        if low == "/memory":
            facts = T.recall().get("facts", [])
            print("  " + ("\n  ".join(facts) if facts else f"{C.GREY}nothing remembered yet{C.RESET}") + "\n")
            continue
        if low == "/forget":
            T.forget_all()
            print(f"{C.GREY}Memory wiped.{C.RESET}\n")
            continue
        if low.startswith("/"):
            print(f"{C.YELLOW}Unknown command. /help for the list.{C.RESET}\n")
            continue

        # -------- normal message --------
        history.append({"role": "user", "content": line})
        handle(line)


if __name__ == "__main__":
    sys.exit(main())
