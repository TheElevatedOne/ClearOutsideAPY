"""Pure-Python parser for clearoutside.com forecast HTML.

Port of the 2.0 C extension. Cloudflare Python Workers run on Pyodide, which
cannot load custom C extensions, so this module must stay dependency-free.

The page is scanned with ``bytes.find`` and a few regular expressions rather
than a DOM parser: it is much faster, and fast matters under the Workers CPU
limit. Everything works on UTF-8 bytes and is decoded when the result is built.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .exceptions import ParseError

MAX_DAYS = 8
MAX_HOURS = 32
MILES_TO_KM = 1.609344

WS = b" \t\n\r"

_TAG_RE = re.compile(rb"""<(?:"[^"]*"?|'[^']*'?|[^>"'])*>?""")
_TAG_CLOSE_RE = re.compile(rb"""(?:"[^"]*"|'[^']*'|[^>"'])*>""")
_LI_RE = re.compile(rb"""<li((?:"[^"]*"|'[^']*'|[^>"'])*)>(.*?)</li>""", re.S)
_ENTITY_RE = re.compile(rb"&(?:(nbsp|deg|amp|lt|gt|quot)|#([xX][0-9a-fA-F]+|[0-9]+));")
_WS_RE = re.compile(rb"[ \t\n\r]+")
_WORD_RE = re.compile(rb"[ \t\n\r]*([^ \t\n\r]+)")
_INT_RE = re.compile(rb"[ \t\n\r]*([+-]?)([0-9]+)")
_FLOAT_RE = re.compile(rb"[ \t\n\r]*([+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)")
_CLOCK_RE = re.compile(rb"[0-9]+(?::[0-9]+)+")

_NAMED_ENTITIES = {
    b"nbsp": b" ",
    b"deg": "°".encode(),
    b"amp": b"&",
    b"lt": b"<",
    b"gt": b">",
    b"quot": b'"',
}

# Order matters: the Met.no / 7Timer labels also contain "Total Clouds" etc.
_ROW_LABELS = (
    (b"Met.no Forecast % Total", "metno_total"),
    (b"Met.no Forecast % Low", "metno_low"),
    (b"Met.no Forecast % Medium", "metno_mid"),
    (b"Met.no Forecast % High", "metno_high"),
    (b"7Timer Cloud Cover", "t7_cloud"),
    (b"7Timer Seeing", "t7_seeing"),
    (b"7Timer Lifted", "t7_lifted"),
    (b"7Timer Transparency", "t7_trans"),
    (b"Total Clouds", "total_clouds"),
    (b"Low Clouds", "low_clouds"),
    (b"Medium Clouds", "mid_clouds"),
    (b"High Clouds", "high_clouds"),
    (b"ISS Passover", "iss"),
    (b"Visibility", "visibility"),
    (b"Fog", "fog"),
    (b"Precipitation Type", "prec_type"),
    (b"Precipitation Probability", "prec_prob"),
    (b"Precipitation Amount", "prec_amt"),
    (b"Wind Speed", "wind"),
    (b"Chance of Frost", "frost"),
    (b"Feels Like", "feels"),
    (b"Dew Point", "dew"),
    (b"Temperature", "temp"),
    (b"Relative Humidity", "humidity"),
    (b"Pressure", "pressure"),
    (b"Ozone", "ozone"),
)

_INT_ROWS = frozenset(
    {
        "total_clouds", "low_clouds", "mid_clouds", "high_clouds", "fog",
        "prec_prob", "temp", "feels", "dew", "humidity", "pressure", "ozone",
    }
)
_EXTRA_ROWS = frozenset(
    {
        "metno_total", "metno_low", "metno_mid", "metno_high",
        "t7_cloud", "t7_seeing", "t7_lifted", "t7_trans",
    }
)


# --------------------------------------------------------------------------
# Low-level text helpers
# --------------------------------------------------------------------------


def _decode_entity(m: re.Match[bytes]) -> bytes:
    name, num = m.group(1), m.group(2)
    if name:
        return _NAMED_ENTITIES[name]
    cp = int(num[1:], 16) if num[:1] in (b"x", b"X") else int(num)
    try:
        return chr(cp).encode("utf-8")
    except (ValueError, OverflowError):
        return m.group(0)


def _text(s: bytes) -> bytes:
    """Strip tags, decode common entities, collapse whitespace."""
    if b"<" in s:
        s = _TAG_RE.sub(b"", s)
    if b"&" in s:
        s = _ENTITY_RE.sub(_decode_entity, s)
    return _WS_RE.sub(b" ", s).strip(b" ")


def _tag_close(html: bytes, pos: int, end: int) -> int:
    """Index of the ``>`` closing the tag at ``pos``, skipping quoted values."""
    m = _TAG_CLOSE_RE.match(html, pos, end)
    return m.end() - 1 if m else -1


def _tag_start(html: bytes, pos: int, lo: int) -> int:
    """Walk back from ``pos`` to the ``<`` that opens its tag."""
    lt = html.rfind(b"<", lo, pos + 1)
    return lt if lt >= 0 else lo


def _attr_raw(tag: bytes, name: bytes) -> bytes:
    """Raw value of a quoted attribute in ``tag`` (empty if absent).

    ``tag`` is the text between ``<name`` and ``>``, or a whole tag starting
    with ``<``; either way the attribute must follow whitespace.
    """
    needle = name + b"="
    n = len(needle)
    p = tag.find(needle)
    while p >= 0 and p + n + 2 < len(tag):
        if p > 0 and tag[p - 1] in WS:
            quote = tag[p + n : p + n + 1]
            if quote not in (b'"', b"'"):
                return b""
            vs = p + n + 1
            ve = tag.find(quote, vs)
            return tag[vs:] if ve < 0 else tag[vs:ve]
        p = tag.find(needle, p + 1)
    return b""


def _attr(tag: bytes, name: bytes) -> bytes:
    return _text(_attr_raw(tag, name))


def _int(s: bytes) -> int | None:
    m = _INT_RE.match(s)
    if not m:
        return None
    value = int(m.group(2))
    return -value if m.group(1) == b"-" else value


def _float(s: bytes) -> float | None:
    m = _FLOAT_RE.match(s)
    return float(m.group(1)) if m else None


def _round2(x: float) -> float:
    if x >= 0.0:
        return math.trunc(x * 100.0 + 0.5) / 100.0
    return math.trunc(x * 100.0 - 0.5) / 100.0


def _after_label(s: bytes, label: bytes) -> int:
    """Position just past ``label`` and any whitespace, or -1."""
    h = s.find(label)
    if h < 0:
        return -1
    h += len(label)
    while h < len(s) and s[h] in WS:
        h += 1
    return h


def _read_word(s: bytes, pos: int) -> tuple[bytes, int]:
    """Read the next whitespace-delimited word; ``pos`` is unchanged on EOF."""
    m = _WORD_RE.match(s, pos)
    if not m:
        return b"", pos
    return m.group(1), m.end()


def _read_time(s: bytes, pos: int) -> tuple[bytes, int]:
    """Read ``HH:MM[:SS]``; ``No Rise`` / ``No Set`` / ``-`` are consumed and yield ``b""``."""
    word, nxt = _read_word(s, pos)
    if not word:
        return b"", pos
    if word in (b"No", b"-"):
        follow, after = _read_word(s, nxt)
        if follow in (b"Rise", b"Set"):
            nxt = after
        return b"", nxt
    if not _CLOCK_RE.fullmatch(word):
        return b"", pos
    return word, nxt


def _read_date(s: bytes, pos: int) -> tuple[bytes, int]:
    word, nxt = _read_word(s, pos)
    if word and b"/" in word:
        return word, nxt
    return b"", pos


def _skip_dash(s: bytes, pos: int) -> int:
    while pos < len(s) and (s[pos] == 0x2D or s[pos] in WS):
        pos += 1
    return pos


def _kebab_lower(s: bytes) -> bytes:
    out = bytearray()
    for c in s.lower():
        if c in b" _/":
            if out and out[-1] != 0x2D:
                out.append(0x2D)
        else:
            out.append(c)
    return bytes(out)


def _str(b: bytes | None) -> str | None:
    return b.decode("utf-8", "replace") if b else None


# --------------------------------------------------------------------------
# Day / hour model
# --------------------------------------------------------------------------


class _Hour:
    # Class attributes act as defaults; parsing only sets what it finds.
    hour = b""
    conditions = b""
    total_clouds = low_clouds = mid_clouds = high_clouds = None
    visibility = None
    fog = None
    prec_type = b""
    prec_prob = None
    prec_amt = None
    wind_speed = None
    wind_dir = b""
    wind_deg = None
    frost = None
    temp = feels = dew = None
    humidity = pressure = ozone = None
    iss = b""
    metno_total = metno_low = metno_mid = metno_high = None
    t7_cloud = t7_seeing = t7_lifted = t7_trans = None


class _Day:
    def __init__(self) -> None:
        self.weekday = b""
        self.day_short = b""
        self.moon_phase = b""
        self.moon_pct: int | None = None
        self.moon_rise = b""
        self.moon_set = b""
        self.moon_rise_date = b""
        self.moon_set_date = b""
        self.mer_time = b""
        self.mer_date = b""
        self.mer_alt: float | None = None
        self.mer_dist_miles: float | None = None
        self.sun_rise = b""
        self.sun_set = b""
        self.sun_transit = b""
        self.civil = [b"", b""]
        self.naut = [b"", b""]
        self.astro = [b"", b""]
        self.hours = [_Hour() for _ in range(MAX_HOURS)]
        self.nhours = 0
        self.has_extra = False


# --------------------------------------------------------------------------
# Day block parsing
# --------------------------------------------------------------------------


def _lis(html: bytes, ul: int, end: int) -> list[tuple[bytes, bytes]]:
    """``(attributes, inner_html)`` for each ``<li>`` of the ``<ul>`` at ``ul``."""
    ul_end = html.find(b"</ul>", ul, end)
    if ul_end < 0:
        return []
    return _LI_RE.findall(html, ul, ul_end)


def _cell_int(inner: bytes) -> int | None:
    # Nearly every cell is a bare number, so try that before stripping markup.
    if inner.isdigit():
        return int(inner)
    return _int(inner if b"<" not in inner and b"&" not in inner else _text(inner))


def _apply_row(kind: str, hour: _Hour, tag: bytes, inner: bytes) -> None:
    if kind == "iss":
        if b"fc_iss" in _attr(tag, b"class"):
            hour.iss = _text(_attr_raw(tag, b"data-content"))
    elif kind == "visibility":
        value = _float(_text(inner))
        if value is not None:
            hour.visibility = value
    elif kind == "prec_amt":
        value = _float(_text(inner))
        if value is not None:
            hour.prec_amt = value
    elif kind == "prec_type":
        src = _attr(tag, b"title") or _text(inner)
        hour.prec_type = b"none" if not src or src.lower() == b"none" else _kebab_lower(src)
    elif kind == "wind":
        cls = _attr(tag, b"class")
        if cls.startswith(b"fc_wind"):
            direction, _ = _read_word(cls, 7)
            if direction:
                hour.wind_dir = direction
        speed = _float(_text(inner))
        if speed is not None:
            hour.wind_speed = speed
        title = _attr(tag, b"title")
        lp = title.find(b"(")
        if lp >= 0:
            deg = _int(title[lp + 1 :])
            if deg is not None:
                hour.wind_deg = deg
    elif kind == "frost":
        cls = _attr(tag, b"class")
        title = _attr(tag, b"title")
        if b"No Frost" in title or b"fc_none" in cls:
            hour.frost = False
        else:
            hour.frost = b"Frost" in title or b"snowflake" in cls


def _parse_lis(html: bytes, ul: int, end: int, kind: str, day: _Day) -> None:
    cells = _lis(html, ul, end)
    # The hour-ratings row sets nhours; surplus cells are ignored.
    if day.nhours == 0:
        cells = cells[:MAX_HOURS]
        day.nhours = len(cells)
    else:
        cells = cells[: day.nhours]
    if kind in _INT_ROWS or kind in _EXTRA_ROWS:
        for hour, (_, inner) in zip(day.hours, cells):
            value = _cell_int(inner)
            if value is not None:
                setattr(hour, kind, value)
    else:
        for hour, (tag, inner) in zip(day.hours, cells):
            _apply_row(kind, hour, tag, inner)


def _parse_hour_ratings(html: bytes, s: int, e: int, day: _Day) -> None:
    block = html.find(b'class="fc_hours fc_hour_ratings"', s, e)
    if block < 0:
        return
    ul = html.find(b"<ul", block, e)
    if ul < 0:
        return
    day.nhours = 0
    for tag, inner in _lis(html, ul, e)[:MAX_HOURS]:
        cls = _attr(tag, b"class")
        if b"fc_good" in cls:
            cond = b"good"
        elif b"fc_ok" in cls:
            cond = b"ok"
        elif b"fc_bad" in cls:
            cond = b"bad"
        else:
            cond = b""
        hour = day.hours[day.nhours]
        hour.hour, _ = _read_word(_text(inner), 0)
        hour.conditions = cond
        day.nhours += 1


def _span_text(html: bytes, cls: bytes, s: int, e: int) -> bytes | None:
    p = html.find(cls, s, e)
    if p < 0:
        return None
    a = _tag_close(html, p, e)
    if a < 0:
        return None
    b = html.find(b"</span>", a, e)
    if b < 0:
        return None
    return _text(html[a + 1 : b])


def _parse_moon(html: bytes, s: int, e: int, day: _Day) -> None:
    moon = html.find(b'class="fc_moon"', s, e)
    if moon < 0:
        return
    tag = _tag_start(html, moon, s)
    gt = _tag_close(html, tag, e)
    if gt < 0:
        return
    div_end = html.find(b'class="fc_hours fc_hour_ratings"', gt, e)
    if div_end < 0:
        div_end = e

    data = _text(_attr_raw(html[tag:gt], b"data-content"))
    if data:
        q = _after_label(data, b"Time:")
        if q >= 0:
            day.mer_time, q = _read_time(data, q)
            day.mer_date, q = _read_date(data, q)
        q = _after_label(data, b"Altitude:")
        if q >= 0:
            day.mer_alt = _float(data[q:])
        q = _after_label(data, b"Distance:")
        if q >= 0:
            num, _ = _read_word(data, q)
            day.mer_dist_miles = _float(num.replace(b",", b""))
        q = _after_label(data, b"Rise:")
        if q >= 0:
            day.moon_rise, q = _read_time(data, q)
            if day.moon_rise:
                day.moon_rise_date, q = _read_date(data, q)
        q = _after_label(data, b"Set:")
        if q >= 0:
            day.moon_set, q = _read_time(data, q)
            if day.moon_set:
                day.moon_set_date, q = _read_date(data, q)

    phase = _span_text(html, b'class="fc_moon_phase"', gt, div_end)
    if phase is not None:
        day.moon_phase = phase
    pct = _span_text(html, b'class="fc_moon_percentage"', gt, div_end)
    if pct is not None:
        day.moon_pct = _int(pct)
    riseset = _span_text(html, b'class="fc_moon_riseset"', gt, div_end)
    if riseset is not None:
        rise, rp = _read_time(riseset, 0)
        if rise and not day.moon_rise:
            day.moon_rise = rise
        set_, _ = _read_time(riseset, rp)
        if set_ and not day.moon_set:
            day.moon_set = set_


def _parse_sun(html: bytes, s: int, e: int, day: _Day) -> None:
    dl = html.find(b'class="fc_daylight"', s, e)
    if dl < 0:
        return
    tag = _tag_start(html, dl, s)
    gt = _tag_close(html, tag, e)
    if gt < 0:
        return
    data = _attr_raw(html[tag:gt], b"data-content")
    if not data:
        return
    data = _text(data)
    q = _after_label(data, b"Sunrise:")
    if q >= 0:
        day.sun_rise, _ = _read_time(data, q)
    q = _after_label(data, b"Sunset:")
    if q >= 0:
        day.sun_set, _ = _read_time(data, q)
    q = _after_label(data, b"Sun Transit:")
    if q >= 0:
        day.sun_transit, _ = _read_time(data, q)
    for label, pair in (
        (b"Civil Dark:", day.civil),
        (b"Nautical Dark:", day.naut),
        (b"Astro Dark:", day.astro),
    ):
        q = _after_label(data, label)
        if q >= 0:
            pair[0], q = _read_time(data, q)
            pair[1], _ = _read_time(data, _skip_dash(data, q))


def _parse_date(html: bytes, s: int, e: int, day: _Day) -> None:
    p = html.find(b'class="fc_day_date"', s, e)
    if p < 0:
        return
    gt = _tag_close(html, p, e)
    if gt < 0:
        return
    end = html.find(b"</div>", gt, e)
    if end < 0:
        return
    text = _text(html[gt + 1 : end])
    day.weekday, q = _read_word(text, 0)
    day.day_short, _ = _read_word(text, q)


def _classify(label: bytes) -> str | None:
    for needle, kind in _ROW_LABELS:
        if needle in label:
            return kind
    return None


def _parse_detail_rows(html: bytes, s: int, e: int, day: _Day) -> None:
    needle = b'class="fc_detail_label"'
    p = s
    while True:
        lab = html.find(needle, p, e)
        if lab < 0:
            return
        gt = _tag_close(html, lab, e)
        if gt < 0:
            return
        lab_end = html.find(b"</span></span>", gt, e)
        if lab_end < 0:
            lab_end = html.find(b"</span>", gt, e)
        if lab_end < 0:
            p = gt + 1
            continue
        kind = _classify(_text(html[gt + 1 : lab_end]))
        next_lab = html.find(needle, lab_end, e)
        block_end = next_lab if next_lab >= 0 else e
        ul = html.find(b"<ul", lab_end, block_end)
        if kind is not None and ul >= 0:
            _parse_lis(html, ul, block_end, kind, day)
            if kind in _EXTRA_ROWS:
                day.has_extra = True
        p = lab_end + 1


def _parse_day(html: bytes, s: int, e: int) -> _Day:
    day = _Day()
    _parse_date(html, s, e, day)
    _parse_moon(html, s, e, day)
    _parse_hour_ratings(html, s, e, day)
    _parse_sun(html, s, e, day)
    _parse_detail_rows(html, s, e, day)
    return day


# --------------------------------------------------------------------------
# Result building
# --------------------------------------------------------------------------


def _iss_point(raw: bytes, label: bytes) -> dict[str, Any] | None:
    q = _after_label(raw, label)
    if q < 0:
        return None
    point: dict[str, Any] = {}
    time, q = _read_word(raw, q)
    if time:
        point["time"] = _str(time)
    lp = raw.find(b"(", q)
    if lp >= 0:
        direction, q = _read_word(raw, lp + 1)
        dash = raw.find(b"-", q)
        point["direction"] = _str(direction)
        point["altitude"] = _int(raw[dash + 1 :]) if dash >= 0 else None
    return point


def _iss_dict(raw: bytes) -> dict[str, Any] | None:
    if not raw:
        return None
    out: dict[str, Any] = {}
    for label, key in ((b"Start:", "start"), (b"Max:", "max"), (b"End:", "end")):
        point = _iss_point(raw, label)
        if point is not None:
            out[key] = point
    q = _after_label(raw, b"Magnitude:")
    if q >= 0:
        mag = _float(raw[q:])
        if mag is not None:
            out["magnitude"] = mag
    return out


def _distance(value: float | None, metric: bool, *, truncate: bool) -> float | None:
    """Convert miles to km (if metric) and round to 2 dp."""
    if value is None:
        return None
    if metric:
        # The site rounds visibility / wind to whole miles.
        return _round2((math.trunc(value) if truncate else value) * MILES_TO_KM)
    return _round2(value)


def _hour_dict(hour: _Hour, metric: bool, include_extra: bool) -> dict[str, Any]:
    d: dict[str, Any] = {
        "conditions": _str(hour.conditions),
        "total-clouds": hour.total_clouds,
        "low-clouds": hour.low_clouds,
        "mid-clouds": hour.mid_clouds,
        "high-clouds": hour.high_clouds,
        "visibility": _distance(hour.visibility, metric, truncate=True),
        "fog": hour.fog,
        "prec-type": _str(hour.prec_type) or "none",
        "prec-probability": hour.prec_prob,
        "prec-amount": hour.prec_amt,
        "wind": {
            "speed": _distance(hour.wind_speed, metric, truncate=True),
            "direction": _str(hour.wind_dir),
            "degrees": hour.wind_deg,
        },
        "frost": None if hour.frost is None else ("frost" if hour.frost else "none"),
        "temperature": {
            "general": hour.temp,
            "feels-like": hour.feels,
            "dew-point": hour.dew,
        },
        "rel-humidity": hour.humidity,
        "pressure": hour.pressure,
        "ozone": hour.ozone,
        "iss": _iss_dict(hour.iss),
    }
    if include_extra:
        d["extra"] = {
            "metno": {
                "total-clouds": hour.metno_total,
                "low-clouds": hour.metno_low,
                "mid-clouds": hour.metno_mid,
                "high-clouds": hour.metno_high,
            },
            "timer": {
                "cloud-cover": hour.t7_cloud,
                "seeing": hour.t7_seeing,
                "lifted-index": hour.t7_lifted,
                "transparency": hour.t7_trans,
            },
        }
    return d


def _day_dict(day: _Day, metric: bool) -> dict[str, Any]:
    hours: dict[str, Any] = {}
    for hour in day.hours[: day.nhours]:
        hours[_str(hour.hour) or "??"] = _hour_dict(hour, metric, day.has_extra)
    return {
        "date": {"long": _str(day.weekday), "short": _str(day.day_short)},
        "sun": {
            "rise": _str(day.sun_rise),
            "set": _str(day.sun_set),
            "transit": _str(day.sun_transit),
            "civil-dark": [_str(t) for t in day.civil],
            "nautical-dark": [_str(t) for t in day.naut],
            "astro-dark": [_str(t) for t in day.astro],
        },
        "moon": {
            "rise": _str(day.moon_rise),
            "set": _str(day.moon_set),
            "rise-date": _str(day.moon_rise_date),
            "set-date": _str(day.moon_set_date),
            "phase": {"name": _str(day.moon_phase), "percentage": day.moon_pct},
            "meridian": {
                "time": _str(day.mer_time),
                "date": _str(day.mer_date),
                "altitude": day.mer_alt,
                "distance": _distance(day.mer_dist_miles, metric, truncate=False),
                "distance-unit": "km" if metric else "miles",
            },
        },
        "hours": hours,
    }


def _between(html: bytes, start: bytes, stop: bytes, lo: int = 0, hi: int | None = None):
    """Return ``(text, index_after_stop)`` for the first ``start ... stop`` span."""
    hi = len(html) if hi is None else hi
    a = html.find(start, lo, hi)
    if a < 0:
        return None, lo
    b = html.find(stop, a + len(start), hi)
    if b < 0:
        return None, a
    return _text(html[a + len(start) : b]), b + len(stop)


def _strip_dot(s: bytes) -> bytes:
    return s[:-1] if s.endswith(b".") else s


def _parse_header(html: bytes) -> dict[str, Any]:
    name = lat = lon = b""
    h1, _ = _between(html, b"<h1>", b"</h1>")
    if h1 is not None:
        loc = h1[13:] if h1.startswith(b"Forecast for ") else h1
        lp, rp = loc.rfind(b"("), loc.rfind(b")")
        if lp >= 0 and rp > lp:
            inner = loc[lp + 1 : rp]
            name = loc[:lp].strip(WS)
            if b"," in inner:
                lat, lon = (part.strip(WS) for part in inner.split(b",", 1))
        else:
            name = loc.strip(WS)

    values = [b"", b"", b"", b""]  # magnitude, bortle, brightness, artificial
    sq = html.find(b"Est. Sky Quality")
    if sq >= 0:
        limit = min(sq + 800, len(html))
        cur = sq
        for i in range(4):
            text, cur = _between(html, b"<strong>", b"</strong>", cur, limit)
            if text is None:
                break
            values[i] = text
    bortle = values[1][6:] if values[1].startswith(b"Class ") else values[1]

    gen_date = gen_time = from_day = to_day = tz = b""
    h2, _ = _between(html, b"<h2>", b"</h2>")
    if h2 is not None:
        q = _after_label(h2, b"Generated:")
        if q >= 0:
            gen_date, q = _read_word(h2, q)
            gen_time, q = _read_word(h2, q)
            gen_time = _strip_dot(gen_time)
        q = _after_label(h2, b"Forecast:")
        if q >= 0:
            from_day, q = _read_word(h2, q)
            _, q = _read_word(h2, q)  # "to"
            to_day, q = _read_word(h2, q)
            to_day = _strip_dot(to_day)
        q = _after_label(h2, b"Timezone:")
        if q >= 0:
            tz, _ = _read_word(h2, q)

    return {
        "location": {"name": _str(name), "latitude": _str(lat), "longitude": _str(lon)},
        "sky-quality": {
            "magnitude": _float(values[0]),
            "bortle_class": _int(bortle),
            "brightness": {"value": _float(values[2]), "unit": "mcd/m2"},
            "artif-brightness": {"value": _float(values[3]), "unit": "ucd/m2"},
        },
        "gen-info": {
            "last-gen": {"date": _str(gen_date), "time": _str(gen_time)},
            "forecast": {"from-day": _str(from_day), "to-day": _str(to_day)},
            "timezone": _str(tz),
        },
    }


def parse_html(html: bytes, metric: bool = True) -> dict[str, Any]:
    """Parse forecast HTML bytes into the result dictionary."""
    starts: list[int] = []
    p = 0
    while len(starts) < MAX_DAYS:
        hit = html.find(b'class="fc_day"', p)
        if hit < 0:
            break
        starts.append(_tag_start(html, hit, 0))
        p = hit + 14
    if not starts:
        raise ParseError("no forecast days found; is this a Clear Outside forecast page?")

    ends = starts[1:] + [len(html)]
    days = [_parse_day(html, s, e) for s, e in zip(starts, ends)]

    out = _parse_header(html)
    out["units"] = {
        "visibility": "km" if metric else "miles",
        "wind-speed": "km/h" if metric else "mph",
        "temperature": "C",
        "precipitation": "mm",
        "pressure": "mb",
        "ozone": "du",
        "moon-distance": "km" if metric else "miles",
        "sky-brightness": "mcd/m2",
        "artificial-brightness": "ucd/m2",
    }
    out["forecast"] = {f"day-{i}": _day_dict(day, metric) for i, day in enumerate(days)}
    return out
