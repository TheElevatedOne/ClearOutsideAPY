from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from clear_outside_apy import (
    ClearOutsideAPY,
    InvalidLocationError,
    build_url,
    fetch_forecast,
    parse,
)

FIXTURE = (Path(__file__).parent / "fixtures" / "forecast_midday.html").read_bytes()


def test_build_url_formats_coords_and_view():
    url = build_url(43.164, -75.841, view="current")
    assert url == "https://clearoutside.com/forecast/43.16/-75.84?view=current"
    url = build_url("43.16", "-75.84", experimental=True)
    assert url.endswith("?view=midday&experimental=on")


def test_invalid_coords_and_view():
    with pytest.raises(InvalidLocationError):
        build_url(100, 0)
    with pytest.raises(InvalidLocationError):
        build_url(0, 200)
    with pytest.raises(InvalidLocationError):
        build_url(0, 0, view="noon")
    with pytest.raises(InvalidLocationError):
        ClearOutsideAPY("not-a-number", "1.0")


def test_lon_alias_and_repr():
    api = ClearOutsideAPY(43.16, lon=-75.84)
    assert api.long == "-75.84"
    assert api.lon == "-75.84"
    assert "43.16" in repr(api)
    assert api.html is None
    with pytest.raises(TypeError):
        ClearOutsideAPY(43.16)
    with pytest.raises(TypeError):
        ClearOutsideAPY(43.16, -75.84, lon=-75.84)


def test_update_and_pull_use_downloaded_html():
    api = ClearOutsideAPY(43.16, -75.84, cache_ttl=60)
    mocked = AsyncMock(return_value=FIXTURE)
    with patch("clear_outside_apy.client.fetch_html", mocked):
        result = asyncio.run(api.pull())
        asyncio.run(api.pull())  # cached HTML is reused
    mocked.assert_awaited_once()
    assert mocked.await_args.args == (api.url,)
    assert mocked.await_args.kwargs["cache_ttl"] == 60
    assert result["location"]["latitude"] == "43.16"
    assert result["url"] == api.url
    assert result["view"] == "midday"
    assert result["experimental"] is False
    assert len(result["forecast"]) == 7


def test_fetch_forecast_helper():
    with patch("clear_outside_apy.client.fetch_html", AsyncMock(return_value=FIXTURE)):
        result = asyncio.run(fetch_forecast(43.16, -75.84))
    assert result["sky-quality"]["bortle_class"] == 4


def test_parse_accepts_str_and_bytes():
    text = FIXTURE.decode("utf-8")
    a = parse(FIXTURE)
    b = parse(text)
    assert a == b
    with pytest.raises(TypeError):
        parse(123)
