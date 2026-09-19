import discord
from discord.ext import commands


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embedOrange = 0xFFA500
        self._greeted = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self._greeted:
            return
        self._greeted = True
        send_to_channels = []
        for guild in self.bot.guilds:
            channel = guild.text_channels[0]
            send_to_channels.append(channel)
        hello_embed = discord.Embed(
            title="Hello", 
            description="I am the study/music bot for the server. Use '!help' if you need assistance.", 
            color=self.embedOrange
        )
        for channel in send_to_channels:
            await channel.send(embed=hello_embed)

    @commands.command(
        name="help", 
        aliases=["h", "?"], 
        help="Displays all commands and their descriptions"
    )
    async def help(self, ctx):
        help_cog = self.bot.get_cog("HelpCog")
        music_cog = self.bot.get_cog("MusicCog")
        study_cog = self.bot.get_cog("StudyCog")
        sections = []
        if help_cog:
            sections.append(("Help", help_cog.get_commands()))
        if study_cog:
            sections.append(("Study", study_cog.get_commands()))
        if music_cog:
            sections.append(("Music", music_cog.get_commands()))

        lines = ["*Use a command with the `!` prefix. Aliases are shown in parentheses.*", ""]
        for title, cog_commands in sections:
            lines.append(f"**{title}**")
            for command in cog_commands:
                aliases = f" (`{'`, `'.join(command.aliases)}`)" if command.aliases else ""
                description = command.help or "No description."
                lines.append(f"• **`!{command.name}`**{aliases} — {description}")
            lines.append("")

        commands_embed = discord.Embed(
            title="Command List",
            description="\n".join(lines).strip(),
            color=self.embedOrange
        )
        await ctx.send(embed=commands_embed)
