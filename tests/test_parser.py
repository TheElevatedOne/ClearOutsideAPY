from __future__ import annotations

import json
from pathlib import Path

import pytest

from clear_outside_apy import parse
from clear_outside_apy.exceptions import ParseError

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture(scope="module")
def midday():
    return parse(_load("forecast_midday.html"), metric=True)


@pytest.fixture(scope="module")
def experimental():
    return parse(_load("forecast_experimental.html"), metric=True)


@pytest.fixture(scope="module")
def frost():
    return parse(_load("forecast_frost.html"), metric=True)


def test_location(midday):
    loc = midday["location"]
    assert loc["latitude"] == "43.16"
    assert loc["longitude"] == "-75.84"
    assert "United States" in loc["name"]


def test_sky_quality(midday):
    sky = midday["sky-quality"]
    assert sky["magnitude"] == 21.3
    assert sky["bortle_class"] == 4
    assert sky["brightness"]["value"] == 0.33
    assert sky["brightness"]["unit"] == "mcd/m2"
    assert sky["artif-brightness"]["value"] == 155.5
    assert sky["artif-brightness"]["unit"] == "ucd/m2"


def test_gen_info(midday):
    info = midday["gen-info"]
    assert info["last-gen"]["date"]
    assert info["last-gen"]["time"]
    assert info["forecast"]["from-day"]
    assert info["forecast"]["to-day"]
    assert info["timezone"].startswith("UTC")


def test_seven_days_twenty_four_hours(midday):
    forecast = midday["forecast"]
    assert len(forecast) == 7
    for i in range(7):
        day = forecast[f"day-{i}"]
        assert len(day["hours"]) == 24
        assert day["date"]["long"]
        assert day["date"]["short"]


def test_sun_and_moon(midday):
    day0 = midday["forecast"]["day-0"]
    sun = day0["sun"]
    assert sun["rise"] == "06:42"
    assert sun["set"] == "19:16"
    assert sun["transit"] == "12:58"
    assert sun["civil-dark"] == ["19:44", "06:14"]
    assert sun["nautical-dark"] == ["20:18", "05:40"]
    assert sun["astro-dark"] == ["20:53", "05:05"]

    moon = day0["moon"]
    assert moon["rise"] == "10:38"
    assert moon["set"] == "20:07"
    assert moon["phase"]["name"] == "Waxing Crescent"
    assert moon["phase"]["percentage"] == 8
    mer = moon["meridian"]
    assert mer["time"] == "14:53"
    assert mer["date"] == "13/09/2026"
    assert mer["altitude"] == 33.0
    assert mer["distance-unit"] == "km"
    assert mer["distance"] == round(241461 * 1.609344, 2)


def test_moon_no_rise(midday):
    day2 = midday["forecast"]["day-2"]
    assert day2["moon"]["rise"] is None
    assert day2["moon"]["set"] == "21:00"


def test_hour_conditions_and_clouds(midday):
    hour12 = midday["forecast"]["day-0"]["hours"]["12"]
    assert hour12["conditions"] == "ok"
    assert hour12["total-clouds"] == 45
    assert hour12["low-clouds"] == 35
    assert hour12["mid-clouds"] == 0
    assert hour12["high-clouds"] == 1
    hour13 = midday["forecast"]["day-0"]["hours"]["13"]
    assert hour13["conditions"] == "bad"


def test_missing_visibility_is_none(midday):
    hour12 = midday["forecast"]["day-0"]["hours"]["12"]
    assert hour12["visibility"] is None
    hour04 = midday["forecast"]["day-0"]["hours"]["04"]
    assert hour04["visibility"] == round(9 * 1.609344, 2)


def test_precipitation(midday):
    hours = midday["forecast"]["day-0"]["hours"]
    assert hours["12"]["prec-type"] == "none"
    assert hours["17"]["prec-type"] == "very-light-rain"
    assert hours["18"]["prec-type"] == "light-rain"
    assert hours["19"]["prec-type"] == "ice-pellet"
    assert hours["19"]["prec-probability"] == 100
    assert hours["19"]["prec-amount"] == 4.6


def test_wind(midday):
    wind = midday["forecast"]["day-0"]["hours"]["12"]["wind"]
    assert wind["direction"] == "west-south-west"
    assert wind["speed"] == round(6 * 1.609344, 2)
    assert wind["degrees"] == 258


def test_iss_passover(midday):
    hours = midday["forecast"]["day-0"]["hours"]
    iss_hours = [h for h, data in hours.items() if data["iss"] is not None]
    assert iss_hours, "expected at least one ISS pass"
    sample = hours[iss_hours[0]]["iss"]
    assert sample["start"]["time"]
    assert sample["start"]["direction"]
    assert isinstance(sample["start"]["altitude"], int)
    assert sample["max"]["time"]
    assert sample["end"]["time"]
    assert isinstance(sample["magnitude"], float)


def test_temperature_humidity_pressure(midday):
    hour = midday["forecast"]["day-0"]["hours"]["12"]
    assert hour["temperature"]["general"] == 25
    assert hour["temperature"]["feels-like"] == 27
    assert hour["temperature"]["dew-point"] == 20
    assert hour["rel-humidity"] == 72
    assert hour["pressure"] == 1012
    assert hour["ozone"] == 309
    assert hour["frost"] == "none"


def test_frost_present(frost):
    values = [
        hour["frost"]
        for day in frost["forecast"].values()
        for hour in day["hours"].values()
    ]
    assert "frost" in values
    assert "none" in values


def test_experimental_rows(experimental, midday):
    hour = experimental["forecast"]["day-0"]["hours"]["04"]
    assert "extra" in hour
    extra = hour["extra"]
    assert "metno" in extra
    assert "timer" in extra
    assert extra["timer"]["seeing"] == 50
    assert extra["timer"]["cloud-cover"] == 90
    assert extra["metno"]["total-clouds"] == 13
    # default page has no extra block
    assert "extra" not in midday["forecast"]["day-0"]["hours"]["12"]


def test_imperial_units(midday):
    imperial = parse(_load("forecast_midday.html"), metric=False)
    vis_m = midday["forecast"]["day-0"]["hours"]["04"]["visibility"]
    vis_i = imperial["forecast"]["day-0"]["hours"]["04"]["visibility"]
    assert vis_i == 9
    assert vis_m == round(9 * 1.609344, 2)
    assert imperial["units"]["visibility"] == "miles"
    assert midday["units"]["visibility"] == "km"
    dist_i = imperial["forecast"]["day-0"]["moon"]["meridian"]["distance"]
    dist_m = midday["forecast"]["day-0"]["moon"]["meridian"]["distance"]
    assert dist_i == 241461
    assert dist_m == round(241461 * 1.609344, 2)


def test_parse_rejects_garbage():
    with pytest.raises(ParseError):
        parse(b"<html><body>not a forecast</body></html>")


def test_result_is_json_serializable(midday):
    json.dumps(midday)
