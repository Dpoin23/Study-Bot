"""Unit tests for StudyCog pure helpers (no Discord gateway)."""

from __future__ import annotations

import pytest

from bot.cogs.study import format_duration, parse_study_minutes


def test_parse_study_minutes_default():
    assert parse_study_minutes(None) == 25
    assert parse_study_minutes("") == 25
    assert parse_study_minutes("  ") == 25


def test_parse_study_minutes_valid():
    assert parse_study_minutes("1") == 1
    assert parse_study_minutes("45") == 45
    assert parse_study_minutes("180") == 180


def test_parse_study_minutes_rejects_invalid():
    with pytest.raises(ValueError, match="whole number"):
        parse_study_minutes("abc")
    with pytest.raises(ValueError, match="between"):
        parse_study_minutes("0")
    with pytest.raises(ValueError, match="between"):
        parse_study_minutes("181")


def test_format_duration():
    assert format_duration(0) == "0s"
    assert format_duration(5) == "5s"
    assert format_duration(65) == "1m 5s"
    assert format_duration(3600) == "1h 0m 0s"
    assert format_duration(3661) == "1h 1m 1s"
    assert format_duration(-3) == "0s"
