"""Study session timer with voice lock-in warnings."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import discord
from discord.ext import commands

_DEFAULT_MINUTES = 25
_MIN_MINUTES = 1
_MAX_MINUTES = 180


def parse_study_minutes(raw: str | None) -> int:
    """Parse a minutes argument; blank uses the default Pomodoro length."""
    if raw is None or str(raw).strip() == "":
        return _DEFAULT_MINUTES
    try:
        minutes = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("Minutes must be a whole number.") from exc
    if minutes < _MIN_MINUTES or minutes > _MAX_MINUTES:
        raise ValueError(f"Minutes must be between {_MIN_MINUTES} and {_MAX_MINUTES}.")
    return minutes


def format_duration(seconds: float) -> str:
    """Format a positive duration as `Xh Ym Zs` (omitting zero units)."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or hours:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


@dataclass
class StudySession:
    user_id: int
    guild_id: int
    text_channel_id: int
    voice_channel_id: int
    duration_seconds: int
    started_at: float
    end_at: float
    task: asyncio.Task | None = field(default=None, repr=False)

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.end_at - time.monotonic())


class StudyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, StudySession] = {}
        self.embedBlue = 0x2c76dd
        self.embedOrange = 0xFFA500
        self.embedRed = 0xdf1141
        self.embedGreen = 0x0eaa51

    def cog_unload(self):
        for session in list(self.sessions.values()):
            if session.task and not session.task.done():
                session.task.cancel()
        self.sessions.clear()

    def _active_session(self, user_id: int) -> StudySession | None:
        return self.sessions.get(user_id)

    async def _announce(self, session: StudySession, embed: discord.Embed) -> None:
        channel = self.bot.get_channel(session.text_channel_id)
        if channel is not None:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

        user = self.bot.get_user(session.user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(session.user_id)
            except discord.HTTPException:
                return
        try:
            await user.send(embed=embed)
        except discord.HTTPException:
            pass

    async def _finish_session(self, session: StudySession, *, completed: bool) -> None:
        current = self.sessions.get(session.user_id)
        if current is not session:
            return
        self.sessions.pop(session.user_id, None)

        if completed:
            embed = discord.Embed(
                title="Study session complete",
                description=(
                    f"Nice work — your **{format_duration(session.duration_seconds)}** "
                    "session is done. Take a short break, then start another with `!study`."
                ),
                color=self.embedGreen,
            )
        else:
            remaining = format_duration(session.remaining_seconds)
            embed = discord.Embed(
                title="Study session ended",
                description=f"Session stopped early with **{remaining}** left.",
                color=self.embedOrange,
            )
        await self._announce(session, embed)

    async def _session_timer(self, session: StudySession) -> None:
        try:
            await asyncio.sleep(session.duration_seconds)
        except asyncio.CancelledError:
            return
        await self._finish_session(session, completed=True)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot:
            return

        session = self._active_session(member.id)
        if session is None or session.guild_id != member.guild.id:
            return

        left_study_channel = (
            before.channel is not None
            and before.channel.id == session.voice_channel_id
            and (after.channel is None or after.channel.id != session.voice_channel_id)
        )
        if not left_study_channel:
            return

        elapsed = format_duration(time.monotonic() - session.started_at)
        remaining = format_duration(session.remaining_seconds)
        channel_name = before.channel.name if before.channel else "the study channel"
        embed = discord.Embed(
            title="Left mid-session",
            description=(
                f"You left **{channel_name}** during an active study session.\n"
                f"Elapsed: **{elapsed}** · Remaining: **{remaining}**\n\n"
                "Rejoin the voice channel to stay locked in, or use `!studyend` to stop."
            ),
            color=self.embedRed,
        )
        await self._announce(session, embed)

    @commands.command(
        name="study",
        aliases=["focus", "pomodoro"],
        help="Start a study timer (default 25 min). Stay in voice or get a leave warning.",
    )
    async def study(self, ctx: commands.Context, minutes: str | None = None):
        if ctx.guild is None:
            await ctx.send("Study sessions can only be started in a server.")
            return

        if self._active_session(ctx.author.id) is not None:
            await ctx.send("You already have an active study session. Use `!studystatus` or `!studyend`.")
            return

        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.send("Join a voice channel first so lock-in warnings can track if you leave.")
            return

        try:
            duration_minutes = parse_study_minutes(minutes)
        except ValueError as exc:
            await ctx.send(str(exc))
            return

        duration_seconds = duration_minutes * 60
        now = time.monotonic()
        session = StudySession(
            user_id=ctx.author.id,
            guild_id=ctx.guild.id,
            text_channel_id=ctx.channel.id,
            voice_channel_id=ctx.author.voice.channel.id,
            duration_seconds=duration_seconds,
            started_at=now,
            end_at=now + duration_seconds,
        )
        session.task = asyncio.create_task(self._session_timer(session))
        self.sessions[ctx.author.id] = session

        embed = discord.Embed(
            title="Study session started",
            description=(
                f"**{duration_minutes} min** timer is running.\n"
                f"Locked into **{ctx.author.voice.channel.name}** — leaving mid-session "
                "sends a warning.\n"
                "Use `!studystatus` to check time left, or `!studyend` to stop early."
            ),
            color=self.embedBlue,
        )
        await ctx.send(embed=embed)

    @commands.command(
        name="studyend",
        aliases=["endstudy", "endfocus", "studystop"],
        help="End your active study session early",
    )
    async def studyend(self, ctx: commands.Context):
        session = self._active_session(ctx.author.id)
        if session is None:
            await ctx.send("You do not have an active study session.")
            return

        task = session.task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._finish_session(session, completed=False)

    @commands.command(
        name="studystatus",
        aliases=["studytimer", "focusstatus"],
        help="Show time remaining on your study session",
    )
    async def studystatus(self, ctx: commands.Context):
        session = self._active_session(ctx.author.id)
        if session is None:
            await ctx.send("You do not have an active study session. Start one with `!study`.")
            return

        voice = self.bot.get_channel(session.voice_channel_id)
        voice_name = voice.name if isinstance(voice, discord.VoiceChannel) else "your study channel"
        embed = discord.Embed(
            title="Study session status",
            description=(
                f"Remaining: **{format_duration(session.remaining_seconds)}**\n"
                f"Total length: **{format_duration(session.duration_seconds)}**\n"
                f"Lock-in channel: **{voice_name}**"
            ),
            color=self.embedOrange,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(StudyCog(bot))
