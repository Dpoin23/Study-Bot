"""Unit tests for MusicCog pure helpers (no Discord / YouTube network)."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from bot.cogs import music as music_mod
from bot.cogs.music import (
    _PLAYLIST_ENQUEUE_CAP,
    _SOURCE_TTL_SECONDS,
    MusicCog,
    is_playlist_url,
    playlist_url_from_query,
)


def _cog() -> MusicCog:
    return MusicCog(MagicMock())


def test_watch_url_from_video_id():
    cog = _cog()
    assert (
        cog._watch_url({"id": "dQw4w9WgXcQ"})
        == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )


def test_watch_url_prefers_webpage_url():
    cog = _cog()
    url = "https://www.youtube.com/watch?v=abcdefghijk"
    assert cog._watch_url({"webpage_url": url, "id": "other"}) == url


def test_watch_url_from_short_url_field():
    cog = _cog()
    assert (
        cog._watch_url({"url": "dQw4w9WgXcQ"})
        == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )


def test_thumbnail_url_direct():
    cog = _cog()
    assert cog._thumbnail_url({"thumbnail": "https://img.example/t.jpg"}) == (
        "https://img.example/t.jpg"
    )


def test_thumbnail_url_from_list_and_id():
    cog = _cog()
    assert (
        cog._thumbnail_url(
            {
                "thumbnails": [
                    {"url": "https://img.example/a.jpg"},
                    {"url": "https://img.example/b.jpg"},
                ]
            }
        )
        == "https://img.example/b.jpg"
    )
    assert (
        cog._thumbnail_url({"id": "dQw4w9WgXcQ"})
        == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
    )


def test_source_is_fresh():
    cog = _cog()
    assert cog._source_is_fresh(None) is False
    assert cog._source_is_fresh({}) is False
    assert cog._source_is_fresh({"source": "x"}) is False

    fresh = {"source": "https://example.com/a", "extracted_at": time.monotonic()}
    assert cog._source_is_fresh(fresh) is True

    stale = {
        "source": "https://example.com/a",
        "extracted_at": time.monotonic() - (_SOURCE_TTL_SECONDS + 1),
    }
    assert cog._source_is_fresh(stale) is False


def test_ffmpeg_executable_resolves():
    path = music_mod._ffmpeg_executable()
    assert isinstance(path, str)
    assert len(path) > 0


def test_js_runtimes_returns_dict():
    runtimes = music_mod._js_runtimes()
    assert isinstance(runtimes, dict)
    assert runtimes  # at least a node placeholder


def test_is_playlist_url():
    assert is_playlist_url(
        "https://www.youtube.com/playlist?list=PLabc123"
    )
    assert not is_playlist_url(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123"
    )
    assert not is_playlist_url("lofi hip hop")
    assert not is_playlist_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_playlist_url_from_query():
    assert (
        playlist_url_from_query(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123"
        )
        == "https://www.youtube.com/playlist?list=PLabc123"
    )
    assert (
        playlist_url_from_query(
            "https://www.youtube.com/playlist?list=PLabc123"
        )
        == "https://www.youtube.com/playlist?list=PLabc123"
    )
    assert playlist_url_from_query("lofi beats") is None


def test_playlist_link_from_entry():
    cog = _cog()
    assert (
        cog._playlist_link_from_entry(
            {
                "id": "PLabc",
                "url": "https://www.youtube.com/playlist?list=PLabc",
            }
        )
        == "https://www.youtube.com/playlist?list=PLabc"
    )
    assert (
        cog._playlist_link_from_entry({"id": "PLonly"})
        == "https://www.youtube.com/playlist?list=PLonly"
    )


def test_apply_playlist_removal_adjusts_index():
    cog = _cog()
    guild_id = 42
    channel = SimpleNamespace(id=1)
    batch_a = "batch-a"
    batch_b = "batch-b"
    cog.musicQueue[guild_id] = [
        [{"title": "A", "playlist_batch": batch_a, "playlist_title": "Alpha"}, channel],
        [{"title": "B", "playlist_batch": batch_b, "playlist_title": "Beta"}, channel],
        [{"title": "C", "playlist_batch": batch_a, "playlist_title": "Alpha"}, channel],
        [{"title": "D"}, channel],
    ]
    cog.queueIndex[guild_id] = 1  # playing B (batch_b)

    summary = cog._apply_playlist_removal(guild_id, batch_a)
    assert summary["removed"] == 2
    assert summary["title"] == "Alpha"
    assert summary["current_was_removed"] is False
    assert [item[0]["title"] for item in cog.musicQueue[guild_id]] == ["B", "D"]
    assert cog.queueIndex[guild_id] == 0


def test_apply_playlist_removal_when_current_in_batch():
    cog = _cog()
    guild_id = 7
    channel = SimpleNamespace(id=1)
    batch = "batch-x"
    cog.musicQueue[guild_id] = [
        [{"title": "Keep"}, channel],
        [{"title": "Go1", "playlist_batch": batch, "playlist_title": "X"}, channel],
        [{"title": "Go2", "playlist_batch": batch, "playlist_title": "X"}, channel],
        [{"title": "Keep2"}, channel],
    ]
    cog.queueIndex[guild_id] = 1

    summary = cog._apply_playlist_removal(guild_id, batch)
    assert summary["removed"] == 2
    assert summary["current_was_removed"] is True
    assert [item[0]["title"] for item in cog.musicQueue[guild_id]] == [
        "Keep",
        "Keep2",
    ]
    assert cog.queueIndex[guild_id] == 1


def test_queued_playlist_batches_groups_by_batch():
    cog = _cog()
    guild_id = 9
    channel = SimpleNamespace(id=1)
    cog.musicQueue[guild_id] = [
        [{"title": "1", "playlist_batch": "b1", "playlist_title": "One"}, channel],
        [{"title": "2", "playlist_batch": "b1", "playlist_title": "One"}, channel],
        [{"title": "3", "playlist_batch": "b2", "playlist_title": "Two"}, channel],
        [{"title": "solo"}, channel],
    ]
    batches = cog.queued_playlist_batches(guild_id)
    assert len(batches) == 2
    assert batches[0]["playlist_title"] == "One"
    assert batches[0]["count"] == 2
    assert batches[1]["playlist_title"] == "Two"
    assert batches[1]["count"] == 1


def test_playlist_enqueue_cap_constant():
    assert _PLAYLIST_ENQUEUE_CAP == 100


def test_format_queue_description_empty():
    cog = _cog()
    guild_id = 1
    cog.musicQueue[guild_id] = []
    cog.queueIndex[guild_id] = 0
    assert cog.format_queue_description(guild_id) is None


def test_format_queue_description_labels_playing_and_next():
    cog = _cog()
    guild_id = 2
    channel = SimpleNamespace(id=1)
    cog.musicQueue[guild_id] = [
        [{"title": "Now", "link": "https://yt.example/1"}, channel],
        [{"title": "Soon", "link": "https://yt.example/2"}, channel],
        [{"title": "Later", "link": "https://yt.example/3"}, channel],
    ]
    cog.queueIndex[guild_id] = 0
    cog.isPlaying[guild_id] = True
    text = cog.format_queue_description(guild_id)
    assert text.startswith("Playing - [Now](https://yt.example/1)\n")
    assert "Next - [Soon](https://yt.example/2)\n" in text
    assert "3 - [Later](https://yt.example/3)\n" in text
    assert "… and" not in text


def test_format_queue_description_caps_song_count():
    cog = _cog()
    guild_id = 3
    channel = SimpleNamespace(id=1)
    cog.musicQueue[guild_id] = [
        [{"title": f"Song {i}", "link": f"https://yt.example/{i}"}, channel]
        for i in range(50)
    ]
    cog.queueIndex[guild_id] = 0
    cog.isPlaying[guild_id] = False
    text = cog.format_queue_description(guild_id)
    assert text is not None
    assert len(text) <= music_mod._QUEUE_EMBED_MAX_CHARS
    assert "… and" in text
    shown_lines = [line for line in text.splitlines() if " - " in line]
    assert len(shown_lines) == music_mod._QUEUE_EMBED_MAX_SONGS
    omitted = 50 - music_mod._QUEUE_EMBED_MAX_SONGS
    assert f"… and {omitted} more" in text


def test_format_queue_description_caps_character_length():
    cog = _cog()
    guild_id = 4
    channel = SimpleNamespace(id=1)
    long_title = "A" * 200
    cog.musicQueue[guild_id] = [
        [
            {
                "title": f"{long_title} {i}",
                "link": f"https://www.youtube.com/watch?v={'x' * 11}",
            },
            channel,
        ]
        for i in range(40)
    ]
    cog.queueIndex[guild_id] = 0
    cog.isPlaying[guild_id] = True
    text = cog.format_queue_description(guild_id)
    assert text is not None
    assert len(text) <= music_mod._QUEUE_EMBED_MAX_CHARS
    assert "… and" in text
    shown_lines = [line for line in text.splitlines() if " - " in line]
    assert len(shown_lines) < music_mod._QUEUE_EMBED_MAX_SONGS
