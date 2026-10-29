# Jarvis — your own AI assistant for Windows

A local AI assistant that runs **entirely on your PC**. It chats, speaks, listens, and can actually
control your computer: open apps, manage files, take screenshots, check your system, and more.

No accounts, no subscriptions, no data leaving your machine.

---

## What you need

- Windows 10 or 11
- 8 GB RAM minimum (16 GB is comfortable)
- About 5 GB of free disk space
- Internet only for the one-time downloads

---

## Install (do this once)

1. **Copy the whole `jarvis` folder** somewhere permanent, e.g. `C:\Users\YourName\Jarvis`.
   Don't run it from inside a ZIP file.

2. **Double-click `setup.bat`.**
   It will install anything missing (Python, Ollama), then ask you to pick an AI model:

   | Choice | Model | Size | Good for |
   |---|---|---|---|
   | 1 | qwen2.5:3b | ~2 GB | Any PC with 8 GB RAM — **start here** |
   | 2 | qwen2.5:7b | ~5 GB | Best quality, needs 16 GB RAM |
   | 3 | llama3.2:3b | ~2 GB | Light and fast |

   If Windows shows a blue "Windows protected your PC" box, click **More info → Run anyway**
   (it's just a script, and you can open it in Notepad to read every line first).
   If setup tells you Python or Ollama was just installed, **close the window, open setup.bat again**.

3. Done.

## Two ways to run it

**Browser version** — `run.bat` or `Launch Jarvis.pyw`. Nicer looking, has voice in/out.
**Terminal version** — `run-cli.bat`, or `python cli.py`. No browser at all, fastest to open.

## Start it

**Double-click `run.bat`.** Your browser opens with Jarvis ready to go.
Keep the black `run.bat` window open while you use it — closing it stops the assistant.

---

## How to use it

**Type** in the box, or click the **microphone** and speak. Replies are read aloud by default.

Things to try:

- `open chrome and search for the weather in Jabalpur`
- `what's my battery, RAM and disk usage?`
- `copy my documents folder to my desktop`
- `move the Downloads folder to my external drive`
- `create a file on my desktop called ideas.txt with three app ideas`
- `take a screenshot`
- `read the clipboard`
- `turn the volume down`
- `remember that my main project is called Nova`
- `what did I tell you to remember?`

### The three switches (left sidebar)

| Switch | What it does |
|---|---|
| **Speak replies** | Jarvis reads answers out loud |
| **Hands-free listening** | Mic stays on, so you can talk without clicking. Use headphones or it will hear itself. |
| **Allow PC control** | Unlocks shell commands, lock screen, restart, shutdown. **Off by default** — turn it on only when you need it. |

**Memory** is saved in `C:\Users\YourName\.jarvis\memory.json`, so Jarvis remembers facts between
sessions. "Clear memory" wipes it.

---

## The terminal version (`python cli.py`)

Same brain, same tools, no browser and no local server — it talks to Ollama directly.

```
python cli.py                 # normal start
python cli.py --speak         # read answers aloud
python cli.py --pc            # start with PC control ON
python cli.py --voice         # talk to it (see below)
python cli.py -m qwen2.5:7b   # pick a model
```

Inside, type normally, or use these:

| Command | Does |
|---|---|
| `/help` | command list |
| `/model <name>` | switch model |
| `/models` | list installed models |
| `/pc` | toggle PC control |
| `/speak` | toggle spoken replies |
| `/voice` | toggle mic input |
| `/memory`, `/forget` | show / wipe memory |
| `/tools` | list abilities |
| `/clear` | fresh conversation |
| `/quit` | exit |

Tool calls appear live as they run, e.g.
`✓ open_app(chrome)` then the answer. No extra packages are needed —
spoken replies use the built-in Windows voice via PowerShell.

**Voice input in the terminal** is optional and needs:
```
pip install SpeechRecognition pyaudio
```
If `pyaudio` refuses to install: `pip install pipwin` then `pipwin install pyaudio`.
With `/voice` on, press **Enter on an empty line** and speak.

---

## Safety, plainly

This program can run commands on your computer. That is the whole point of it — and the one thing
to understand before you use it.

- Dangerous abilities (shell commands, shutdown, restart, lock) are **blocked unless you flip
  "Allow PC control"**, and that switch resets every time you restart Jarvis.
- The assistant **cannot write into** `C:\Windows`, `Program Files`, or `ProgramData`.
- It cannot delete files — there is no delete tool at all.
- **Copying** never silently replaces anything. If the destination already exists it stops and asks;
  it only overwrites when you explicitly say "overwrite". It also refuses to copy a folder into itself,
  and cannot copy *out of* system folders like `C:\Windows`.
- Every action it takes shows up as a small chip under its reply (✓ succeeded, ✕ failed), so you can
  always see exactly what it did.
- The server only listens on `127.0.0.1` (your own PC). Nothing is exposed to your network.
- Smaller local models are not geniuses. They sometimes pick the wrong tool. Watch the chips, and
  don't enable PC control while doing something delicate.

---

## Files in this folder

| File | What it is |
|---|---|
| `setup.bat` | One-time installer (Python packages + AI engine + model) |
| `run.bat` | Starts the assistant |
| `app.py` | Local web server + the API the interface talks to |
| `agent.py` | The brain: talks to Ollama, decides which tools to use |
| `tools.py` | All 26 abilities (open apps, copy/move files, screenshot, system info…) |
| `static/index.html` | The interface you see in the browser |
| `requirements.txt` | Python packages |

---

## Common problems

**"Ollama not running" in the sidebar**
Ollama isn't started. Open **Ollama** from the Start menu (or run `run.bat`, which tries to start it),
wait ~5 seconds, then reload the page.

**"I have no AI model to think with"**
The model download didn't finish. Open Command Prompt and run `ollama pull qwen2.5:3b`.

**The assistant starts repeating my own message back to me**
This was a real bug, fixed in this version. The 3B model was being handed too much history and tool
output for its context window, so it degraded into parroting. Now: the context is 16k, only the last
6 messages are replayed, tool output is trimmed, and if a reply comes back as an echo of your question
it automatically retries once with tools off. If it still trips, ask in a shorter sentence, or use
`qwen2.5:7b` (needs 16 GB RAM) which holds up much better.

Tune it if you like, before starting:
```
set JARVIS_MAX_TURNS=4
set JARVIS_NUM_CTX=8192
```

**The mic button does nothing at all**
Fixed in this version — it used to `return` silently when a flag was stuck. Now there is a status
line under the input box that always explains what happened, and a watchdog clears wedged state
every 2 seconds. Common causes, in order:

1. **The browser.** Voice input needs Chrome or Edge. Firefox and Brave have no speech recognition.
2. **Page address.** It must be `127.0.0.1` or `localhost`. `http://169.254.x.x:5000` is not a secure
   context, so the browser refuses the mic. Check the address bar.
3. **Microphone permission.** Click the padlock icon at the left of the address bar → Microphone → Allow.
   Then reload with `Ctrl+F5`.
4. **Windows permission.** Settings → Privacy & security → Microphone → turn on "Let desktop apps
   access your microphone".
5. **No microphone at all.** If Jarvis keeps saying "waiting for permission", Windows may not see a
   mic: Settings → System → Sound → Input.

Right-click the mic button for a live diagnostics readout (secure page, speech API, stuck flags, voices).

**The microphone keeps sending by itself**
Also a real bug, fixed: it used to re-send whatever text was left in the box when a recording ended
with silence. Now a voice send only happens when speech was actually captured, repeat sends within
4 seconds are ignored, it never listens while it is speaking, the gap between recordings is 0.9s, and
hands-free switches itself off after 4 silent recordings in a row.

**Replies are slow**
Normal on a 3B model without a graphics card — 3–10 seconds is expected. A bigger model is smarter
but slower. On a weak PC, `llama3.2:3b` is the fastest choice.

**The microphone button does nothing**
Voice input needs Chrome or Edge, and permission to use the mic — click **Allow** in the address bar.
Also check Windows Settings → Privacy → Microphone.

**Voice replies have the wrong accent**
Windows → Settings → Time & Language → Speech → add an English voice you like.
Jarvis automatically prefers the most natural installed voice.

**Port 5000 already in use**
Jarvis moves to the next free port automatically; check the `run.bat` window for the address.

**I want a smarter model**
`ollama pull qwen2.5:7b` (needs 16 GB RAM), then pick it from the **Brain** dropdown.

---

## Where to take it next

Easy additions you can make in `tools.py`:

- Email/calendar — needs an API key, so ask if you want this wired up
- Weather with a real API instead of just a web search
- A dictation mode that types what you say into any app
- Zip a folder before copying or emailing it
- A `delete_file` tool — deliberately left out; add it only with a confirmation step
