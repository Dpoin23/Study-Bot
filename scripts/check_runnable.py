#!/usr/bin/env python3
"""Verify the bot process is constructible and (optionally) can log in.

Default mode is offline: import, create_bot, run setup_hook.
Set STUDY_BOT_LIVE_CHECK=1 with a valid DISCORD_TOKEN to also log in briefly.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def _offline_check() -> None:
    from bot.app import create_bot

    bot = create_bot()
    await bot.setup_hook()
    expected = ("MusicCog", "StudyCog", "AdminCog", "HelpCog")
    missing = [name for name in expected if bot.get_cog(name) is None]
    await bot.close()
    if missing:
        raise SystemExit(f"missing cogs after setup_hook: {missing}")


async def _live_check(token: str) -> None:
    from bot.app import create_bot

    bot = create_bot()
    ready = asyncio.Event()

    @bot.listen("on_ready")
    async def _on_ready():
        ready.set()

    try:
        await bot.login(token)
        connect_task = asyncio.create_task(bot.connect(reconnect=False))
        try:
            await asyncio.wait_for(ready.wait(), timeout=30)
        finally:
            await bot.close()
            if not connect_task.done():
                connect_task.cancel()
                try:
                    await connect_task
                except (asyncio.CancelledError, Exception):
                    pass
    finally:
        if not bot.is_closed():
            await bot.close()


def main() -> int:
    asyncio.run(_offline_check())
    print("runnable ok: create_bot + setup_hook")

    if os.getenv("STUDY_BOT_LIVE_CHECK", "").strip().lower() in {"1", "true", "yes"}:
        from bot.app import get_discord_token

        token = get_discord_token()
        asyncio.run(_live_check(token))
        print("runnable ok: live Discord login")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as err:
        print(f"runnable check failed: {err}", file=sys.stderr)
        sys.exit(1)
