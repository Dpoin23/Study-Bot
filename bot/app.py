"""Bot construction and Discord gateway entry."""

from __future__ import annotations

import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from bot.cogs.admin import AdminCog
from bot.cogs.help import HelpCog
from bot.cogs.music import MusicCog


class StudyBot(commands.Bot):
    async def setup_hook(self):
        await self.add_cog(MusicCog(self))
        await self.add_cog(AdminCog(self))
        await self.add_cog(HelpCog(self))


def create_bot() -> StudyBot:
    load_dotenv()

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = StudyBot(command_prefix='!', intents=intents)
    bot.remove_command('help')

    @bot.listen('on_command_error')
    async def notify_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        original = getattr(error, 'original', error)
        try:
            await ctx.send(f'Command failed: {original}')
        except Exception:
            logger.error(f'Error sending command error to {ctx.author.name}: {error}')

    return bot


def run() -> None:
    token = os.getenv('DISCORD_TOKEN')
    handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    create_bot().run(token, log_handler=handler, log_level=logging.DEBUG)
