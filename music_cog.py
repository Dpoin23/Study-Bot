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

# guild represents the server

class music_cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # index using the server id each server should have its own queue, song, etc.
        self.isPlaying = {}
        self.isPaused = {}
        self.musicQueue = {}
        # don't have to use this, but queue index stores the index of the location
        # in the queue for that server, this would support playback functionality,
        # but could also implement the queue just by popping from the front once the
        # song is over
        self.queueIndex = {}

        # status for whether or not the bot is in the voice channel or not
        self.vc = {}

        self.YTDL_OPTIONS = {'format': 'bestaudio', 'nonplaylist': 'True'}
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
            'options': '-vn'
        }

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            id = int(guild.id)
            self.musicQueue[id] = []
            self.queueIndex[id] = 0
            self.vc[id] = None
            self.isPaused[id] = self.isPlaying[id] = False

    async def join_vc(self, ctx, channel):
        id = int(ctx.guild.id)
        if self.vc[id] == None or not self.vc[id].is_connected():
            self.vc[id] = await channel.connect()

            if self.vc[id] == None:
                await ctx.send("Could not connect to the voice channel.")
                return
        
        else: 
            await self.vc[id].move_to(channel)
    
    def search_yt(self, search):
        queryString = parse.urlencode({"search_query": search})
        htmContent =  request.urlopen('http://www.youtube.com/results?' + queryString)
        searchResults = re.findall('/watch\?v=(.{11})', htmContent.read().decode())
        return searchResults[:10]

    def extract_yt(self, url):
        with YoutubeDL(self.YTDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except:
                return False
        return {
            'link': 'https://www.youtube.com/watch?v=' + url,
            'thumbnail': 'https://i.ytimg.com/vi/' + url + '/hqdefault.jpg?sqp=-oaymwEcCOADEI4CSFXyq4qpAw4IARUAAIhCGAFwAcABBg==&rs=AOn4CLD5uL4xKN-IUfez6KIW_j5y70mlig',
            'source': info['formats'][0]['url'],
            'title': info['title']
        }