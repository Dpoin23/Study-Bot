import discord
from discord.ext import commands
import os

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot