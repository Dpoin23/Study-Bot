# Study-Bot

A Discord music bot that allows users to search, queue, and control music playback directly from a voice channel

**Command Prefix:** `!`

---

## Commands:
| Command | Aliases | Description | Requirements |
|---------|---------|-------------|--------------|
| `!play` | `!pl` | `Plays any music that is currently added to the queue, it can also be used as a resume button if there is a song that is currently paused. Play also supports limited search functionality, searching for a song in the play command (!play The Pretender) will search for the specified song and play the first song that appears in the search (if any).` | `Using the play command requires that you are in a voice channel.` |
!play - 
    Alias: !pl
    Description: Plays any music that is currently added to the queue, it can also be used as a resume button if there is a song that is currently paused. Play also supports limited search functionality, searching for a song in the play command (!play The Pretender) will search for the specified song and play the first song that appears in the search (if any).
    Requirements: Using the play command requires that you are in a voice channel.

!add -
    Aliases: !a !+
    Description: Adds the song specified in the command to the queue (!play The Pretender).
    Requirements: The add command also requires that you are connected to a voice channel, and also requires that the command contains a song to add (regardless of whether said song will yield any search results or not).

!remove
    Alias: !rm
    Description: Removes the song that was most recently add to the queue (the sone at the back).
    Requirements: The remove command requires that the user is connected to a voice channel, it also requires that the queue contains at least 1 song, remove the only song in the queue essentially just clears the queue, if the song is playing, that song will also be stopped and the bot will leave the voice channel.

!search -
    Aliases: !? !se !find
    Description: Searches for the song specified in the command and displays a list of the first 10 songs found in the search, the command also prompts you to enter your choice of which song you'd like to add to the queue. Upon choosing from one of the 10 options, the choosen song is added to the queue.
    Requirements: Search requires that the user is connected to the voice channel and the command contains a song to search for (regardless of whether said song will yield any search results or not).

!pause -
    Alias: !stop
    Description: The pause command pauses any currently playing music.
    Requirements: Pause requires that the user is connected to a voice channel, and that a song is currently playing at the time of the command.

!resume -
    Aliases: !re !start
    Description: The resume command resumes any music that is currently paused.
    Requirements: Resume requires that the user is connected to a voice channel, and there is a song that is currently paused.

!join -
    Alias: !j
    Description: The join command prompts the bot to join the voice channel.
    Requirements: Join requires that the user is connected to a voice channel so the bot has a channel to join.

!leave -
    Alias: !l
    Description: The leave command prompts the bot to leave the voice channel, which will also cause any currently playing music to stop and the current music queue to be erased.
    Requirements: Leave requires that the user is connected to a voice channel and that the bot is also in the voice channel. If there are no users left in the voice channel, the bot will automatically leave.
