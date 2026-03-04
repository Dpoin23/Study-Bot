import discord

class SearchView(discord.ui.View):
    def __init__(self, ctx, songs, songReferences, embedBlue, musicQueue):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.songs = songs
        self.songReferences = songReferences
        self.embedBlue = embedBlue
        self.musicQueue = musicQueue

        options = [
            discord.SelectOption(
                label=f"{i+1} - {song['title'][:90]}\n",
                value=str(i)
            )
            for i, song in enumerate(songs)
        ]

        self.select = discord.ui.Select(
            placeholder="Select an option",
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.danger
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def select_callback(self, interaction: discord.Interaction):
        chosenIndex = int(self.select.values[0])
        songRef = self.songReferences[chosenIndex]

        embedResponse = discord.Embed(
            title=f"Option #{chosenIndex + 1} selected.",
            description=f"[{songRef['title']}]({songRef['link']}) added to the queue!",
            color=self.embedBlue
        )
        embedResponse.set_thumbnail(url=songRef['thumbnail'])

        self.musicQueue[self.ctx.guild.id].append(
            [songRef, self.ctx.author.voice.channel]
        )

        await interaction.response.edit_message(embed=embedResponse, view=None)
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Search Cancelled",
            color=self.embedBlue
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except:
            print("Error on_timeout in SearchView.")