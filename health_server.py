"""Lightweight health check server, Webhook listener, and 24/7 keep-alive engine for Render."""
import asyncio
import collections
import datetime
import json
import logging
import os
import time
from typing import Optional

import aiohttp
from aiohttp import web
from telegram import Update
import config

logger = logging.getLogger(__name__)

# Render dynamically sets PORT; fall back to config or 10000
PORT = int(os.getenv("PORT", getattr(config, "PORT", 10000)))
BASE_URL = os.getenv(
    "RENDER_EXTERNAL_URL",
    os.getenv("WEBHOOK_BASE_URL", "https://cheatcode-telegram-bot.onrender.com")
).rstrip("/")

KEEP_ALIVE_URL = f"{BASE_URL}/health"

# In-memory circular log buffer to inspect live logs at /logs
LOG_BUFFER = collections.deque(maxlen=250)

class InMemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            LOG_BUFFER.append(msg)
        except Exception:
            pass

# Install buffer handler onto root logger
_buf_handler = InMemoryLogHandler()
_buf_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

def attach_log_capture(target_logger=None):
    """Attach memory buffer handler to target logger and root logger."""
    _buf_handler.setLevel(logging.INFO)
    if target_logger:
        target_logger.addHandler(_buf_handler)
    logging.getLogger().addHandler(_buf_handler)

attach_log_capture()


# Global telemetry state
START_TIME = time.time()
TELEMETRY = {
    "updates_received": 0,
    "last_update_time": None,
    "last_update_type": None,
    "last_sender": None,
    "last_error": None,
    "mode": "unknown",
    "webhook_url": None,
}

async def health_check_handler(request: web.Request) -> web.Response:
    """Return lightweight plain text to stay far below cron payload limits."""
    return web.Response(text="OK", content_type="text/plain")

async def logs_handler(request: web.Request) -> web.Response:
    """Return live in-memory logs in plain text for instant remote troubleshooting."""
    logs_text = "\n".join(LOG_BUFFER) or "No logs recorded yet."
    return web.Response(text=logs_text, content_type="text/plain")

async def status_handler(request: web.Request) -> web.Response:
    """Return JSON health and telemetry status."""
    uptime_sec = int(time.time() - START_TIME)
    data = {
        "status": "operational",
        "uptime_seconds": uptime_sec,
        "uptime_human": str(datetime.timedelta(seconds=uptime_sec)),
        "mode": TELEMETRY["mode"],
        "webhook_url": TELEMETRY["webhook_url"],
        "updates_received": TELEMETRY["updates_received"],
        "last_update_time": TELEMETRY["last_update_time"],
        "last_update_type": TELEMETRY["last_update_type"],
        "last_sender": TELEMETRY["last_sender"],
        "last_error": TELEMETRY["last_error"],
        "ai_model": config.AI_MODEL,
        "ai_provider": config.AI_PROVIDER,
    }
    return web.Response(text=json.dumps(data, indent=2), content_type="application/json")

def create_webhook_handler(telegram_app):
    """Factory creating the Telegram webhook POST handler."""
    async def webhook_handler(request: web.Request) -> web.Response:
        try:
            raw_data = await request.json()
            TELEMETRY["updates_received"] += 1
            TELEMETRY["last_update_time"] = datetime.datetime.utcnow().isoformat() + "Z"

            # Parse sender details for quick status review
            msg = raw_data.get("message") or raw_data.get("channel_post") or raw_data.get("edited_message") or {}
            sender = "Unknown"
            if "from" in msg:
                sender = f"@{msg['from'].get('username') or msg['from'].get('first_name')}"
            elif "sender_chat" in msg:
                sender = f"Chat [{msg['sender_chat'].get('title')}]"
            TELEMETRY["last_sender"] = sender
            TELEMETRY["last_update_type"] = list(raw_data.keys())[-1] if raw_data else "empty"

            update = Update.de_json(raw_data, telegram_app.bot)
            if update:
                # Process concurrently so Telegram receives an immediate 200 OK acknowledgment
                asyncio.create_task(telegram_app.process_update(update))
            
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Error handling Telegram webhook payload: {e}")
            TELEMETRY["last_error"] = str(e)
            return web.Response(text="ERROR", status=500)

    return webhook_handler

async def keep_alive_loop():
    """Self-ping loop as a secondary fallback."""
    await asyncio.sleep(60)
    logger.info(f"Keep-alive watchdog active targeting: {KEEP_ALIVE_URL}")

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(KEEP_ALIVE_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    logger.debug(f"Keep-alive self-ping -> HTTP {resp.status}")
        except Exception as e:
            logger.warning(f"Keep-alive ping error: {e}")

        await asyncio.sleep(480)

async def start_health_server(telegram_app=None, webhook_mode=False, webhook_url=None):
    """Start an aiohttp server handling health checks, logs, status, and Telegram Webhooks."""
    if not getattr(config, "ENABLE_HEALTH_SERVER", True):
        logger.warning("ENABLE_HEALTH_SERVER is disabled in config.")
        return None

    TELEMETRY["mode"] = "webhook" if webhook_mode else "polling"
    TELEMETRY["webhook_url"] = webhook_url

    try:
        app = web.Application()
        app.router.add_get("/", health_check_handler)
        app.router.add_get("/health", health_check_handler)
        app.router.add_head("/", health_check_handler)
        app.router.add_head("/health", health_check_handler)
        app.router.add_get("/logs", logs_handler)
        app.router.add_get("/status", status_handler)

        if webhook_mode and telegram_app:
            wh_handler = create_webhook_handler(telegram_app)
            app.router.add_post("/webhook", wh_handler)
            app.router.add_post("/telegram-webhook", wh_handler)
            logger.info("Mounted Telegram webhook endpoint on /webhook and /telegram-webhook")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"Unified HTTP/Webhook server active on 0.0.0.0:{PORT} (Mode: {TELEMETRY['mode']})")

        asyncio.create_task(keep_alive_loop())
        return runner
    except Exception as e:
        logger.error(f"Could not start HTTP server on port {PORT}: {e}")
        return None
