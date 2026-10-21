"""Cheat Code Telegram Bot - Tactical direct-bypass troubleshooting bot for DMs and Discussion Groups."""
import asyncio
import logging
import re
import sys
from typing import Dict, Tuple
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from ai_client import ai_client
from formatter import markdown_to_telegram_html
from health_server import start_health_server

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Setup structured logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("CheatCodeBot")

# Cache channel posts in memory: (chat_id, message_thread_id / root_post_id) -> post text/caption
channel_posts_cache: Dict[Tuple[int, int], str] = {}

# Troubleshooting keyword patterns for auto-detecting member complaints in discussion groups
TROUBLESHOOT_KEYWORDS = (
    r"\?|"
    r"\b(crash|crashing|crashes|freeze|freezes|hang|hangs|stuck|error|failed|fails|black screen)\b|"
    r"\b(not working|doesnt work|doesn't work|wont work|won't work|cant open|can't open|wont open|won't open)\b|"
    r"\b(how to|how do|where to|help|fix|bypass|solution|solve|patch)\b|"
    r"\b(apk|apks|obb|rom|iso|pkg|fpkg|zip|rar|download|install|installing|extract|sai|split)\b|"
    r"\b(lag|lagging|fps|stutter|drop|performance|slow|overheat)\b|"
    r"\b(sd 855|sd855|snapdragon|adreno|mali|exynos|dimensity|ram|specs|support)\b|"
    r"\b(driver|turnip|vulkan|dxvk|opengl|glitch|graphics|texture|corrupted)\b|"
    r"\b(license|verification|google play|auth|password|key)\b"
)
troubleshoot_regex = re.compile(TROUBLESHOOT_KEYWORDS, re.IGNORECASE)

def is_user_authorized(user_id: int) -> bool:
    if not config.ALLOWED_USERS:
        return True
    return user_id in config.ALLOWED_USERS

def is_troubleshooting_query(text: str) -> bool:
    """Check if message in discussion group looks like an issue or complaint."""
    if not text or len(text.strip()) < 3:
        return False
    return bool(troubleshoot_regex.search(text))

async def send_solution(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: str,
    channel_context: str = "",
    parent_comment_context: str = "",
    is_nuke: bool = False
):
    """Query AI, send typing action, and reply with formatted 3-part layout."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not is_user_authorized(user.id if user else 0):
        await update.message.reply_text("⛔ Unauthorized access. Bot is in private whitelist mode.")
        return

    if not query.strip():
        await update.message.reply_text(
            "⚡ <b>THE CHEAT CODE:</b>\n"
            "<code>/cheat &lt;your problem or error message&gt;</code>\n\n"
            "🔍 <b>THE MECHANIC:</b>\n"
            "Command needs an argument to generate a bypass.\n\n"
            "💣 <b>THE OVERRIDE (Plan B):</b>\n"
            "Send any direct message without a command.",
            parse_mode=constants.ParseMode.HTML
        )
        return

    # Assemble contextual prompt if channel post or parent comment exists
    ai_input_parts = []
    if channel_context.strip():
        ai_input_parts.append(f"[CHANNEL POST CONTEXT]:\n{channel_context.strip()}")
    if parent_comment_context.strip():
        ai_input_parts.append(f"[PARENT COMMENT IN THREAD]:\n{parent_comment_context.strip()}")
    ai_input_parts.append(f"[USER COMPLAINT / QUESTION]:\n{query.strip()}")

    composite_query = "\n\n".join(ai_input_parts)

    # Keep sending typing action while awaiting AI response
    async def keep_typing():
        while True:
            try:
                await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
                await asyncio.sleep(4.0)
            except asyncio.CancelledError:
                break
            except Exception:
                break

    typing_task = asyncio.create_task(keep_typing())

    try:
        raw_solution = await ai_client.get_solution(composite_query, is_nuke=is_nuke)
    finally:
        typing_task.cancel()

    formatted_html = markdown_to_telegram_html(raw_solution)

    try:
        await update.message.reply_text(
            formatted_html,
            parse_mode=constants.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"reply_text failed ({e}), falling back to direct channel/group message.")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=formatted_html,
                parse_mode=constants.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                text=raw_solution,
                disable_web_page_preview=True
            )

# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "⚡ <b>CHEAT CODE BOT READY.</b>\n\n"
        "Direct-bypass systems engineer. Zero filler. Pure terminal one-liners, registry tweaks, APK/ROM fixes, and root bypasses.\n\n"
        "<b>USAGE:</b>\n"
        "• Send any error or glitch in DMs or discussion group comments\n"
        "• Automatically detects channel post context for games/APKs\n"
        "• <code>/cheat &lt;issue&gt;</code> — Quick 80/20 bypass\n"
        "• <code>/nuke &lt;issue&gt;</code> — Aggressive nuclear override\n"
        "• <code>/fix &lt;issue&gt;</code> — Immediate tactical repair\n"
        "• <code>/ping</code> — Status check\n\n"
        "<i>Tap any command block on mobile to copy directly to clipboard.</i>"
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)

async def cheat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    channel_ctx, parent_ctx = extract_message_contexts(update)
    await send_solution(update, context, query, channel_context=channel_ctx, parent_comment_context=parent_ctx, is_nuke=False)

async def fix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    channel_ctx, parent_ctx = extract_message_contexts(update)
    await send_solution(update, context, query, channel_context=channel_ctx, parent_comment_context=parent_ctx, is_nuke=False)

async def nuke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    channel_ctx, parent_ctx = extract_message_contexts(update)
    await send_solution(update, context, query, channel_context=channel_ctx, parent_comment_context=parent_ctx, is_nuke=True)

async def setkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_authorized(update.effective_user.id if update.effective_user else 0):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚡ <b>THE CHEAT CODE:</b>\n"
            "<code>/setkey &lt;your_groq_or_gemini_or_openai_api_key&gt;</code>\n\n"
            "🔍 <b>THE MECHANIC:</b>\n"
            "Automatically detects key format, hot-reloads engine, and writes to .env.\n\n"
            "💣 <b>THE OVERRIDE (Plan B):</b>\n"
            "Get free key in 10s: https://console.groq.com/keys",
            parse_mode=constants.ParseMode.HTML
        )
        return

    new_key = context.args[0].strip()
    ai_client.set_key(new_key)

    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "⚡ <b>THE CHEAT CODE:</b>\n"
            f"<code>API KEY HOT-LOADED [{config.AI_PROVIDER.upper()}]</code>\n\n"
            "🔍 <b>THE MECHANIC:</b>\n"
            f"Inference client connected to <code>{config.AI_MODEL}</code>.\n\n"
            "💣 <b>THE OVERRIDE (Plan B):</b>\n"
            "Send <code>/ping</code> to verify status."
        ),
        parse_mode=constants.ParseMode.HTML
    )

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key_configured = bool(config.get_api_key())
    status_text = (
        "⚡ <b>STATUS: OPERATIONAL</b>\n"
        f"• <b>Engine:</b> <code>{config.AI_MODEL}</code>\n"
        f"• <b>Provider:</b> <code>{config.AI_PROVIDER}</code>\n"
        f"• <b>Failover Key Pool:</b> <code>{ai_client.get_pool_status()}</code>\n"
        f"• <b>Discussion Group Auto-Reply:</b> {'<code>ACTIVE</code>' if config.AUTO_REPLY_GROUP_QUESTIONS else '<code>MENTIONS ONLY</code>'}\n"
        f"• <b>Cached Channel Threads:</b> <code>{len(channel_posts_cache)}</code>\n"
        "• <b>24/7 Watchdog:</b> <code>ACTIVE</code>"
    )
    await update.message.reply_text(status_text, parse_mode=constants.ParseMode.HTML)

def extract_message_contexts(update: Update) -> Tuple[str, str]:
    """Extract both the channel root post context and any replied comment context."""
    message = update.message
    if not message:
        return "", ""

    chat_id = message.chat_id
    channel_context = ""
    parent_comment_context = ""

    # 1. Check if user is replying directly to a message
    if message.reply_to_message:
        parent = message.reply_to_message
        parent_text = parent.text or parent.caption or ""

        # Check if parent is the original channel broadcast post
        is_parent_channel = (
            getattr(parent, "is_automatic_forward", False) or
            (parent.sender_chat and parent.sender_chat.type == "channel") or
            getattr(parent, "forward_from_chat", None) is not None
        )

        if is_parent_channel:
            channel_context = parent_text
        else:
            parent_comment_context = parent_text

    # 2. Check thread root post from memory cache
    thread_id = getattr(message, "message_thread_id", None)
    if not channel_context and thread_id and (chat_id, thread_id) in channel_posts_cache:
        channel_context = channel_posts_cache[(chat_id, thread_id)]

    return channel_context, parent_comment_context

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat = message.chat
    chat_id = chat.id
    text = (message.text or message.caption or "").strip()

    bot_user = context.bot
    bot_username = (bot_user.username or "").lower()
    is_mentioned = bool(bot_username and f"@{bot_username}" in text.lower())

    # Only treat as an automatic channel broadcast post if it is an actual system forward and does NOT mention the bot
    is_auto_broadcast = getattr(message, "is_automatic_forward", False) and not is_mentioned

    if is_auto_broadcast:
        # Cache this root post's text under its message_id (which is thread_id for all comments under it)
        channel_posts_cache[(chat_id, message.message_id)] = text
        logger.info(f"Cached channel broadcast post [{message.message_id}] in chat [{chat_id}]: {text[:60]}...")
        return  # Do not reply to the channel post itself

    # Ignore other bots
    if message.from_user and message.from_user.is_bot:
        return

    is_group = chat.type in ("group", "supergroup")

    sender_desc = "Unknown"
    if message.from_user:
        sender_desc = f"@{message.from_user.username or message.from_user.first_name}"
    elif message.sender_chat:
        sender_desc = f"Channel/Admin [{message.sender_chat.title or message.sender_chat.id}]"

    if is_group:
        logger.info(f"Incoming group message in [{chat.title or chat_id}] from {sender_desc}: {text[:80]}")

    # In 1-on-1 private chat: ALWAYS respond
    if not is_group:
        channel_ctx, parent_ctx = extract_message_contexts(update)
        await send_solution(update, context, text, channel_context=channel_ctx, parent_comment_context=parent_ctx, is_nuke=False)
        return

    # In Discussion Group:
    # Strip bot mention from text if present
    if is_mentioned:
        text = re.sub(rf"@{re.escape(bot_username)}", "", text, flags=re.IGNORECASE).strip()

    # Check if user replied directly to one of the bot's past messages
    is_reply_to_bot = False
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == bot_user.id:
            is_reply_to_bot = True

    # If configuration says ONLY reply when mentioned or replied to
    if config.REPLY_ONLY_WHEN_MENTIONED:
        if not (is_mentioned or is_reply_to_bot):
            return

    # If auto-replying to questions in discussion groups:
    # Only reply if user explicitly mentioned bot, replied to bot, OR asked a troubleshooting question/complaint
    if not (is_mentioned or is_reply_to_bot):
        if not config.AUTO_REPLY_GROUP_QUESTIONS:
            return
        if not is_troubleshooting_query(text):
            # Casual chatter ("haha stick with playing mate", "thanks", "nice") -> skip to prevent group spam
            return

    # Extract original channel post context and parent comment context early
    channel_ctx, parent_ctx = extract_message_contexts(update)

    # If user mentioned bot without text while replying to someone's question, use parent text as the query!
    if is_mentioned and not text and parent_ctx:
        text = parent_ctx

    if is_mentioned and (not text or text.lower() in ("ping", "/ping", "test", "alive")):
        await ping_command(update, context)
        return

    if is_mentioned and text.lower() in ("hi", "hello", "start", "/start", "help", "/help"):
        await start_command(update, context)
        return

    logger.info(f"Troubleshooting trigger in group [{chat.title or chat_id}] under context: {channel_ctx[:40]} | Query: {text[:60]}")
    await send_solution(
        update,
        context,
        text,
        channel_context=channel_ctx,
        parent_comment_context=parent_ctx,
        is_nuke=False
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler to prevent bot crash."""
    logger.error(f"Telegram Exception encountered: {context.error}")

async def post_init(application):
    """Background startup hooks."""
    await start_health_server()
    me = await application.bot.get_me()
    logger.info(f"Cheat Code Bot @{me.username} successfully initialized and monitoring discussion groups.")

def main():
    token = config.TELEGRAM_BOT_TOKEN
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("FATAL: TELEGRAM_BOT_TOKEN is not set in .env! Please configure your token.")
        print("\n[!] FATAL: TELEGRAM_BOT_TOKEN is missing in .env")
        print("    1. Open .env")
        print("    2. Set TELEGRAM_BOT_TOKEN=your_token_from_botfather")
        print("    3. Restart bot\n")
        sys.exit(1)

    app = ApplicationBuilder().token(token).post_init(post_init).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cheat", cheat_command))
    app.add_handler(CommandHandler("fix", fix_command))
    app.add_handler(CommandHandler("nuke", nuke_command))
    app.add_handler(CommandHandler("override", nuke_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("setkey", setkey_command))

    # Catch all text and media captions (no ~filters.COMMAND dead zone)
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, text_message_handler))

    app.add_error_handler(error_handler)

    logger.info(f"Starting long-polling with AI Model [{config.AI_MODEL}] on [{config.AI_PROVIDER}]...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
