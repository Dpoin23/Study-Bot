"""Bot construction and Discord gateway entry."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from bot.cogs.admin import AdminCog
from bot.cogs.help import HelpCog
from bot.cogs.music import MusicCog
from bot.cogs.study import StudyCog

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_PATH = _REPO_ROOT / ".env"
_PLACEHOLDER_TOKEN = "your_bot_token_here"


def load_environment() -> None:
    """Load `.env` from the repo root (works even if cwd is elsewhere)."""
    load_dotenv(_ENV_PATH)


def get_discord_token() -> str:
    """Return a configured Discord bot token, or raise ValueError if missing."""
    load_environment()
    token = (os.getenv("DISCORD_TOKEN") or "").strip()
    if not token or token == _PLACEHOLDER_TOKEN:
        raise ValueError(
            "DISCORD_TOKEN is missing or still the placeholder. "
            "Copy .env.example to .env and set your bot token."
        )
    return token


class StudyBot(commands.Bot):
    async def setup_hook(self):
        await self.add_cog(MusicCog(self))
        await self.add_cog(StudyCog(self))
        await self.add_cog(AdminCog(self))
        await self.add_cog(HelpCog(self))


def create_bot() -> StudyBot:
    load_environment()

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = StudyBot(command_prefix="!", intents=intents)
    bot.remove_command("help")

    @bot.listen("on_command_error")
    async def notify_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        original = getattr(error, "original", error)
        try:
            await ctx.send(f"Command failed: {original}")
        except Exception:
            logger.error(f"Error sending command error to {ctx.author.name}: {error}")

    return bot


def run() -> None:
    try:
        token = get_discord_token()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
    create_bot().run(token, log_handler=handler, log_level=logging.DEBUG)
