from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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
        ClearOutsideAPY("not-a-number", "1.0", fetch=False)


def test_lon_alias_and_repr():
    api = ClearOutsideAPY(43.16, lon=-75.84, fetch=False)
    assert api.long == "-75.84"
    assert api.lon == "-75.84"
    assert "43.16" in repr(api)
    with pytest.raises(TypeError):
        ClearOutsideAPY(43.16, fetch=False)
    with pytest.raises(TypeError):
        ClearOutsideAPY(43.16, -75.84, lon=-75.84, fetch=False)


def test_update_and_pull_use_downloaded_html():
    api = ClearOutsideAPY(43.16, -75.84, fetch=False)
    with patch("clear_outside_apy.client.fetch_html", return_value=FIXTURE) as mocked:
        result = api.pull()
    mocked.assert_called_once()
    assert result["location"]["latitude"] == "43.16"
    assert result["url"] == api.url
    assert result["view"] == "midday"
    assert result["experimental"] is False
    assert len(result["forecast"]) == 7


def test_fetch_forecast_helper():
    with patch("clear_outside_apy.client.fetch_html", return_value=FIXTURE):
        result = fetch_forecast(43.16, -75.84)
    assert result["sky-quality"]["bortle_class"] == 4


def test_parse_accepts_str_and_bytes():
    text = FIXTURE.decode("utf-8")
    a = parse(FIXTURE)
    b = parse(text)
    assert a["location"] == b["location"]
