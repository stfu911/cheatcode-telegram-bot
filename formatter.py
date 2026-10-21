"""Formatting utilities for Telegram messages with tap-to-copy support."""
import html
import re

def markdown_to_telegram_html(text: str) -> str:
    """Convert AI markdown output to Telegram-compatible HTML with tap-to-copy code."""
    # First, protect fenced code blocks ```lang\ncode\n```
    code_blocks = []
    
    def repl_code_block(match):
        code_content = match.group(2)
        escaped_code = html.escape(code_content.strip("\r\n"))
        token = f"___CODEBLOCK_{len(code_blocks)}___"
        # pre + code enables tap-to-copy on Telegram mobile
        code_blocks.append(f"<pre><code>{escaped_code}</code></pre>")
        return token

    # Extract fenced code blocks
    pattern_block = re.compile(r"```([a-zA-Z0-9_\-\+]*)\n?(.*?)```", re.DOTALL)
    text = pattern_block.sub(repl_code_block, text)

    # Protect inline code `code`
    inline_codes = []
    def repl_inline_code(match):
        inline_content = match.group(1)
        escaped_inline = html.escape(inline_content)
        token = f"___INLINECODE_{len(inline_codes)}___"
        # Inline code is tap-to-copy on Telegram
        inline_codes.append(f"<code>{escaped_inline}</code>")
        return token

    pattern_inline = re.compile(r"`([^`]+)`")
    text = pattern_inline.sub(repl_inline_code, text)

    # HTML escape standard text so <, >, & do not break Telegram parser
    text = html.escape(text)

    # Convert bold **text** or *text*
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    # Convert italic _text_
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<i>\1</i>", text)

    # Put back inline code blocks
    for i, icode in enumerate(inline_codes):
        text = text.replace(f"___INLINECODE_{i}___", icode)

    # Put back fenced code blocks
    for i, cblock in enumerate(code_blocks):
        text = text.replace(f"___CODEBLOCK_{i}___", cblock)

    # Ensure header symbols look clean and bold
    text = text.replace("⚡ THE CHEAT CODE:", "⚡ <b>THE CHEAT CODE:</b>")
    text = text.replace("🔍 THE MECHANIC:", "🔍 <b>THE MECHANIC:</b>")
    text = text.replace("💣 THE OVERRIDE (Plan B):", "💣 <b>THE OVERRIDE (Plan B):</b>")

    return text
