import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

from music_cog import MusicCog
from help_cog import HelpCog
from admin_cog import AdminCog

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.og', encoding='utf-8', mode='w')
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

DEV = "Developer"
MEM = "Member"
ADM = "Admin"

bot.run(token, log_handler=handler, log_level=logging.DEBUG)