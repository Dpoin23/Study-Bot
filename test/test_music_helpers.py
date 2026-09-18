"""Unit tests for MusicCog pure helpers (no Discord / YouTube network)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import music_cog
from music_cog import _SOURCE_TTL_SECONDS, MusicCog


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
            {"thumbnails": [{"url": "https://img.example/a.jpg"}, {"url": "https://img.example/b.jpg"}]}
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
    path = music_cog._ffmpeg_executable()
    assert isinstance(path, str)
    assert len(path) > 0


def test_js_runtimes_returns_dict():
    runtimes = music_cog._js_runtimes()
    assert isinstance(runtimes, dict)
    assert runtimes  # at least a node placeholder
