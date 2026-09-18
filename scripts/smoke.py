#!/usr/bin/env python3
"""Import application modules and exercise pure helpers without Discord login."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from bot.cogs import admin, music
    from bot.cogs import help as help_cog
    from bot.views import search

    bot = MagicMock()
    music_cog = music.MusicCog(bot)

    entry = {"id": "dQw4w9WgXcQ", "title": "smoke"}
    watch = music_cog._watch_url(entry)
    thumb = music_cog._thumbnail_url(entry)
    if "dQw4w9WgXcQ" not in watch:
        raise SystemExit(f"unexpected watch url: {watch}")
    if "dQw4w9WgXcQ" not in (thumb or ""):
        raise SystemExit(f"unexpected thumbnail: {thumb}")

    song = {"source": "https://example.com/a.m4a", "extracted_at": time.monotonic()}
    if not music_cog._source_is_fresh(song):
        raise SystemExit("fresh source should be considered fresh")

    help_cog.HelpCog(bot)
    admin.AdminCog(bot)

    ctx = SimpleNamespace(guild=SimpleNamespace(id=1))
    songs = [
        {
            "title": "Smoke Track",
            "link": watch,
            "thumbnail": thumb,
            "source": None,
            "extracted_at": None,
        }
    ]
    music_cog.musicQueue[1] = []
    search.SearchView(ctx, songs, music_cog)

    ffmpeg = music._ffmpeg_executable()
    if not ffmpeg:
        raise SystemExit("ffmpeg executable resolution returned empty")

    print(
        f"smoke ok: watch={watch!r} ffmpeg={ffmpeg!r} "
        f"modules={[admin.__name__, help_cog.__name__, music.__name__, search.__name__]}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as err:
        print(f"smoke failed: {err}", file=sys.stderr)
        sys.exit(1)
