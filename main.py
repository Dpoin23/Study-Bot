import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

from music_cog import MusicCog
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

bot = MyBot(command_prefix='!', intents=intents)

secretRole = "Developer"
regularRole = "Member"
topRole = "Admin"

"""@bot.event
async def on_ready():
    print(f'Ready to go: {bot.user.name}')

@bot.event
async def on_member_join(member):
    await member.send(f"Welcome to the server {member.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return 
    
    if "shit" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} don't use that word")

    await bot.process_commands(message)

@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}!")

@bot.command()
async def assign_admin(ctx):
    role = discord.utils.get(ctx.guild.roles, name=top_role)
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"{ctx.author.mention} is now assigned to {top_role}")
    else:
        await ctx.send("Role doesn't exist")

@bot.command()
async def assign_worker(ctx):
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"{ctx.author.mention} is now assigned to {secret_role}")
    else:
        await ctx.send("Role doesn't exist")

@bot.command()
async def assign_member(ctx):
    role = discord.utils.get(ctx.guild.roles, name=regular_role)
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"{ctx.author.mention} is now assigned to {regular_role}")
    else:
        await ctx.send("Role doesn't exist")

@bot.command()
async def remove_worker(ctx):
    role = discord.utils.get(ctx.guild.roles, name=regular_role)
    if role:
        await ctx.author.remove_roles(regular_role)
        await ctx.send(f"{ctx.author.mention} has had their {regular_role} role removed")
    else:
        await ctx.send("Role doesn't exist")

@bot.command()
async def dm(ctx, *, msg):
    await ctx.author.send(f"You said {msg}")

@bot.command()
async def reply(ctx):
    await ctx.reply("This is a reply to your message.")

@bot.command()
async def poll(ctx, *, msg):
    embed = discord.Embed(title="New Poll", description=msg)
    poll_message = await ctx.send(embed=embed)
    await poll_message.add_reaction("👍")
    await poll_message.add_reaction("😊")


@bot.command()
@commands.has_role(secret_role)
async def secret(ctx):
    await ctx.send('Welcome to the club!')

@bot.command()
async def join():
    pass

@bot.command()
async def play():
    pass

@bot.command()
async def skip():
    pass

@bot.command()
async def playback():
    pass

@bot.command()
async def stop():
    pass

@secret.error()
async def secret_error(ctx, err):
    if isinstance(err, commands.MissingRole):
        await ctx.send("You do not have the proper permissions.")"""

bot.run(token, log_handler=handler, log_level=logging.DEBUG)