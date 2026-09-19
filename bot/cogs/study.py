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
_TIMER_TICK_SECONDS = 15
_STUDY_CHANNEL_NAMES = ("study", "study-chat", "studychat")
_FALLBACK_CHANNEL_NAMES = ("general", "chat", "lounge")


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


def find_text_channel_by_names(channels, names: tuple[str, ...]):
    """Return the first text channel whose name matches (case-insensitive)."""
    wanted = {name.lower() for name in names}
    for channel in channels:
        if channel.name.lower() in wanted:
            return channel
    return None


@dataclass
class StudySession:
    user_id: int
    guild_id: int
    text_channel_id: int
    voice_channel_id: int
    duration_seconds: int
    started_at: float
    end_at: float
    timer_message_id: int | None = None
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

    def _can_send(self, channel: discord.TextChannel) -> bool:
        me = channel.guild.me
        if me is None:
            return False
        perms = channel.permissions_for(me)
        return perms.view_channel and perms.send_messages and perms.embed_links

    async def _resolve_study_channel(
        self,
        guild: discord.Guild,
        fallback: discord.TextChannel,
    ) -> discord.TextChannel:
        """Prefer #study (create if allowed), else general-like names, else fallback."""
        existing = find_text_channel_by_names(list(guild.text_channels), _STUDY_CHANNEL_NAMES)
        if existing is not None and self._can_send(existing):
            return existing

        me = guild.me
        if me is not None and me.guild_permissions.manage_channels:
            try:
                created = await guild.create_text_channel(
                    "study",
                    reason="Study Bot study chat for session timers",
                )
                return created
            except discord.HTTPException:
                pass

        candidate = find_text_channel_by_names(
            list(guild.text_channels),
            _FALLBACK_CHANNEL_NAMES,
        )
        if candidate is not None and self._can_send(candidate):
            return candidate

        if guild.system_channel is not None and self._can_send(guild.system_channel):
            return guild.system_channel

        for channel in guild.text_channels:
            if self._can_send(channel):
                return channel

        return fallback

    def _timer_embed(self, session: StudySession, *, status: str = "active") -> discord.Embed:
        member_mention = f"<@{session.user_id}>"
        voice = self.bot.get_channel(session.voice_channel_id)
        voice_name = voice.name if isinstance(voice, discord.VoiceChannel) else "voice"
        remaining = format_duration(session.remaining_seconds)
        total = format_duration(session.duration_seconds)
        elapsed = format_duration(time.monotonic() - session.started_at)

        if status == "complete":
            return discord.Embed(
                title="Study session complete",
                description=(
                    f"{member_mention} finished a **{total}** session.\n"
                    "Start another with `!study`."
                ),
                color=self.embedGreen,
            )
        if status == "ended":
            return discord.Embed(
                title="Study session ended",
                description=(
                    f"{member_mention} stopped early with **{remaining}** left."
                ),
                color=self.embedOrange,
            )

        return discord.Embed(
            title="Study timer",
            description=(
                f"{member_mention} is studying.\n\n"
                f"**Remaining:** {remaining}\n"
                f"**Elapsed:** {elapsed} / {total}\n"
                f"**Lock-in:** {voice_name}\n\n"
                "Leaving the voice channel mid-session triggers a warning.\n"
                "Stop early with `!studyend`."
            ),
            color=self.embedBlue,
        )

    async def _edit_timer_message(
        self,
        session: StudySession,
        *,
        status: str = "active",
    ) -> None:
        if session.timer_message_id is None:
            return
        channel = self.bot.get_channel(session.text_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(session.timer_message_id)
            await message.edit(embed=self._timer_embed(session, status=status))
        except discord.HTTPException:
            pass

    async def _announce(self, session: StudySession, embed: discord.Embed) -> None:
        channel = self.bot.get_channel(session.text_channel_id)
        if isinstance(channel, discord.TextChannel):
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

        status = "complete" if completed else "ended"
        await self._edit_timer_message(session, status=status)

    async def _session_timer(self, session: StudySession) -> None:
        try:
            while session.remaining_seconds > 0:
                await self._edit_timer_message(session)
                await asyncio.sleep(min(_TIMER_TICK_SECONDS, session.remaining_seconds))
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
                f"{member.mention} left **{channel_name}** during an active study session.\n"
                f"Elapsed: **{elapsed}** · Remaining: **{remaining}**\n\n"
                "Rejoin the voice channel to stay locked in, or use `!studyend` to stop."
            ),
            color=self.embedRed,
        )
        await self._announce(session, embed)

    @commands.command(
        name="study",
        aliases=["focus", "pomodoro"],
        help="Start a study timer in #study (default 25 min). Stay in voice or get a leave warning.",
    )
    async def study(self, ctx: commands.Context, minutes: str | None = None):
        if ctx.guild is None:
            await ctx.send("Study sessions can only be started in a server.")
            return

        if self._active_session(ctx.author.id) is not None:
            await ctx.send("You already have an active study session. Use `!studyend` to stop it.")
            return

        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.send("Join a voice channel first so lock-in warnings can track if you leave.")
            return

        try:
            duration_minutes = parse_study_minutes(minutes)
        except ValueError as exc:
            await ctx.send(str(exc))
            return

        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("Start a study session from a text channel.")
            return

        study_channel = await self._resolve_study_channel(ctx.guild, ctx.channel)
        duration_seconds = duration_minutes * 60
        now = time.monotonic()
        session = StudySession(
            user_id=ctx.author.id,
            guild_id=ctx.guild.id,
            text_channel_id=study_channel.id,
            voice_channel_id=ctx.author.voice.channel.id,
            duration_seconds=duration_seconds,
            started_at=now,
            end_at=now + duration_seconds,
        )

        try:
            timer_message = await study_channel.send(embed=self._timer_embed(session))
        except discord.HTTPException as exc:
            await ctx.send(f"Could not post the study timer: {exc}")
            return

        session.timer_message_id = timer_message.id
        session.task = asyncio.create_task(self._session_timer(session))
        self.sessions[ctx.author.id] = session

        if study_channel.id == ctx.channel.id:
            await ctx.send(
                f"Study session started ({duration_minutes} min). "
                "The timer above updates live — use `!studyend` to stop early."
            )
        else:
            await ctx.send(
                f"Study session started ({duration_minutes} min). "
                f"Live timer is in {study_channel.mention} — use `!studyend` to stop early."
            )

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
        if ctx.channel.id != session.text_channel_id:
            await ctx.send("Study session ended.")


async def setup(bot: commands.Bot):
    await bot.add_cog(StudyCog(bot))
