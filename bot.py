"""Cheat Code Telegram Bot - Tactical direct-bypass troubleshooting bot for DMs and Discussion Groups."""
import asyncio
import logging
import os
import re
import signal
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
from health_server import start_health_server, attach_log_capture

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
attach_log_capture(logger)


# Cache channel posts in memory: (chat_id, message_thread_id / root_post_id) -> post text/caption
channel_posts_cache: Dict[Tuple[int, int], str] = {}

# Strict troubleshooting keyword patterns
TROUBLESHOOT_KEYWORDS = (
    r"\b(crash|crashing|crashes|freeze|freezes|hang|hangs|stuck|black screen)\b|"
    r"\b(not working|doesnt work|doesn't work|wont work|won't work|cant open|can't open|wont open|won't open)\b|"
    r"\b(how to install|where to put|how to fix|how to bypass|how to run|how to use)\b|"
    r"\b(apk|apks|obb|rom|iso|pkg|fpkg|zip|extract|sai|split)\b|"
    r"\b(lag|lagging|fps|stutter|drop fps|overheat)\b|"
    r"\b(sd 855|sd855|snapdragon|adreno|mali|exynos|dimensity)\b|"
    r"\b(turnip driver|vulkan|dxvk|opengl error)\b|"
    r"\b(license verification|google play error)\b"
)
troubleshoot_regex = re.compile(TROUBLESHOOT_KEYWORDS, re.IGNORECASE)

# Short conversational phrases that must NEVER trigger the bot unsummoned
CONVERSATIONAL_NOISE = {
    "got it", "got it?", "ok", "ok?", "okay", "okay?", "why", "why?",
    "what", "what?", "how", "how?", "who", "who?", "where", "where?",
    "you there?", "thanks", "thank you", "nice", "lol", "lmao", "yes", "no"
}

def is_user_authorized(user_id: int, sender_chat=None) -> bool:
    if not config.ALLOWED_USERS:
        return True
    if sender_chat is not None or user_id in (0, 1087968824, 777000):
        return True
    return user_id in config.ALLOWED_USERS


def is_troubleshooting_query(text: str) -> bool:
    """Check if message in discussion group looks like an actual technical issue."""
    cleaned = text.strip().lower()
    if len(cleaned) < 10:
        return False
    if cleaned in CONVERSATIONAL_NOISE:
        return False
    return bool(troubleshoot_regex.search(cleaned))

async def send_solution(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: str,
    channel_context: str = "",
    parent_comment_context: str = "",
    is_nuke: bool = False
):
    """Query AI, send typing action, and reply with formatted 3-part layout."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return

    chat_id = chat.id
    thread_id = getattr(message, "message_thread_id", None)
    user = update.effective_user
    sender_chat = getattr(message, "sender_chat", None)

    if not is_user_authorized(user.id if user else 0, sender_chat=sender_chat):
        try:
            await message.reply_text("⛔ Unauthorized access. Bot is in private whitelist mode.")
        except Exception:
            pass
        return

    if not query.strip():
        fallback_msg = (
            "⚡ <b>THE CHEAT CODE:</b>\n"
            "<code>/cheat &lt;your problem or error message&gt;</code>\n\n"
            "🔍 <b>THE MECHANIC:</b>\n"
            "Command needs an issue to generate a bypass.\n\n"
            "💣 <b>THE OVERRIDE (Plan B):</b>\n"
            "Send any error text or tag @Stfu0911_bot with your question."
        )
        try:
            await message.reply_text(fallback_msg, parse_mode=constants.ParseMode.HTML)
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id,
                text=fallback_msg,
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
                await context.bot.send_chat_action(chat_id=chat_id, message_thread_id=thread_id, action=constants.ChatAction.TYPING)
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

    # Safe reply with automatic thread and plain-text fallback
    try:
        await message.reply_text(
            formatted_html,
            parse_mode=constants.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"reply_text failed ({e}), falling back to direct send_message with thread_id={thread_id}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id,
                text=formatted_html,
                parse_mode=constants.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e2:
            logger.warning(f"send_message with HTML failed ({e2}), falling back to plain text")
            await context.bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id,
                text=raw_solution,
                disable_web_page_preview=True
            )

# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    thread_id = getattr(message, "message_thread_id", None)

    msg = (
        "⚡ <b>CHEAT CODE BOT READY.</b>\n\n"
        "Direct-bypass systems engineer. Zero filler. Pure terminal one-liners, registry tweaks, APK/ROM fixes, and root bypasses.\n\n"
        "<b>USAGE:</b>\n"
        "• Send any error or glitch in DMs or discussion group comments\n"
        "• Tag <code>@Stfu0911_bot</code> or reply to any message\n"
        "• <code>/cheat &lt;issue&gt;</code> — Quick 80/20 bypass\n"
        "• <code>/nuke &lt;issue&gt;</code> — Aggressive nuclear override\n"
        "• <code>/fix &lt;issue&gt;</code> — Immediate tactical repair\n"
        "• <code>/ping</code> — Status check\n\n"
        "<i>Tap any command block on mobile to copy directly to clipboard.</i>"
    )
    try:
        await message.reply_text(msg, parse_mode=constants.ParseMode.HTML)
    except Exception:
        await context.bot.send_message(chat_id=chat.id, message_thread_id=thread_id, text=msg, parse_mode=constants.ParseMode.HTML)

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
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    thread_id = getattr(message, "message_thread_id", None)

    if not is_user_authorized(update.effective_user.id if update.effective_user else 0, sender_chat=getattr(message, "sender_chat", None)):
        await message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        help_msg = (
            "⚡ <b>THE CHEAT CODE:</b>\n"
            "<code>/setkey &lt;your_groq_or_gemini_or_openai_api_key&gt;</code>\n\n"
            "🔍 <b>THE MECHANIC:</b>\n"
            "Automatically detects key format, hot-reloads engine, and writes to .env.\n\n"
            "💣 <b>THE OVERRIDE (Plan B):</b>\n"
            "Get free key in 10s: https://console.groq.com/keys"
        )
        try:
            await message.reply_text(help_msg, parse_mode=constants.ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=chat.id, message_thread_id=thread_id, text=help_msg, parse_mode=constants.ParseMode.HTML)
        return

    new_key = context.args[0].strip()
    ai_client.set_key(new_key)

    try:
        await message.delete()
    except Exception:
        pass

    success_msg = (
        "⚡ <b>THE CHEAT CODE:</b>\n"
        f"<code>API KEY HOT-LOADED [{config.AI_PROVIDER.upper()}]</code>\n\n"
        "🔍 <b>THE MECHANIC:</b>\n"
        f"Inference client connected to <code>{config.AI_MODEL}</code>.\n\n"
        "💣 <b>THE OVERRIDE (Plan B):</b>\n"
        "Send <code>/ping</code> to verify status."
    )
    await context.bot.send_message(
        chat_id=chat.id,
        message_thread_id=thread_id,
        text=success_msg,
        parse_mode=constants.ParseMode.HTML
    )

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return
    thread_id = getattr(message, "message_thread_id", None)

    status_text = (
        "⚡ <b>STATUS: OPERATIONAL</b>\n"
        f"• <b>Engine:</b> <code>{config.AI_MODEL}</code>\n"
        f"• <b>Provider:</b> <code>{config.AI_PROVIDER}</code>\n"
        f"• <b>Failover Key Pool:</b> <code>{ai_client.get_pool_status()}</code>\n"
        f"• <b>Discussion Group Auto-Reply:</b> {'<code>ACTIVE</code>' if config.AUTO_REPLY_GROUP_QUESTIONS else '<code>MENTIONS ONLY</code>'}\n"
        f"• <b>Cached Channel Threads:</b> <code>{len(channel_posts_cache)}</code>\n"
        "• <b>24/7 Cloud Host:</b> <code>RENDER (ACTIVE)</code>"
    )
    try:
        await message.reply_text(status_text, parse_mode=constants.ParseMode.HTML)
    except Exception:
        await context.bot.send_message(chat_id=chat.id, message_thread_id=thread_id, text=status_text, parse_mode=constants.ParseMode.HTML)

def extract_message_contexts(update: Update) -> Tuple[str, str]:
    """Extract both the channel root post context and any replied comment context."""
    message = update.effective_message
    if not message:
        return "", ""

    chat_id = update.effective_chat.id if update.effective_chat else 0
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
            thread_id = getattr(message, "message_thread_id", None)
            if thread_id:
                channel_posts_cache[(chat_id, thread_id)] = channel_context
        else:
            parent_comment_context = parent_text

    # 2. Check thread root post from memory cache
    thread_id = getattr(message, "message_thread_id", None)
    if not channel_context and thread_id and (chat_id, thread_id) in channel_posts_cache:
        channel_context = channel_posts_cache[(chat_id, thread_id)]

    return channel_context, parent_comment_context

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    chat = update.effective_chat
    if not chat:
        return
    chat_id = chat.id
    text = (message.text or message.caption or "").strip()

    bot_user = context.bot
    bot_username = (bot_user.username or "Stfu0911_bot").lower()

    # 1. Regex text mention check (matches @Stfu0911_bot, Stfu0911_bot, @Stfu0911_bot:, etc.)
    is_mentioned = bool(re.search(rf"@?{re.escape(bot_username)}\b", text, re.IGNORECASE))

    # 2. Telegram entities (both message.entities and message.caption_entities)
    all_entities = list(message.entities or []) + list(message.caption_entities or [])
    if not is_mentioned and all_entities:
        for ent in all_entities:
            if ent.type == "mention":
                mention_str = text[ent.offset : ent.offset + ent.length].lower().lstrip("@")
                if mention_str == bot_username:
                    is_mentioned = True
                    break
            elif ent.type == "text_mention" and ent.user and ent.user.id == bot_user.id:
                is_mentioned = True
                break

    # 3. Only treat as an automatic channel broadcast post if it is a pure automated system forward AND does NOT mention bot
    is_auto_broadcast = getattr(message, "is_automatic_forward", False) and not is_mentioned

    if is_auto_broadcast:
        # Cache this root post's text under its message_id (which is thread_id for all comments under it)
        channel_posts_cache[(chat_id, message.message_id)] = text
        logger.info(f"Cached channel broadcast post [{message.message_id}] in chat [{chat_id}]: {text[:60]}...")
        return  # Do not reply to the automated channel broadcast itself

    # Ignore third-party bots (NEVER ignore GroupAnonymousBot ID 1087968824 or Telegram service ID 777000)
    if message.from_user and message.from_user.is_bot:
        is_anonymous_admin = (
            message.from_user.id in (1087968824, 777000) or
            message.from_user.username == "GroupAnonymousBot" or
            getattr(message, "sender_chat", None) is not None
        )
        if not is_anonymous_admin:
            return

    is_group = chat.type in ("group", "supergroup", "channel")

    sender_desc = "Unknown"
    if getattr(message, "sender_chat", None):
        sender_desc = f"Anonymous Admin / Channel [{message.sender_chat.title or message.sender_chat.id}]"
    elif message.from_user:
        if message.from_user.id == 1087968824 or message.from_user.username == "GroupAnonymousBot":
            sender_desc = f"Anonymous Admin ({chat.title or chat_id})"
        else:
            sender_desc = f"@{message.from_user.username or message.from_user.first_name}"

    if is_group:
        logger.info(f"Incoming group/channel message in [{chat.title or chat_id}] from {sender_desc} (Mentioned: {is_mentioned}): {text[:80]}")


    # In 1-on-1 private chat: ALWAYS respond
    if not is_group:
        channel_ctx, parent_ctx = extract_message_contexts(update)
        await send_solution(update, context, text, channel_context=channel_ctx, parent_comment_context=parent_ctx, is_nuke=False)
        return

    # In Discussion Group / Channel:
    # Check if user replied directly to one of the bot's past messages
    is_reply_to_bot = False
    if message.reply_to_message:
        parent = message.reply_to_message
        if (parent.from_user and parent.from_user.id == bot_user.id) or (parent.sender_chat and parent.sender_chat.id == bot_user.id):
            is_reply_to_bot = True

    # If not mentioned and not reply to bot:
    if not (is_mentioned or is_reply_to_bot):
        if config.REPLY_ONLY_WHEN_MENTIONED:
            return
        if not config.AUTO_REPLY_GROUP_QUESTIONS:
            return
        if not is_troubleshooting_query(text):
            # Casual chatter -> skip to prevent group spam
            return

    # Extract original channel post context and parent comment context early
    channel_ctx, parent_ctx = extract_message_contexts(update)

    # Strip bot mention from text if present
    cleaned_query = text
    if is_mentioned:
        cleaned_query = re.sub(rf"@?{re.escape(bot_username)}\b", "", cleaned_query, flags=re.IGNORECASE).strip()
        cleaned_query = re.sub(r"^[\s,:\-]+", "", cleaned_query).strip()

    # If user mentioned bot without question while replying to someone's question, use parent text as the query!
    if is_mentioned and not cleaned_query and parent_ctx:
        cleaned_query = parent_ctx

    # If user just mentioned bot with nothing else or greetings
    if is_mentioned and (not cleaned_query or cleaned_query.lower() in ("ping", "/ping", "test", "alive")):
        await ping_command(update, context)
        return

    if is_mentioned and cleaned_query.lower() in ("hi", "hello", "start", "/start", "help", "/help"):
        await start_command(update, context)
        return

    logger.info(f"Troubleshooting trigger in [{chat.title or chat_id}] under context: {channel_ctx[:40]} | Query: {cleaned_query[:60]}")
    await send_solution(
        update,
        context,
        cleaned_query,
        channel_context=channel_ctx,
        parent_comment_context=parent_ctx,
        is_nuke=False
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler to prevent bot crash."""
    logger.error(f"Telegram Exception encountered: {context.error}")

async def run_bot():
    token = config.TELEGRAM_BOT_TOKEN
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("FATAL: TELEGRAM_BOT_TOKEN is not set in .env! Please configure your token.")
        sys.exit(1)

    app = ApplicationBuilder().token(token).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cheat", cheat_command))
    app.add_handler(CommandHandler("fix", fix_command))
    app.add_handler(CommandHandler("nuke", nuke_command))
    app.add_handler(CommandHandler("override", nuke_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("setkey", setkey_command))

    # Catch all text and media captions (including channel posts)
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, text_message_handler))
    app.add_error_handler(error_handler)

    # Initialize and start PTB Application
    await app.initialize()
    await app.start()
    me = await app.bot.get_me()
    logger.info(f"Cheat Code Bot @{me.username} (ID: {me.id}) fully initialized.")

    base_url = os.getenv(
        "RENDER_EXTERNAL_URL",
        os.getenv("WEBHOOK_BASE_URL", "https://cheatcode-telegram-bot.onrender.com")
    ).rstrip("/")

    # Detect if we should run in Webhook mode (Render cloud environment)
    is_render = bool(os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_URL") or os.getenv("PORT"))

    if is_render:
        webhook_url = f"{base_url}/webhook"
        logger.info(f"Deploying in Telegram Webhook Mode for Render: {webhook_url}")
        try:
            await app.bot.set_webhook(
                url=webhook_url,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False
            )
            logger.info(f"Telegram Webhook successfully set to: {webhook_url}")
        except Exception as e:
            logger.error(f"Failed to set Telegram webhook: {e}")

        runner = await start_health_server(telegram_app=app, webhook_mode=True, webhook_url=webhook_url)

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
            if sig is not None:
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except NotImplementedError:
                    pass

        try:
            await stop_event.wait()
        finally:
            logger.info("Shutting down Webhook server...")
            if runner:
                await runner.cleanup()
            await app.stop()
            await app.shutdown()
    else:
        # Long-polling mode for local development
        logger.info("Deploying in Long-Polling Mode (Local Dev)...")
        try:
            await app.bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            pass

        runner = await start_health_server(telegram_app=app, webhook_mode=False)

        async with app:
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
                if sig is not None:
                    try:
                        loop.add_signal_handler(sig, stop_event.set)
                    except NotImplementedError:
                        pass
            try:
                await stop_event.wait()
            finally:
                logger.info("Stopping polling...")
                if runner:
                    await runner.cleanup()

def main():
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Cheat Code Bot process terminated.")

if __name__ == "__main__":
    main()
