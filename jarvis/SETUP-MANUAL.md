# Manual setup — if `setup.bat` keeps vanishing

Use this route if `setup.bat` disappeared after you ran it, or it wrongly says
Ollama is not installed. This version uses **no batch files at all**, so there is
nothing for Windows or antivirus to delete.

You will do 3 things:

1. Install **Ollama** (the AI engine) by hand
2. Install **Python** by hand
3. Run 3 lines in a Command Prompt

Total time: about 15 minutes, most of it waiting for downloads.

---

## Step 1 — Install Ollama

1. Open this page in your browser: **https://ollama.com/download/windows**
2. Click **Download for Windows**. You get a file called `OllamaSetup.exe`.
3. Open it and let it install (no options to change, just Install).
4. Look at the **bottom-right corner of your screen, near the clock** — you should see a
   small llama icon. That means it is running in the background.

### Route B — the one-line PowerShell install

If the `OllamaSetup.exe` download is slow or blocked, Ollama's own download page offers this
one-liner instead. It is official and safe:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Reading it left to right:

| Piece | Meaning |
|---|---|
| `irm` | short for `Invoke-RestMethod` — downloads the text at that address |
| `https://ollama.com/install.ps1` | Ollama's official install script, on their own website |
| `\|` | the pipe — hands what was downloaded to the next command |
| `iex` | short for `Invoke-Expression` — runs it |

So: *"download Ollama's installer script from ollama.com and run it."* That script downloads
OllamaSetup.exe and installs it for your user account — no administrator rights needed.

**To run it:**

1. Press `Win + X`, then choose **Terminal** or **Windows PowerShell**.
   (It must be **PowerShell**, not the old Command Prompt.)
2. Paste the line — `Ctrl + V`, or right-click inside the window — and press `Enter`.
3. Nothing much appears for 1–2 minutes. That's normal; it runs silently.
4. When it finishes, **close PowerShell and open a new one** so Windows picks up the new command.

> **Safety rule worth remembering:** `irm ... | iex` means "download code and run it".
> Only ever do that when the address is a site you trust — for Ollama that is exactly
> `ollama.com`. If you ever see the same pattern with some other domain, don't run it.
> Want to read the script before running it? Paste just `irm https://ollama.com/install.ps1`
> (no pipe) — it prints the script instead of running it.

---

**Check it worked.** Press `Win + R`, type `cmd`, press Enter, then type this and press Enter:

```
ollama --version
```

You should see a version number, e.g. `ollama version is 0.5.1`.
If you instead see *"'ollama' is not recognized"*, close that black window, open a **new** one,
and try again — Windows only picks up new programs in freshly opened windows.

> If `ollama --version` still fails but you do see the llama icon:
> type this instead, all on one line:
>
> ```
> "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" --version
> ```

---

## Step 2 — Install Python

1. Go to **https://www.python.org/downloads/windows/**
2. Click the big yellow **"Download Windows installer (64-bit)"** link.
3. Open the downloaded file. **On the very first screen, tick the box at the bottom that says
   "Add python.exe to PATH"** — this is the one people miss, and without it nothing works.
4. Click **Install Now**, wait, then click **Close**.

**Check it worked.** Open a **new** Command Prompt (`Win + R` → `cmd` → Enter):

```
python --version
```

You want something like `Python 3.12.4`. If it says *"not recognized"*, close the window and
open a new one before worrying — that alone fixes it most of the time.

---

## Step 3 — Start Jarvis

**3a. Put the `jarvis` folder somewhere permanent** — for example
`C:\Users\YourName\Jarvis`. It must contain `app.py`, `agent.py`, `tools.py` and a `static` folder.

**3b. Open a Command Prompt inside that folder.** Easiest way:

- Open the `jarvis` folder in File Explorer
- Click once in the **address bar** at the top (where the path is shown)
- Type `cmd` and press `Enter`

A black window opens, already pointing at your jarvis folder.

**3c. Install the packages** (one line, then Enter; takes 1–3 minutes):

```
pip install -r requirements.txt
```

**3d. Download the AI model** (one line, ~2 GB, several minutes):

```
ollama pull qwen2.5:3b
```

**3e. Start the assistant:**

```
python app.py
```

Your browser opens with Jarvis. **Leave that black window open** while you use it —
closing it stops the assistant.

---

## Starting it again next time

1. Open the `jarvis` folder
2. Click the address bar, type `cmd`, press Enter
3. Type `python app.py` and press Enter

Or, if it still exists, just double-click **`run.bat`**.
You can also double-click **`Launch Jarvis.pyw`** — it does the same thing.

---

## Why did `setup.bat` disappear?

Almost always one of these two:

**A) You ran it from inside the ZIP file.** Windows silently extracts a temporary copy,
runs it, then deletes that temp copy — so it looks like the file deleted itself, and the
script complains that files are missing because the real folder isn't there.
**Fix:** right-click the zip → **Extract All…** first, then run things inside the extracted folder.

**B) Windows Defender or your antivirus removed it.** Batch files that download and install
software are a common false positive. You'll usually find a notification like
"Threat found: Trojan:BAT/..." in Windows Security → **Protection history**.
**Fix:** use this manual guide instead (it needs no batch file), or click **Actions → Restore**
and add the jarvis folder as an exclusion: Windows Security → Virus & threat protection →
Manage settings → Exclusions → Add an exclusion → Folder.

Either way, **Ollama was never installed** — that's why the script said so. Step 1 above fixes it.

---

## "Could not open requirements file" / "can't open file 'app.py'"

Both mean the same thing: your terminal is in the wrong folder.
Note the path in the error - if it says `C:\Users\YourName\app.py`, you are in your home folder,
not inside the jarvis folder.

**Find the folder** - paste this into PowerShell and press Enter:

```powershell
Get-ChildItem -Path $HOME -Recurse -Filter app.py -ErrorAction SilentlyContinue |
  Select-Object -First 5 -ExpandProperty FullName
```

It prints something like `C:\Users\YourName\Downloads\jarvis\app.py`.
Strip the `\app.py` off the end and go there:

```powershell
cd $HOME\Downloads\jarvis
dir
```

`dir` must show `app.py`, `agent.py`, `tools.py`, `run.bat` and a `static` folder.
Then run:

```powershell
pip install -r requirements.txt
python app.py
```

If `dir` shows only a single folder named `jarvis`, the zip was double-nested - go one level deeper
with `cd jarvis`.

---

## Still stuck?

Copy the exact text from the black window and paste it back to me. The useful lines are the
ones after `pip install` or `python app.py`; "Traceback" or "error" lines matter most.
