"""Startup and runnability checks for Study Bot (no Discord login required)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from bot.app import StudyBot, create_bot, get_discord_token, run


def test_get_discord_token_rejects_missing(monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with patch("bot.app.load_environment"):
        with pytest.raises(ValueError, match="DISCORD_TOKEN"):
            get_discord_token()


def test_get_discord_token_rejects_placeholder(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "your_bot_token_here")
    with patch("bot.app.load_environment"):
        with pytest.raises(ValueError, match="placeholder"):
            get_discord_token()


def test_get_discord_token_strips_whitespace(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "  real-token-value  ")
    with patch("bot.app.load_environment"):
        assert get_discord_token() == "real-token-value"


def test_run_exits_when_token_missing(monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with patch("bot.app.load_environment"):
        with pytest.raises(SystemExit, match="DISCORD_TOKEN"):
            run()


def test_create_bot_returns_study_bot():
    bot = create_bot()
    assert isinstance(bot, StudyBot)
    assert bot.command_prefix == "!"
    assert bot.get_command("help") is None


def test_create_bot_setup_hook_loads_cogs():
    async def _run():
        bot = create_bot()
        await bot.setup_hook()
        try:
            assert bot.get_cog("MusicCog") is not None
            assert bot.get_cog("StudyCog") is not None
            assert bot.get_cog("AdminCog") is not None
            assert bot.get_cog("HelpCog") is not None
            assert bot.get_command("study") is not None
            assert bot.get_command("play") is not None
            assert bot.get_command("studystatus") is None
        finally:
            await bot.close()

    asyncio.run(_run())


def test_bot_module_entrypoint_importable():
    import bot.__main__ as bot_main
    import main as root_main

    assert callable(bot_main.run)
    assert callable(root_main.run)
