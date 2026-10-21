"""Configuration loader for Cheat Code Telegram Bot."""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# AI Provider Settings
# Supported: "groq", "openai", "openrouter", "gemini", "custom"
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower().strip()

# Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()

def get_api_keys() -> List[str]:
    """Return all configured API keys for failover pool."""
    raw = ""
    if AI_API_KEY:
        raw = AI_API_KEY
    elif AI_PROVIDER == "groq":
        raw = GROQ_API_KEY or os.getenv("GROQ_KEY", "")
    elif AI_PROVIDER == "gemini":
        raw = GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY", "")
    elif AI_PROVIDER in ("openai", "openrouter"):
        raw = OPENAI_API_KEY
    else:
        raw = GROQ_API_KEY or OPENAI_API_KEY or GEMINI_API_KEY

    # Split on commas or whitespace
    keys = [k.strip() for k in raw.replace("\n", ",").split(",") if k.strip()]
    return keys

def get_api_key() -> str:
    keys = get_api_keys()
    return keys[0] if keys else ""

# Determine Base URL and Model
def get_api_config():
    provider = AI_PROVIDER
    base_url = os.getenv("AI_BASE_URL", "").strip()
    model = os.getenv("AI_MODEL", "").strip()

    if provider == "groq":
        base_url = base_url or "https://api.groq.com/openai/v1"
        model = model or "qwen/qwen3.8-27b"

    elif provider == "gemini":
        # Google provides an OpenAI-compatible endpoint
        base_url = base_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
        model = model or "gemini-2.0-flash"
    elif provider == "openrouter":
        base_url = base_url or "https://openrouter.ai/api/v1"
        model = model or "meta-llama/llama-3.3-70b-instruct"
    elif provider == "openai":
        base_url = base_url or "https://api.openai.com/v1"
        model = model or "gpt-4o-mini"
    else:
        # Custom fallback
        base_url = base_url or "https://api.groq.com/openai/v1"
        model = model or "llama-3.3-70b-versatile"

    return base_url, model

AI_BASE_URL, AI_MODEL = get_api_config()

# Hyperparameters
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.2"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "600"))

# Allowed User IDs (comma separated, empty = all users allowed)
_allowed = os.getenv("ALLOWED_USER_IDS", "").strip()
ALLOWED_USERS: List[int] = [int(uid.strip()) for uid in _allowed.split(",") if uid.strip().isdigit()]

# Optional HTTP Port for cloud health check (Render / Railway / Fly.io)
PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "8080")))
ENABLE_HEALTH_SERVER = os.getenv("ENABLE_HEALTH_SERVER", "true").lower() in ("true", "1", "yes")

# Group Discussion & Auto-Context Settings
AUTO_REPLY_GROUP_QUESTIONS = os.getenv("AUTO_REPLY_GROUP_QUESTIONS", "true").lower() in ("true", "1", "yes")
REPLY_ONLY_WHEN_MENTIONED = os.getenv("REPLY_ONLY_WHEN_MENTIONED", "false").lower() in ("true", "1", "yes")
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "true").lower() in ("true", "1", "yes")

