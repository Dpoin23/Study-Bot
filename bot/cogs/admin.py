from discord.ext import commands


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
