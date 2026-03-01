import discord
from discord.ui import Select, Button
from discord import SelectOption
from discord.ext import commands
import asyncio
from asyncio import run_coroutine_threadsafe
from urllib import parse, request
import re
import json
import os
from youtube_dl import YoutubeDL

class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot