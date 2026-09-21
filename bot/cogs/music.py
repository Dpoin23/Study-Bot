import asyncio
import os
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

import discord
from discord.ext import commands
from yt_dlp import YoutubeDL

from bot.views.playlist import PlaylistRemoveView, PlaylistSearchView
from bot.views.search import SearchView

# Stream URLs from YouTube stay valid for hours; refresh before this to be safe.
_SOURCE_TTL_SECONDS = 20 * 60
_PLAYLIST_ENQUEUE_CAP = 100
_PLAYLIST_SEARCH_LIMIT = 10
_REPO_ROOT = Path(__file__).resolve().parents[2]


def is_playlist_url(query: str) -> bool:
    """True for explicit playlist pages (not watch?v=…&list=…)."""
    q = (query or "").strip()
    if not q.lower().startswith("http"):
        return False
    lower = q.lower()
    return "list=" in lower and "/playlist" in lower


def playlist_url_from_query(query: str) -> str | None:
    """Canonical playlist URL if query contains a list= id."""
    q = (query or "").strip()
    if not q.lower().startswith("http"):
        return None
    list_ids = parse_qs(urlparse(q).query).get("list") or []
    if not list_ids:
        return None
    return f"https://www.youtube.com/playlist?list={list_ids[0]}"


def _ffmpeg_executable():
    explicit = os.getenv('FFMPEG_PATH')
    if explicit:
        return explicit
    local = _REPO_ROOT / 'bin' / 'ffmpeg'
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    on_path = shutil.which('ffmpeg')
    if on_path:
        return on_path
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _js_runtimes():
    runtimes = {}
    node = os.getenv('NODE_PATH') or shutil.which('node')
    if node:
        runtimes['node'] = {'path': node}
    deno = (
        os.getenv('DENO_PATH')
        or shutil.which('deno')
        or os.path.expanduser('~/.deno/bin/deno')
    )
    if deno and os.path.isfile(deno):
        runtimes['deno'] = {'path': deno}
    if not runtimes:
        runtimes['node'] = {}
    return runtimes

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
        self._play_locks = {}

        self.YTDL_OPTIONS = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'noprogress': True,
            'no_warnings': True,
            'skip_download': True,
            'socket_timeout': 15,
            'remote_components': ['ejs:github'],
            'js_runtimes': _js_runtimes(),
        }
        # Metadata only — do not resolve a stream URL for every search hit.
        self.YTDL_SEARCH_OPTIONS = {
            'quiet': True,
            'noprogress': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'socket_timeout': 15,
            'playlistend': 10,
        }
        # Flat metadata for playlist pages / playlist search results.
        self.YTDL_PLAYLIST_OPTIONS = {
            'quiet': True,
            'noprogress': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'noplaylist': False,
            'socket_timeout': 15,
            'playlistend': _PLAYLIST_ENQUEUE_CAP,
        }
        self.YTDL_PLAYLIST_SEARCH_OPTIONS = {
            'quiet': True,
            'noprogress': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'socket_timeout': 15,
            'playlistend': _PLAYLIST_SEARCH_LIMIT,
        }
        self.ffmpeg_executable = _ffmpeg_executable()
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
            'options': '-vn'
        }

        self.embedBlue = 0x2c76dd
        self.embedRed = 0xdf1141
        self.embedGreen = 0x0eaa51
        self.embedOrange = 0xFFA500

    # Listeners
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            id = int(guild.id)
            self.musicQueue[id] = []
            self.queueIndex[id] = 0
            self.vc[id] = None
            self._play_locks[id] = asyncio.Lock()
            self.isPaused[id] = self.isPlaying[id] = False

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        id = int(member.guild.id)
        if member.id != self.bot.user.id and before.channel is not None and after.channel != before.channel:
            remainingChannelMembers = before.channel.members
            if len(remainingChannelMembers) == 1 and remainingChannelMembers[0].id == self.bot.user.id and self.vc[id].is_connected():
                self.musicQueue[id] = []
                self.queueIndex[id] = 0
                self.isPaused[id] = self.isPlaying[id] = False
                await self.vc[id].disconnect()

    # Embed functions
    def now_playing_embed(self, ctx, song):
        title = song['title']
        link = song['link']
        thumbnail = song['thumbnail']
        author = ctx.author
        avatar = author.display_avatar.url

        embed = discord.Embed(
            title="Now Playing.",
            description=f'[{title}]({link})',
            colour=self.embedOrange
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"Song added by: {author!s}", icon_url=avatar)
        return embed
    
    def added_song_embed(self, ctx, song):
        title = song['title']
        link = song['link']
        thumbnail = song['thumbnail']
        author = ctx.author
        avatar = author.display_avatar.url

        embed = discord.Embed(
            title="Song Added to Queue.",
            description=f'[{title}]({link})',
            colour=self.embedBlue
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"Song added by: {author!s}", icon_url=avatar)
        return embed
    
    def removed_song_embed(self, ctx, song):
        title = song['title']
        link = song['link']
        thumbnail = song['thumbnail']
        author = ctx.author
        avatar = author.display_avatar.url

        embed = discord.Embed(
            title="Song Removed From Queue.",
            description=f'[{title}]({link})',
            colour=self.embedBlue
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"Song removed by: {author!s}", icon_url=avatar)
        return embed

    def added_playlist_embed(
        self, ctx, title, link, added, total, thumbnail=None
    ):
        author = ctx.author
        avatar = author.display_avatar.url
        cap_note = ""
        if total > added:
            cap_note = f" (first {added} of {total})"
        embed = discord.Embed(
            title="Playlist Added to Queue.",
            description=(
                f"[{title}]({link})\n"
                f"**{added}** track(s) added{cap_note}."
            ),
            colour=self.embedBlue,
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"Playlist added by: {author!s}", icon_url=avatar)
        return embed

    # Helper Functions
    async def join_vc(self, ctx, channel):
        id = int(ctx.guild.id)
        if self.vc[id] is None or not self.vc[id].is_connected():
            self.vc[id] = await channel.connect()

            if self.vc[id] is None:
                await ctx.send("Could not connect to the voice channel.")
                return
        
        else: 
            await self.vc[id].move_to(channel)

    def _play_lock(self, guild_id):
        gid = int(guild_id)
        lock = self._play_locks.get(gid)
        if lock is None:
            lock = asyncio.Lock()
            self._play_locks[gid] = lock
        return lock

    def _voice_client(self, guild_id):
        return self.vc.get(int(guild_id))

    def is_audio_playing(self, guild_id):
        vc = self._voice_client(guild_id)
        return vc is not None and vc.is_playing()

    def is_audio_paused(self, guild_id):
        vc = self._voice_client(guild_id)
        return vc is not None and vc.is_paused()

    def _start_source(self, ctx, song):
        id = int(ctx.guild.id)

        def after_play(error):
            if error:
                print(f"Playback error: {error}")
            self.play_next(ctx)

        self.vc[id].play(
            discord.FFmpegOpusAudio(
                song['source'],
                executable=self.ffmpeg_executable,
                **self.FFMPEG_OPTIONS,
            ),
            after=after_play,
        )
    
    def _watch_url(self, entry):
        video_id = entry.get('id')
        if video_id and len(str(video_id)) == 11:
            return f'https://www.youtube.com/watch?v={video_id}'
        url = entry.get('webpage_url') or entry.get('url') or ''
        if isinstance(url, str) and url.startswith('http'):
            return url
        if url and len(str(url)) == 11:
            return f'https://www.youtube.com/watch?v={url}'
        return url

    def _thumbnail_url(self, entry):
        thumbnail = entry.get('thumbnail')
        if thumbnail:
            return thumbnail
        thumbs = entry.get('thumbnails') or []
        if thumbs:
            return thumbs[-1].get('url')
        video_id = entry.get('id')
        if video_id and len(str(video_id)) == 11:
            return f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'
        return None

    def _source_is_fresh(self, song):
        if not song or not song.get('source'):
            return False
        extracted_at = song.get('extracted_at')
        if extracted_at is None:
            return False
        return (time.monotonic() - extracted_at) < _SOURCE_TTL_SECONDS

    def _ensure_stream(self, song):
        if self._source_is_fresh(song):
            return song
        return self.find_song(song['link'])

    def find_song(self, query):
        with YoutubeDL(self.YTDL_OPTIONS) as ydl:
            try:
                if query.startswith('http'):
                    info = ydl.extract_info(query, download=False)
                else:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                    entries = (info or {}).get('entries') or []
                    info = next((entry for entry in entries if entry), None)
                if not info:
                    return None
            except Exception as e:
                print(f"Error extracting song: {e}")
                return None
        stream = info.get('url')
        if not stream:
            return None
        return {
            'link': info.get('webpage_url') or self._watch_url(info),
            'thumbnail': self._thumbnail_url(info),
            'source': stream,
            'title': info.get('title') or 'Unknown title',
            'extracted_at': time.monotonic(),
        }

    def search_helper(self, search):
        with YoutubeDL(self.YTDL_SEARCH_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch10:{search}", download=False)
                entries = (info or {}).get('entries') or []
            except Exception as e:
                print(f"Error when trying to search: {e}")
                return None

        results = []
        for entry in entries:
            if not entry:
                continue
            title = entry.get('title')
            if not title:
                continue
            results.append({
                'link': self._watch_url(entry),
                'thumbnail': self._thumbnail_url(entry),
                'source': None,
                'title': title,
                'extracted_at': None,
            })
        return results or None

    def _playlist_link_from_entry(self, entry):
        link = entry.get('url') or entry.get('webpage_url') or ''
        if isinstance(link, str) and link.startswith('http') and 'list=' in link:
            return playlist_url_from_query(link) or link
        entry_id = entry.get('id')
        if entry_id:
            return f'https://www.youtube.com/playlist?list={entry_id}'
        return None

    def search_playlists_helper(self, search):
        query_url = (
            "https://www.youtube.com/results?"
            f"search_query={quote_plus(search)}&sp=EgIQAw%3D%3D"
        )
        with YoutubeDL(self.YTDL_PLAYLIST_SEARCH_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(query_url, download=False)
                entries = (info or {}).get('entries') or []
            except Exception as e:
                print(f"Error when trying to search playlists: {e}")
                return None

        results = []
        for entry in entries:
            if not entry:
                continue
            title = entry.get('title')
            link = self._playlist_link_from_entry(entry)
            if not title or not link:
                continue
            results.append({
                'link': link,
                'thumbnail': self._thumbnail_url(entry),
                'title': title,
                'id': entry.get('id'),
            })
            if len(results) >= _PLAYLIST_SEARCH_LIMIT:
                break
        return results or None

    def extract_playlist(self, playlist_url):
        with YoutubeDL(self.YTDL_PLAYLIST_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(playlist_url, download=False)
            except Exception as e:
                print(f"Error extracting playlist: {e}")
                return None
        if not info:
            return None

        entries = info.get('entries') or []
        tracks = []
        for entry in entries:
            if not entry:
                continue
            title = entry.get('title')
            if not title:
                continue
            link = self._watch_url(entry)
            if not link:
                continue
            tracks.append({
                'link': link,
                'thumbnail': self._thumbnail_url(entry),
                'source': None,
                'title': title,
                'extracted_at': None,
            })

        playlist_id = info.get('id')
        link = info.get('webpage_url') or playlist_url
        if playlist_id and 'list=' not in str(link):
            link = f'https://www.youtube.com/playlist?list={playlist_id}'
        return {
            'id': playlist_id,
            'title': info.get('title') or 'Playlist',
            'link': link,
            'thumbnail': self._thumbnail_url(info),
            'tracks': tracks,
            'total': len(tracks),
        }

    def queued_playlist_batches(self, guild_id):
        seen = {}
        order = []
        for song, _channel in self.musicQueue[int(guild_id)]:
            batch = song.get('playlist_batch')
            if not batch:
                continue
            if batch not in seen:
                seen[batch] = {
                    'batch': batch,
                    'playlist_id': song.get('playlist_id'),
                    'playlist_title': song.get('playlist_title') or 'Playlist',
                    'count': 0,
                }
                order.append(batch)
            seen[batch]['count'] += 1
        return [seen[batch] for batch in order]

    def _match_playlist_batches(self, guild_id, name_query):
        query = (name_query or '').strip().lower()
        batches = self.queued_playlist_batches(guild_id)
        if not query:
            return batches
        return [
            batch
            for batch in batches
            if query in batch['playlist_title'].lower()
        ]

    def _apply_playlist_removal(self, guild_id, batch_id):
        """Remove a playlist batch from the queue. Returns a summary dict."""
        gid = int(guild_id)
        queue = self.musicQueue[gid]
        current_index = self.queueIndex[gid]
        current_was_removed = False
        if 0 <= current_index < len(queue):
            current_was_removed = (
                queue[current_index][0].get('playlist_batch') == batch_id
            )

        removed_before = 0
        removed = 0
        title = 'Playlist'
        new_queue = []
        for i, item in enumerate(queue):
            song = item[0]
            if song.get('playlist_batch') == batch_id:
                removed += 1
                title = song.get('playlist_title') or title
                if i < current_index:
                    removed_before += 1
                continue
            new_queue.append(item)

        self.musicQueue[gid] = new_queue
        self.queueIndex[gid] = max(0, current_index - removed_before)
        if self.queueIndex[gid] > len(new_queue):
            self.queueIndex[gid] = len(new_queue)

        return {
            'removed': removed,
            'title': title,
            'current_was_removed': current_was_removed,
            'queue_empty': new_queue == [],
        }

    async def enqueue_playlist_url(self, ctx, playlist_url, *, start_playback):
        id = int(ctx.guild.id)
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You must be connected to a voice channel.")
            return None

        async with ctx.typing():
            playlist = await asyncio.to_thread(self.extract_playlist, playlist_url)
        if not playlist or not playlist['tracks']:
            return None

        user_channel = ctx.author.voice.channel
        batch_id = str(uuid.uuid4())
        tracks = playlist['tracks'][:_PLAYLIST_ENQUEUE_CAP]
        for track in tracks:
            track['playlist_id'] = playlist['id']
            track['playlist_title'] = playlist['title']
            track['playlist_batch'] = batch_id
            self.musicQueue[id].append([track, user_channel])

        result = {
            'title': playlist['title'],
            'link': playlist['link'],
            'thumbnail': playlist.get('thumbnail'),
            'added': len(tracks),
            'total': playlist['total'],
            'batch': batch_id,
        }

        if start_playback and not self.is_audio_playing(id):
            await self.play_music(ctx)
        return result

    async def _play_playlist_query(self, ctx, query):
        playlist_url = playlist_url_from_query(query)
        if playlist_url:
            result = await self.enqueue_playlist_url(
                ctx, playlist_url, start_playback=False
            )
            if result is None:
                await ctx.send("Could not load that playlist.")
                return
            message = self.added_playlist_embed(
                ctx,
                result['title'],
                result['link'],
                result['added'],
                result['total'],
                thumbnail=result.get('thumbnail'),
            )
            await ctx.send(embed=message)
            if not self.is_audio_playing(ctx.guild.id):
                await self.play_music(ctx)
            return

        async with ctx.typing():
            playlists = await asyncio.to_thread(
                self.search_playlists_helper, query
            )
        if not playlists:
            await ctx.send("No playlists matching your search.")
            return

        result = await self.enqueue_playlist_url(
            ctx, playlists[0]['link'], start_playback=False
        )
        if result is None:
            await ctx.send("Could not load that playlist.")
            return
        message = self.added_playlist_embed(
            ctx,
            result['title'],
            result['link'],
            result['added'],
            result['total'],
            thumbnail=result.get('thumbnail'),
        )
        await ctx.send(embed=message)
        if not self.is_audio_playing(ctx.guild.id):
            await self.play_music(ctx)

    async def _search_playlists(self, ctx, query):
        if not query:
            await ctx.send("You must specify playlist search terms.")
            return
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You must be connected to a voice channel.")
            return

        await ctx.send("Fetching playlist results . . .")
        async with ctx.typing():
            playlists = await asyncio.to_thread(
                self.search_playlists_helper, query
            )
        if not playlists:
            await ctx.send("No playlists matching your search.")
            return

        embed_text = ""
        for i, playlist in enumerate(playlists):
            embed_text += (
                f"{i + 1} - [{playlist['title']}]({playlist['link']})\n"
            )

        search_results = discord.Embed(
            title="Playlist Search Results",
            description=embed_text,
            color=self.embedBlue,
        )
        view = PlaylistSearchView(ctx, playlists, self, start_playback=True)
        message = await ctx.send(embed=search_results, view=view)
        view.message = message

    async def remove_playlist_batch(self, ctx, batch_id):
        id = int(ctx.guild.id)
        summary = self._apply_playlist_removal(id, batch_id)
        if summary['removed'] == 0:
            return summary

        if summary['queue_empty']:
            if self.vc.get(id) is not None and (
                self.isPlaying[id] or self.is_audio_playing(id) or self.is_audio_paused(id)
            ):
                self.isPlaying[id] = self.isPaused[id] = False
                if self.vc[id].is_playing() or self.vc[id].is_paused():
                    self.vc[id].stop()
                await self.vc[id].disconnect()
                self.vc[id] = None
            self.queueIndex[id] = 0
            return summary

        if summary['current_was_removed'] and self.vc.get(id) is not None:
            # Prevent the stop() after-callback from advancing the index again.
            self.isPlaying[id] = False
            self.isPaused[id] = False
            if self.vc[id].is_playing() or self.vc[id].is_paused():
                self.vc[id].stop()
            if self.queueIndex[id] < len(self.musicQueue[id]):
                await self.play_music(ctx)
        return summary

    async def _remove_playlist_command(self, ctx, *args):
        id = int(ctx.guild.id)
        name_query = " ".join(args).strip()
        batches = self._match_playlist_batches(id, name_query)
        if not batches:
            if name_query:
                await ctx.send("No queued playlist matched that name.")
            else:
                await ctx.send("There are no playlists in the queue to remove.")
            return

        if len(batches) == 1:
            summary = await self.remove_playlist_batch(ctx, batches[0]['batch'])
            removed = summary['removed']
            title = summary['title']
            embed = discord.Embed(
                title="Playlist Removed From Queue.",
                description=(
                    f"Removed **{removed}** track(s) from **{title}**."
                ),
                color=self.embedBlue,
            )
            await ctx.send(embed=embed)
            return

        embed_text = ""
        for i, batch in enumerate(batches):
            embed_text += (
                f"{i + 1} - **{batch['playlist_title']}** "
                f"({batch['count']} track(s))\n"
            )
        embed = discord.Embed(
            title="Queued Playlists",
            description=embed_text,
            color=self.embedBlue,
        )
        view = PlaylistRemoveView(ctx, batches, self)
        message = await ctx.send(embed=embed, view=view)
        view.message = message
    
    def play_next(self, ctx):
        id = int(ctx.guild.id)
        if not self.isPlaying[id]:
            return
        if self.queueIndex[id] + 1 < len(self.musicQueue[id]):
            self.isPlaying[id] = True
            self.queueIndex[id] += 1
            
            song = self.musicQueue[id][self.queueIndex[id]][0]
            fresh = self._ensure_stream(song)
            if fresh:
                song = fresh
                self.musicQueue[id][self.queueIndex[id]][0] = fresh
            elif not song.get('source'):
                self.isPlaying[id] = False
                return
            message = self.now_playing_embed(ctx, song)
            coroutine = ctx.send(embed=message)
            var = asyncio.run_coroutine_threadsafe(coroutine, self.bot.loop)
            try:
                var.result()
            except Exception as e:
                print(f"Error: {e}")
            self._start_source(ctx, song)
        else:
            self.queueIndex[id] += 1
            self.isPlaying[id] = False

    # Other Async Functions
    async def play_music(self, ctx):
        id = int(ctx.guild.id)
        async with self._play_lock(id):
            if self.is_audio_playing(id):
                return
            if self.queueIndex[id] < len(self.musicQueue[id]):
                self.isPlaying[id] = True
                self.isPaused[id] = False

                await self.join_vc(ctx, self.musicQueue[id][self.queueIndex[id]][1])
                if self.vc.get(id) is None:
                    self.isPlaying[id] = False
                    return

                song = self.musicQueue[id][self.queueIndex[id]][0]
                async with ctx.typing():
                    fresh = await asyncio.to_thread(self._ensure_stream, song)
                if fresh:
                    song = fresh
                    self.musicQueue[id][self.queueIndex[id]][0] = fresh
                elif not song.get('source'):
                    await ctx.send("Could not get a playable audio stream.")
                    self.isPlaying[id] = False
                    return

                message = self.now_playing_embed(ctx, song)
                await ctx.send(embed=message)
                self._start_source(ctx, song)
            else:
                await ctx.send("There are no songs in the queue.")
                self.queueIndex[id] += 1
                self.isPlaying[id] = False

    # Commands
    @commands.command(
        name="play",
        aliases=['pl'],
        help="Play a song (or playlist page URL), or resume if paused"
    )
    async def play(self, ctx, *args):
        search = " ".join(args)
        id = int(ctx.guild.id)
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You must be connected to a voice channel to play music.")
            return
        userChannel = ctx.author.voice.channel
        if not args:
            if len(self.musicQueue[id]) == 0:
                await ctx.send("There are no songs in the queue.")
                return
            if self.is_audio_paused(id):
                self.isPaused[id] = False
                self.isPlaying[id] = True
                self.vc[id].resume()
                return
            if not self.is_audio_playing(id):
                await self.play_music(ctx)
            return
        else:
            if is_playlist_url(search):
                await self._play_playlist_query(ctx, search)
                return
            async with ctx.typing():
                song = await asyncio.to_thread(self.find_song, search)
            if song is None:
                await ctx.send("Could not download the song, incorrect format, try a different search.")
            else:
                self.musicQueue[id].append([song, userChannel])

                if not self.is_audio_playing(id):
                    await self.play_music(ctx)
                else:
                    message = self.added_song_embed(ctx, song)
                    await ctx.send(embed=message)

    @commands.command(
        name='playlist',
        aliases=['plist', 'pllist'],
        help="Play a YouTube playlist from a search or URL"
    )
    async def playlist(self, ctx, *args):
        if not args:
            await ctx.send("Please specify a playlist search or URL.")
            return
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You must be connected to a voice channel to play music.")
            return
        await self._play_playlist_query(ctx, " ".join(args))

    @commands.command(
        name='add',
        aliases=['a', '+'],
        help="Add a song to the queue without starting playback"
    )
    async def add(self, ctx, *args):
        search = " ".join(args)
        id = int(ctx.guild.id)
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You must be connected to a voice channel to play music.")
            return
        userChannel = ctx.author.voice.channel
        if not args:
            await ctx.send("Please specify a song to add.")
        else:
            async with ctx.typing():
                song = await asyncio.to_thread(self.find_song, search)
            if song is None:
                await ctx.send("Could not download the song, incorrect format, try a different search.")
            else:
                self.musicQueue[id].append([song, userChannel])
                message = self.added_song_embed(ctx, song)
                await ctx.send(embed=message)

    @commands.command(
        name='remove',
        aliases=['rm'],
        help="Remove the last song, or a playlist with `!remove playlist [name]`"
    )
    async def remove(self, ctx, *args):
        if args and args[0].lower() == 'playlist':
            await self._remove_playlist_command(ctx, *args[1:])
            return

        id = int(ctx.guild.id)
        if self.musicQueue[id] != []:
            song = self.musicQueue[id][-1][0]
            removeSongEmbed = self.removed_song_embed(ctx, song)
            await ctx.send(embed=removeSongEmbed)
        else:
            await ctx.send("There are no songs to remove from the queue.")
        self.musicQueue[id] = self.musicQueue[id][:-1]
        if self.musicQueue[id] == []:
            if self.vc[id] is not None and self.isPlaying[id]:
                self.isPlaying[id] = self.isPaused[id] = False
                await self.vc[id].disconnect()
                self.vc[id] = None
            self.queueIndex[id] = 0
        elif self.queueIndex[id] == len(self.musicQueue[id]) and self.vc[id] is not None and self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] -= 1
            await self.play_music(ctx)

    @commands.command(
        name='removeplaylist',
        aliases=['rmpl', 'rmplaylist'],
        help="Remove a queued playlist's tracks (picker, or match by name)"
    )
    async def removeplaylist(self, ctx, *args):
        await self._remove_playlist_command(ctx, *args)

    @commands.command(
        name="search",
        aliases=['se', 'find'],
        help="Search YouTube videos, or playlists with `!search playlist <name>`"
    )
    async def search(self, ctx, *args):
        if args and args[0].lower() == 'playlist':
            await self._search_playlists(ctx, " ".join(args[1:]))
            return

        search = " ".join(args)
        embedText = ""
        
        if not args:
            await ctx.send("You must specify search terms.")
            return
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You must be connected to a voice channel.")
            return

        await ctx.send("Fetching search results . . .")

        async with ctx.typing():
            songs = await asyncio.to_thread(self.search_helper, search)
        if not songs:
            await ctx.send("No results matching your search.")
            return
    
        for i, song in enumerate(songs):
            embedText += f"{i + 1} - [{song['title']}]({song['link']})\n"

        searchResults = discord.Embed(
            title="Search Results",
            description=embedText,
            color=self.embedBlue
        )

        view = SearchView(ctx, songs, self)
        message = await ctx.send(embed=searchResults, view=view)
        view.message = message

    @commands.command(
        name="pause",
        aliases=['stop'],
        help="Pause the song that is currently playing"
    )
    async def pause(self, ctx):
        id = int(ctx.guild.id)
        if not self.vc[id]:
            await ctx.send("There is no audio being played at the moment.")
        elif self.isPlaying[id]:
            await ctx.send("Audio paused.")
            self.isPlaying[id] = False
            self.isPaused[id] = True
            self.vc[id].pause()
        else:
            await ctx.send("There is no audio being played at the moment.")

    @commands.command(
        name='resume',
        aliases=['re', 'start'],
        help="Resume playback if the song is paused"
    )
    async def resume(self, ctx):
        id = int(ctx.guild.id)
        if not self.vc[id]:
            await ctx.send("There is no paused audio at the moment.")
        elif self.isPaused[id]:
            await ctx.send("Audio resumed.")
            self.isPaused[id] = False
            self.isPlaying[id] = True
            self.vc[id].resume()
        elif self.isPlaying[id]:
            await ctx.send("Audio is currently being played.")
        else:
            await ctx.send("Encountered and error when attempting to resume.")

    @commands.command(
        name='previous',
        aliases=['pr', 'prev'],
        help="Go back to the previous song in the queue"
    )
    async def previous(self, ctx):
        id = int(ctx.guild.id)
        if self.vc[id] is None:
            await ctx.send("You need to be in a voice channel to use previous.")
        elif self.queueIndex[id] <= 0:
            await ctx.send("There is no previous song in the queue, replaying current song.")
            self.vc[id].pause()
            await self.play_music(ctx)
        elif self.vc[id] is not None and self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] -= 1
            await self.play_music(ctx)

    @commands.command(
        name='skip',
        aliases=['sk', 'next'],
        help="Skip to the next song in the queue"
    )
    async def skip(self, ctx):
        id = int(ctx.guild.id)
        if self.vc[id] is None:
            await ctx.send("You need to be in a voice channel to use skip.")
        elif self.queueIndex[id] >= len(self.musicQueue[id]) - 1:
            await ctx.send("There is no next song in the queue.")
        elif self.vc[id] is not None and self.vc[id]:
            self.vc[id].pause()
            self.queueIndex[id] += 1
            await self.play_music(ctx)
    
    @commands.command(
        name='replay',
        aliases=['rep'],
        help="Replay the current song from the beginning"
    )
    async def replay(self, ctx):
        id = int(ctx.guild.id)
        if self.vc[id] is None:
            await ctx.send("You need to be in a voice channel to replay a song.")
        elif self.musicQueue[id] == []:
            await ctx.send("There are no songs to replay.")
        elif self.vc[id] is not None and self.vc[id] and self.queueIndex[id] == len(self.musicQueue[id]):
            self.queueIndex[id] -= 1
            await self.play_music(ctx)
        elif self.vc[id] is not None and self.vc[id] and self.isPaused[id]:
            await self.play_music(ctx)
        elif self.vc[id] is not None and self.vc[id]:
            self.vc[id].pause()
            await self.play_music(ctx) 

    @commands.command(
        name='queue',
        aliases=['q', 'list'],
        help="Show the songs currently in the queue"
    )
    async def queue(self, ctx):
        id = int(ctx.guild.id)
        returnValue = ""
        if self.musicQueue[id] == []:
            await ctx.send("There are no songs in the queue.")
            return
        
        for i in range(self.queueIndex[id], len(self.musicQueue[id])):
            nextSongs = len(self.musicQueue[id]) - self.queueIndex[id]
            if i > 5 + nextSongs:
                break
            returnIndex = i - self.queueIndex[id]
            if returnIndex == 0 and self.isPlaying[id]:
                returnIndex = "Playing"
            elif returnIndex == 1 and self.isPlaying[id]:
                returnIndex = "Next"
            else:
                returnIndex += 1
            returnValue += f"{returnIndex} - [{self.musicQueue[id][i][0]['title']}]({self.musicQueue[id][i][0]['link']})\n"

            if returnValue == "":
                await ctx.send("There are no songs in the queue.")
                return
        
        queue = discord.Embed(
            title="Current Queue",
            description=returnValue,
            color=self.embedGreen
        )
        await ctx.send(embed=queue)

    @commands.command(
        name='clear',
        aliases=['cl', 'removeall'],
        help="Clear every song from the queue and stop playback"
    )
    async def clear(self, ctx):
        id = int(ctx.guild.id)
        if self.vc[id] is not None and self.isPlaying[id]:
            self.isPlaying[id] = self.isPaused[id] = False
            self.vc[id].stop()
        if self.musicQueue[id] != []:
            await ctx.send("Music queue cleared.")
            self.musicQueue[id] = []
        self.queueIndex[id] = 0
            
    @commands.command(
        name="join",
        aliases=['j'],
        help="Join the voice channel you are currently in"
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
        help="Leave the voice channel and clear the queue"
    )
    async def leave(self, ctx):
        id = int(ctx.guild.id)
        self.musicQueue[id] = []
        self.queueIndex[id] = 0
        self.isPaused[id] = self.isPlaying[id] = False
        if self.vc[id] is not None:
            await ctx.send(f"Study bot has left {ctx.author.voice.channel}")
            await self.vc[id].disconnect()
            self.vc[id] = None
