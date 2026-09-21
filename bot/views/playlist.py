import discord


class PlaylistSearchView(discord.ui.View):
    """Dropdown to pick a YouTube playlist and enqueue its tracks."""

    def __init__(self, ctx, playlists, music_cog, *, start_playback=False):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.playlists = playlists
        self.music_cog = music_cog
        self.start_playback = start_playback
        self.embedBlue = music_cog.embedBlue
        self.message = None

        options = [
            discord.SelectOption(
                label=f"{i + 1} - {playlist['title'][:90]}",
                value=str(i),
            )
            for i, playlist in enumerate(playlists)
        ]

        self.select = discord.ui.Select(
            placeholder="Select a playlist",
            options=options,
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.danger,
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def select_callback(self, interaction: discord.Interaction):
        chosen_index = int(self.select.values[0])
        playlist = self.playlists[chosen_index]

        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"Option #{chosen_index + 1} selected.",
                description=(
                    f"Loading [{playlist['title']}]({playlist['link']})…"
                ),
                color=self.embedBlue,
            ),
            view=None,
        )
        self.stop()

        result = await self.music_cog.enqueue_playlist_url(
            self.ctx,
            playlist["link"],
            start_playback=False,
        )
        if result is None:
            await interaction.followup.send(
                "Could not load that playlist. Try a different one."
            )
            return

        embed = self.music_cog.added_playlist_embed(
            self.ctx,
            result["title"],
            result["link"],
            result["added"],
            result["total"],
            thumbnail=result.get("thumbnail"),
        )
        await interaction.followup.send(embed=embed)
        if self.start_playback and not self.music_cog.is_audio_playing(
            self.ctx.guild.id
        ):
            await self.music_cog.play_music(self.ctx)

    async def cancel_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Search Cancelled",
            color=self.embedBlue,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        try:
            if self.message:
                await self.message.edit(view=None)
        except Exception:
            print("Error on_timeout in PlaylistSearchView.")


class PlaylistRemoveView(discord.ui.View):
    """Dropdown to pick a queued playlist batch and remove its tracks."""

    def __init__(self, ctx, batches, music_cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.batches = batches
        self.music_cog = music_cog
        self.embedBlue = music_cog.embedBlue
        self.message = None

        options = [
            discord.SelectOption(
                label=f"{i + 1} - {batch['playlist_title'][:80]} ({batch['count']})",
                value=str(i),
            )
            for i, batch in enumerate(batches)
        ]

        self.select = discord.ui.Select(
            placeholder="Select a playlist to remove",
            options=options,
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.danger,
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def select_callback(self, interaction: discord.Interaction):
        chosen_index = int(self.select.values[0])
        batch = self.batches[chosen_index]
        summary = await self.music_cog.remove_playlist_batch(
            self.ctx,
            batch["batch"],
        )
        title = summary["title"]
        removed = summary["removed"]
        embed = discord.Embed(
            title="Playlist Removed From Queue.",
            description=f"Removed **{removed}** track(s) from **{title}**.",
            color=self.embedBlue,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Remove Cancelled",
            color=self.embedBlue,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        try:
            if self.message:
                await self.message.edit(view=None)
        except Exception:
            print("Error on_timeout in PlaylistRemoveView.")
