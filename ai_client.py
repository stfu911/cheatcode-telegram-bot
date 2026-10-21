import os
import re
import logging
from typing import Optional
from openai import AsyncOpenAI
import config
from prompts import CHEATCODE_SYSTEM_PROMPT, NUKE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class CheatCodeAIClient:
    def __init__(self):
        self.api_keys = config.get_api_keys()
        self.current_key_idx = 0
        self.base_url = config.AI_BASE_URL
        self.model = config.AI_MODEL
        self.temperature = config.AI_TEMPERATURE
        self.max_tokens = config.AI_MAX_TOKENS
        self.client: Optional[AsyncOpenAI] = None
        self._init_client()

    def _init_client(self):
        if not self.api_keys:
            self.client = None
        else:
            active_key = self.api_keys[self.current_key_idx % len(self.api_keys)]
            self.client = AsyncOpenAI(
                api_key=active_key,
                base_url=self.base_url
            )

    def reload(self):
        """Reload configuration dynamically if keys change."""
        self.api_keys = config.get_api_keys()
        self.base_url, self.model = config.get_api_config()
        self._init_client()

    def get_pool_status(self) -> str:
        if not self.api_keys:
            return "0 keys"
        idx = (self.current_key_idx % len(self.api_keys)) + 1
        return f"{len(self.api_keys)} keys active (Current: #{idx})"

    def set_key(self, new_key: str, provider: str = None):
        """Add or set key in runtime and persist to .env."""
        new_key = new_key.strip()
        if provider:
            config.AI_PROVIDER = provider.lower().strip()
        elif new_key.startswith("gsk_"):
            config.AI_PROVIDER = "groq"
        elif new_key.startswith("AIzaSy"):
            config.AI_PROVIDER = "gemini"
        elif new_key.startswith("sk-"):
            config.AI_PROVIDER = "openai"

        # If key already exists in pool, do nothing; else append or set
        if new_key not in self.api_keys:
            self.api_keys.append(new_key)
            keys_str = ",".join(self.api_keys)
            if config.AI_PROVIDER == "groq":
                config.GROQ_API_KEY = keys_str
            elif config.AI_PROVIDER == "gemini":
                config.GEMINI_API_KEY = keys_str
            elif config.AI_PROVIDER == "openai":
                config.OPENAI_API_KEY = keys_str
            self._persist_env(keys_str, config.AI_PROVIDER)

        self.reload()

    def _persist_env(self, key_str: str, provider: str):
        try:
            env_path = ".env"
            content = ""
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
            
            # Update provider
            if "AI_PROVIDER=" in content:
                content = re.sub(r"AI_PROVIDER=.*", f"AI_PROVIDER={provider}", content)
            else:
                content += f"\nAI_PROVIDER={provider}"

            # Update key
            if provider == "groq":
                key_var = "GROQ_API_KEY"
            elif provider == "gemini":
                key_var = "GEMINI_API_KEY"
            else:
                key_var = "OPENAI_API_KEY"

            if f"{key_var}=" in content:
                content = re.sub(rf"{key_var}=.*", f"{key_var}={key_str}", content)
            else:
                content += f"\n{key_var}={key_str}"

            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to persist .env: {e}")

    def _get_offline_cheatcode(self, q: str) -> Optional[str]:
        """Built-in tactical one-liners for instant offline response."""
        ql = q.lower()
        if any(w in ql for w in ("wifi", "wi-fi", "internet", "dns", "no internet")):
            return (
                "⚡ THE CHEAT CODE:\n"
                "`ipconfig /flushdns && ipconfig /renew`\n\n"
                "🔍 THE MECHANIC:\n"
                "Flushes stale local DNS lookup table and forces DHCP lease handshake with gateway.\n\n"
                "💣 THE OVERRIDE (Plan B):\n"
                "`netsh int ip reset && netsh winsock reset`\n"
                "*(Reboot required)*"
            )
        if any(w in ql for w in ("port", "in use", "eaddrinuse", "address already in use")):
            return (
                "⚡ THE CHEAT CODE:\n"
                "`netstat -ano | findstr :<PORT>` then `taskkill /PID <PID> /F`\n\n"
                "🔍 THE MECHANIC:\n"
                "Finds owner process holding socket lock and issues uncatchable SIGKILL to kernel.\n\n"
                "💣 THE OVERRIDE (Plan B):\n"
                "`Stop-Process -Id (Get-NetTCPConnection -LocalPort <PORT>).OwningProcess -Force`"
            )
        if any(w in ql for w in ("frozen", "freeze", "kill", "not responding", "hang")):
            return (
                "⚡ THE CHEAT CODE:\n"
                "`taskkill /F /FI \"STATUS eq NOT RESPONDING\"`\n\n"
                "🔍 THE MECHANIC:\n"
                "Queries Windows window manager queue and purges all deadlocked application threads.\n\n"
                "💣 THE OVERRIDE (Plan B):\n"
                "`Get-Process | Where-Object { -not $_.Responding } | Stop-Process -Force`"
            )
        if any(w in ql for w in ("git", "revert", "undo", "commit")):
            return (
                "⚡ THE CHEAT CODE:\n"
                "`git reset --soft HEAD~1`\n\n"
                "🔍 THE MECHANIC:\n"
                "Rewinds commit pointer by 1 commit while preserving all uncommitted changes in working tree.\n\n"
                "💣 THE OVERRIDE (Plan B):\n"
                "`git reset --hard HEAD~1`"
            )
        if any(w in ql for w in ("disk", "space", "storage", "temp")):
            return (
                "⚡ THE CHEAT CODE:\n"
                "`cleanmgr /sageset:1 && cleanmgr /sagerun:1`\n\n"
                "🔍 THE MECHANIC:\n"
                "Automates Windows Disk Cleanup system cache and Windows.old purging routines.\n\n"
                "💣 THE OVERRIDE (Plan B):\n"
                "`del /q/f/s %TEMP%\\*`"
            )
        return None

    async def get_solution(self, user_query: str, is_nuke: bool = False) -> str:
        """Call AI provider with automatic multi-key failover."""
        if not self.api_keys:
            self.reload()

        if not self.api_keys:
            offline = self._get_offline_cheatcode(user_query)
            if offline:
                return offline
            return (
                "⚡ THE CHEAT CODE:\n"
                "`/setkey gsk_YourGroqKeyHere`\n\n"
                "🔍 THE MECHANIC:\n"
                "AI engine requires inference API key to generate real-time bypasses.\n\n"
                "💣 THE OVERRIDE (Plan B):\n"
                "Get free key in 10s at https://console.groq.com/keys"
            )

        system_prompt = NUKE_SYSTEM_PROMPT if is_nuke else CHEATCODE_SYSTEM_PROMPT
        max_attempts = len(self.api_keys)
        last_error = ""

        # Failover loop across all keys in pool
        for attempt in range(max_attempts):
            idx = (self.current_key_idx + attempt) % len(self.api_keys)
            active_key = self.api_keys[idx]
            masked_key = f"{active_key[:8]}...{active_key[-4:]}"

            try:
                client = AsyncOpenAI(
                    api_key=active_key,
                    base_url=self.base_url
                )
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_query},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                # Successful call: make this active index for next time
                self.current_key_idx = idx
                content = response.choices[0].message.content
                return (content or "").strip()
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"AI Key [{masked_key}] failed ({e}). "
                    f"Auto-switching to next key ({attempt + 1}/{max_attempts})..."
                )

        logger.error(f"All {max_attempts} keys in failover pool exhausted. Last error: {last_error}")
        return (
            "⚡ THE CHEAT CODE:\n"
            f"`All {len(self.api_keys)} API keys in pool exhausted: {last_error[:120]}`\n\n"
            "🔍 THE MECHANIC:\n"
            "Every connected API key hit rate limits, quota caps, or network errors.\n\n"
            "💣 THE OVERRIDE (Plan B):\n"
            "`Add another free key with /setkey gsk_...`"
        )

ai_client = CheatCodeAIClient()
