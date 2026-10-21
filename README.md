# ⚡ Cheat Code Telegram Bot (24/7 Tactical Troubleshooter)

Tactical problem fixer Telegram bot. Zero fluff, zero conversational filler. Jump straight to high-impact terminal one-liners, hidden registry toggles, and shortcut workarounds.

---

## ⚡ The 3-Part Output Format

Every response strictly follows this 3-part layout:

```
⚡ THE CHEAT CODE:
[Direct command, key combo, registry tweak, or exact 2-step click path]

🔍 THE MECHANIC:
[1 sentence explaining why this works so the user learns the bypass]

💣 THE OVERRIDE (Plan B):
[The aggressive, nuclear, or alternative bypass if the quick fix fails]
```

*Commands are formatted for Telegram tap-to-copy (single tap on mobile copies directly to clipboard).*

---

## 🚀 Quick Setup (3 Minutes)

### Step 1: Clone or Navigate to Project
```bash
cd cheatcode-bot
```

### Step 2: Configure `.env`
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Open `.env` and fill:
1. `TELEGRAM_BOT_TOKEN`: Get it from [@BotFather](https://t.me/BotFather) on Telegram.
2. `GROQ_API_KEY`: Get a 100% free key from [Groq Console](https://console.groq.com/keys) (instant token generation, runs `llama-3.3-70b-versatile` at ~300 tokens/sec).
   *(Or set `AI_PROVIDER=gemini` with `GEMINI_API_KEY` from Google AI Studio, or `AI_PROVIDER=openai`).*

### Step 3: Run Locally
**Windows:**
Double-click `run_local.bat` or run:
```powershell
.\run_local_247.ps1
```

**Linux / Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

---

## 🤖 Bot Commands & Triggers

| Trigger | Description |
|---|---|
| Plain Text | Send any glitch, issue, or error message directly to get a 3-part bypass. |
| `/cheat <issue>` | Forces direct 80/20 terminal or UI bypass. |
| `/nuke <issue>` | Scorched-earth aggressive override (process killers, cache flushes, stack resets). |
| `/fix <issue>` | Immediate tactical repair. |
| `/ping` | Health & model telemetry check. |

---

## 🌐 24/7 Always-On Deployment Options

### Option 1: Free Cloud Hosting (Render)
1. Push this folder to a GitHub repository.
2. Go to [render.com](https://render.com) and create a **Web Service** or **Background Worker**.
3. Connect your repository.
4. Settings:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. Under **Environment Variables**, add:
   - `TELEGRAM_BOT_TOKEN` = `your_token`
   - `AI_PROVIDER` = `groq`
   - `GROQ_API_KEY` = `your_key`
6. Click **Deploy**. Bot runs 24/7. *(The built-in `health_server.py` automatically binds to `$PORT` to keep Render happy).*

---

### Option 2: Docker / Docker Compose
Deploy on any server with a single command:
```bash
docker compose up -d --build
```
`restart: always` keeps the container alive 24/7 through reboots and network drops.

---

### Option 3: Linux VPS (Ubuntu / Debian Systemd Service)
Keep it running 24/7 on your VPS with auto-recovery:

1. Copy folder to `/opt/cheatcode-bot`
2. Create virtual environment & install requirements:
   ```bash
   cd /opt/cheatcode-bot
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```
3. Copy the systemd service file:
   ```bash
   sudo cp cheatcode-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now cheatcode-bot
   ```
4. Check status & logs:
   ```bash
   sudo systemctl status cheatcode-bot
   journalctl -u cheatcode-bot -f
   ```

---

### Option 4: Windows 24/7 Background (Watchdog)
Run `run_local_247.ps1`. If Telegram drops or the process halts, the watchdog re-spawns it after 5 seconds automatically.
