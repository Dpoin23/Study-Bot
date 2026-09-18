import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from admin_cog import AdminCog
from help_cog import HelpCog
from music_cog import MusicCog

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class MyBot(commands.Bot):
    async def setup_hook(self):
        await self.add_cog(MusicCog(self))
        await self.add_cog(AdminCog(self))
        await self.add_cog(HelpCog(self))


bot = MyBot(command_prefix='!', intents=intents)

bot.remove_command('help')


@bot.listen('on_command_error')
async def notify_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    original = getattr(error, 'original', error)
    try:
        await ctx.send(f'Command failed: {original}')
    except Exception:
        pass


if __name__ == '__main__':
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)
