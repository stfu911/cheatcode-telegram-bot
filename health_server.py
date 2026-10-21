"""Lightweight health check server and 24/7 keep-alive engine for Render."""
import asyncio
import logging
import os
import aiohttp
from aiohttp import web
import config

logger = logging.getLogger(__name__)

# Render dynamically sets PORT; fall back to config or 10000
PORT = int(os.getenv("PORT", getattr(config, "PORT", 10000)))
KEEP_ALIVE_URL = os.getenv(
    "RENDER_EXTERNAL_URL",
    os.getenv("KEEP_ALIVE_URL", "https://cheatcode-telegram-bot.onrender.com/health")
)

async def health_check_handler(request):
    """Return lightweight plain text to stay far below cron payload limits."""
    return web.Response(text="OK", content_type="text/plain")

async def keep_alive_loop():
    """Self-ping loop as a secondary fallback."""
    await asyncio.sleep(120)
    logger.info(f"Keep-alive watchdog active targeting: {KEEP_ALIVE_URL}")

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(KEEP_ALIVE_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    logger.info(f"Keep-alive ping sent to {KEEP_ALIVE_URL} -> HTTP {resp.status}")
        except Exception as e:
            logger.warning(f"Keep-alive ping error: {e}")

        await asyncio.sleep(480)

async def start_health_server():
    """Start an aiohttp server in the background for 24/7 cloud health checks."""
    if not getattr(config, "ENABLE_HEALTH_SERVER", True):
        logger.warning("ENABLE_HEALTH_SERVER is disabled in config.")
        return None

    try:
        app = web.Application()
        app.router.add_get("/", health_check_handler)
        app.router.add_get("/health", health_check_handler)
        app.router.add_head("/", health_check_handler)
        app.router.add_head("/health", health_check_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"Health check HTTP server active on 0.0.0.0:{PORT}")

        asyncio.create_task(keep_alive_loop())
        return runner
    except Exception as e:
        logger.error(f"Could not start health check HTTP server on port {PORT}: {e}")
        return None
        
