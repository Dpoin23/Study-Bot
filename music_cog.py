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
from yt_dlp import YoutubeDL

# guild represents the server

class MusicCog(commands.Cog):
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

        self.YTDL_OPTIONS = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'js_runtimes': {
                'node': {
                    'path': r'C:\Program Files\nodejs\node.exe'
                }
            },
            'remote_components': {
                'ejs': 'github'
            }
        }
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
            'options': '-vn'
        }

        self.embedBlue = 0x2c76dd
        self.embedRed = 0xdf1141
        self.embedGreen = 0x0eaa51
        self.embedOrange = 0xFFA500

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            id = int(guild.id)
            self.musicQueue[id] = []
            self.queueIndex[id] = 0
            self.vc[id] = None
            self.isPaused[id] = self.isPlaying[id] = False

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        id = int(member.guild.id)
        if member.id != self.bot.user.id and before.channel != None and after.channel != before.channel:
            remainingChannelMembers = before.channel.members
            if len(remainingChannelMembers) == 1 and remainingChannelMembers[0].id == self.bot.user.id and self.vc[id].is_connected():
                self.musicQueue[id] = []
                self.queueIndex[id] = 0
                self.isPaused[id] = self.isPlaying[id] = False
                await self.vc[id].disconnect()
    
    def now_playing_embed(self, ctx, song):
        title = song['title']
        link = song['link']
        thumbnail = song['thumbnail']
        author = ctx.author
        avatar = author.display_avatar.url

        embed = discord.Embed(
            title="Now Playing",
            description=f'[{title}]({link})',
            colour=self.embedOrange
        )
        embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"Song added by: {str(author)}", icon_url=avatar)
        return embed

    async def join_vc(self, ctx, channel):
        id = int(ctx.guild.id)
        if self.vc[id] == None or not self.vc[id].is_connected():
            self.vc[id] = await channel.connect()

            if self.vc[id] == None:
                await ctx.send("Could not connect to the voice channel.")
                return
        
        else: 
            await self.vc[id].move_to(channel)
    
    def find_song(self, query):
        with YoutubeDL(self.YTDL_OPTIONS) as ydl:
            try:
                if query.startswith('http'):
                    info = ydl.extract_info(query, download=False)
                else:
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)
                    info = info['entries'][0]
            except:
                return None
        return {
            'link': info['webpage_url'],
            'thumbnail': info.get('thumbnail'),
            'source': info['url'],
            'title': info['title']
        }
    
    def play_next(self, ctx):
        id = int(ctx.guild.id)
        if not self.isPlaying[id]:
            return
        if self.queueIndex[id] + 1 < len(self.musicQueue[id]):
            self.isPlaying[id] = True
            self.queueIndex[id] += 1
            
            song = self.musicQueue[id][self.queueIndex[id]][0]
            message = self.now_playing_embed(ctx, song)
            coroutine = ctx.send(embed=message)
            var = run_coroutine_threadsafe(coroutine, self.bot.loop)
            try:
                var.result()
            except Exception as e:
                print(f"Error: {e}")

            self.vc[id].play(discord.FFmpegPCMAudio(
                song['source'], **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(ctx))
        else:
            self.queueIndex[id] += 1
            self.isPlaying[id] = False

    async def play_music(self, ctx):
        id = int(ctx.guild.id)
        if self.queueIndex[id] < len(self.musicQueue[id]):
            self.isPlaying[id] = True
            self.isPaused[id] = False

            await self.join_vc(ctx, self.musicQueue[id][self.queueIndex[id]][1])

            song = self.musicQueue[id][self.queueIndex[id]][0]
            message = self.now_playing_embed(ctx, song)
            await ctx.send(embed=message)

            self.vc[id].play(discord.FFmpegPCMAudio(
                song['source'], **self.FFMPEG_OPTIONS), after=lambda e: self.play_next(ctx))
        else:
            await ctx.send("There are no songs in the queue.")
            self.queueIndex[id] += 1
            self.isPlaying[id] = False

    @commands.command(
        name="play",
        aliases=['pl'],
        help=""
    )
    async def play(self, ctx, *args):
        search = " ".join(args)
        id = int(ctx.guild.id)
        try:
            userChannel = ctx.author.voice.channel
        except:
            await ctx.send("You must be connected to a voice channel to play music.")
            return
        if not args:
            if len(self.musicQueue[id]) == 0:
                await ctx.send("There are no songs in the queue.")
                return
            elif not self.isPlaying[id]:
                if self.musicQueue[id] == None or self.vc[id] == None:
                    await self.play_music(ctx)
                else:
                    self.isPaused[id] = False
                    self.isPlaying[id] = True
                    self.vc[id].resume()
            else:
                return
        else:
            song = self.find_song(search)
            if song is None:
                await ctx.send("Could not download the song, incorrect format, try a different search.")
            else:
                self.musicQueue[id].append([song, userChannel])

                if not self.isPlaying[id]:
                    await self.play_music(ctx)
                else:
                    message = ""
                    await ctx.send(message)

    @commands.command(
        name="pause",
        aliases=['p'],
        help=""
    )
    async def pause(self, ctx):
        pass

    @commands.command(
        name='resume',
        aliases=['r'],
        help=''
    )
    async def resume(self, ctx):
        pass
            
    @commands.command(
        name="join",
        aliases=['j'],
        help=""
    )
    async def join(self, ctx):
        if ctx.author.voice:
            userChannel = ctx.author.voice.channel
            await self.join_vc(ctx, userChannel)
            await ctx.send(f'Study Bot has joined {userChannel}')
        else:
            await ctx.send("You need to be connected to a voice channel.")

    @commands.command(
        name="leave",
        aliases=['l'],
        help=""
    )
    async def leave(self, ctx):
        id = int(ctx.guild.id)
        self.musicQueue[id] = []
        self.queueIndex[id] = 0
        self.isPaused[id] = self.isPlaying[id] = False
        if self.vc[id] != None:
            userChannel = ctx.author.voice.channel
            await ctx.send(f"Study bot has left {userChannel}")
            await self.vc[id].disconnect()