"""Test script for formatter and prompt structure."""
import sys
import io

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from formatter import markdown_to_telegram_html
from prompts import CHEATCODE_SYSTEM_PROMPT, NUKE_SYSTEM_PROMPT

sample_ai_output = """⚡ THE CHEAT CODE:
Flush your DNS cache and renew the DHCP lease in one shot. Open Terminal / PowerShell as Admin and paste:
```bash
ipconfig /flushdns && ipconfig /renew
```

🔍 THE MECHANIC:
Your machine has an IP address assigned by the router, but its local DNS resolver or gateway routing table is stalled on an expired handshake.

💣 THE OVERRIDE (Plan B):
If the lease fails, force a network stack reset:
```bash
netsh int ip reset && netsh winsock reset
```
Reboot immediately."""

html_output = markdown_to_telegram_html(sample_ai_output)
print("=== GENERATED HTML ===")
print(html_output)
print("\n=== CHECKS ===")
assert "⚡ <b>THE CHEAT CODE:</b>" in html_output
assert "<pre><code>ipconfig /flushdns &amp;&amp; ipconfig /renew</code></pre>" in html_output
assert "🔍 <b>THE MECHANIC:</b>" in html_output
assert "💣 <b>THE OVERRIDE (Plan B):</b>" in html_output
print("All formatter checks passed successfully!")
