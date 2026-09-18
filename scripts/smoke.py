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
    import admin_cog
    import help_cog
    import music_cog
    import view

    bot = MagicMock()
    music = music_cog.MusicCog(bot)

    entry = {"id": "dQw4w9WgXcQ", "title": "smoke"}
    watch = music._watch_url(entry)
    thumb = music._thumbnail_url(entry)
    if "dQw4w9WgXcQ" not in watch:
        raise SystemExit(f"unexpected watch url: {watch}")
    if "dQw4w9WgXcQ" not in (thumb or ""):
        raise SystemExit(f"unexpected thumbnail: {thumb}")

    song = {"source": "https://example.com/a.m4a", "extracted_at": time.monotonic()}
    if not music._source_is_fresh(song):
        raise SystemExit("fresh source should be considered fresh")

    # Confirm cog modules construct without connecting.
    help_cog.HelpCog(bot)
    admin_cog.AdminCog(bot)

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
    music.musicQueue[1] = []
    view.SearchView(ctx, songs, music)

    ffmpeg = music_cog._ffmpeg_executable()
    if not ffmpeg:
        raise SystemExit("ffmpeg executable resolution returned empty")

    print(
        f"smoke ok: watch={watch!r} ffmpeg={ffmpeg!r} "
        f"modules={[admin_cog.__name__, help_cog.__name__, music_cog.__name__, view.__name__]}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as err:
        print(f"smoke failed: {err}", file=sys.stderr)
        sys.exit(1)
