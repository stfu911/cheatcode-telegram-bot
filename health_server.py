"""Lightweight health check server to satisfy Cloud PaaS port binding requirements."""
import logging
from aiohttp import web
import config

logger = logging.getLogger(__name__)

async def health_check_handler(request):
    return web.Response(
        text='{"status": "online", "mode": "cheatcode-bot", "health": "ok"}',
        content_type="application/json"
    )

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
        return runner
    except Exception as e:
        logger.warning(f"Could not start health check HTTP server on port {config.PORT}: {e}")
        return None
