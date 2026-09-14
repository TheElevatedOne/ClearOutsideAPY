from __future__ import annotations

import os

import pytest

from clear_outside_apy import ClearOutsideAPY

pytestmark = pytest.mark.network


@pytest.mark.skipif(
    os.environ.get("CLEAROUTSIDE_LIVE") != "1",
    reason="set CLEAROUTSIDE_LIVE=1 to hit clearoutside.com",
)
def test_live_midday_forecast():
    api = ClearOutsideAPY(43.16, -75.84, view="midday", timeout=30)
    result = api.pull()
    assert result["location"]["latitude"] == "43.16"
    assert len(result["forecast"]) == 7
    assert len(result["forecast"]["day-0"]["hours"]) == 24
