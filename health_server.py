"""Lightweight health check server and 24/7 keep-alive engine for Render."""
import asyncio
import logging
import os
import aiohttp
from aiohttp import web
import config

logger = logging.getLogger(__name__)

# Public Render URL or custom keep-alive target
KEEP_ALIVE_URL = os.getenv("RENDER_EXTERNAL_URL", os.getenv("KEEP_ALIVE_URL", "https://cheatcode-telegram-bot.onrender.com/health"))

async def health_check_handler(request):
    return web.Response(
        text='{"status": "online", "mode": "cheatcode-bot", "health": "ok", "version": "2.0"}',
        content_type="application/json"
    )

async def keep_alive_loop():
    """Ping public URL every 8 minutes so Render never spins down on free tier."""
    # Wait 2 minutes after startup before first ping
    await asyncio.sleep(120)
    logger.info(f"Keep-alive watchdog active targeting: {KEEP_ALIVE_URL}")

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(KEEP_ALIVE_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    logger.info(f"Keep-alive ping sent to {KEEP_ALIVE_URL} -> HTTP {resp.status}")
        except Exception as e:
            logger.warning(f"Keep-alive ping error: {e}")

        # Sleep 8 minutes (Render sleeps after 15 min of no HTTP traffic)
        await asyncio.sleep(480)

async def start_health_server():
    """Start an aiohttp server in the background for 24/7 cloud health checks."""
    if not config.ENABLE_HEALTH_SERVER:
        return None
    try:
        app = web.Application()
        app.router.add_get("/", health_check_handler)
        app.router.add_get("/health", health_check_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", config.PORT)
        await site.start()
        logger.info(f"Health check HTTP server active on 0.0.0.0:{config.PORT}")

        # Launch background keep-alive task so Render never sleeps
        asyncio.create_task(keep_alive_loop())

        return runner
    except Exception as e:
        logger.warning(f"Could not start health check HTTP server on port {config.PORT}: {e}")
        return None
