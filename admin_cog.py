import discord
from discord.ext import commands
import logging
import os

class admin_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot