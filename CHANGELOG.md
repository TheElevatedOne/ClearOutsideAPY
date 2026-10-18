# Changelog

## ClearOutsideAPY 3.0.0

Now a Cloudflare Python Worker instead of a PyPI package with a C extension.

### Worker / HTTP API
- `GET /forecast/{lat}/{lon}` with `view`, `experimental` and `units` query
  parameters returns the forecast as JSON. `GET /` describes the API.
- Errors are JSON with status codes: 400 for bad input, 404, 405, and 502 when
  clearoutside.com is unreachable or returns a page that is not a forecast.
- CORS is open to any origin.
- Caching: the upstream page is cached by Cloudflare (`cf.cacheTtl`), and
  responses go through the Workers Cache API and carry `Cache-Control`.
  `CACHE_TTL` in `wrangler.jsonc` controls all three (default 900 s).
- Run with `uv run pywrangler dev` and deploy with `uv run pywrangler deploy`.

### Library
- The C parser is ported to pure Python (`clear_outside_apy.parser`), because
  Pyodide cannot load custom C extensions. Output is identical to 2.0 on all
  test fixtures, in both metric and imperial units.
- Downloads use the Workers `fetch` API with an `AbortSignal` timeout,
  replacing `urllib`.

### Breaking changes vs 2.x
- `ClearOutsideAPY.update()`, `ClearOutsideAPY.pull()`, `fetch_forecast()`
  and `fetch_html()` are now `async`, and they only run inside the Workers
  runtime. `parse()` still works anywhere.
- `ClearOutsideAPY(...)` no longer downloads in `__init__`, and the `fetch=`
  argument is gone. `pull()` downloads on first use.
- New `cache_ttl=` option (upstream cache seconds, `0` to disable).
- The CLI (`clear-outside-apy`, `python -m clear_outside_apy`), the PyPI build
  (`setup.py`, `build.sh`, cibuildwheel config) and the C extension were removed.

## ClearOutsideAPY 2.0.0

Rewrite. The 1.x BeautifulSoup / html5lib scraper was slow, index-based, and
incomplete. 2.0 is a C parser behind the same `ClearOutsideAPY` import.

### Speed
- HTML is scanned in C instead of html5lib + BeautifulSoup (about 1–2 ms to
  parse a full 7-day page; the old stack was hundreds of milliseconds).
- HTTP uses the standard library (`urllib`). No `requests`, `bs4`, or
  `html5lib` runtime dependency.

### Completeness / bug fixes
- Moon meridian is parsed from the popover (`time`, `date`, `altitude`,
  `distance`) instead of the broken split-on-spaces hack that 1.0.1 removed.
- `No Rise` / `No Set` for the moon (and empty sun fields) become `None`.
- ISS passover is included per hour: start / max / end time, azimuth,
  altitude, and magnitude.
- Wind compass degrees are taken from the cell title.
- Frost actually works. 1.x compared a BeautifulSoup class *list* to the
  string `"fc_none"`, so every hour was reported as frost.
- Missing visibility / fog (`-` on the site) is `None`, not `0.0`.
- Precipitation types such as `very-light-rain` and `ice-pellet` are kept.
- Optional experimental Met.no and 7Timer rows (`experimental=True`).
- Location name and coordinates are in the result.
- Invalid coordinates raise `InvalidLocationError` instead of `SystemExit`.

### Packaging
- Installable package layout: `from clear_outside_apy import ClearOutsideAPY`.
- `./build.sh` produces the PyPI source tarball and a wheel.
- Linux wheels are retagged with auditwheel to `manylinux_*`. PyPI no longer
  accepts `linux_x86_64`.
- Console script: `clear-outside-apy LAT LON`.

### Breaking changes vs 1.x
- Numeric fields are numbers (`int` / `float`), not strings.
- Sky brightness is `{value, unit}` rather than a two-element list.
- Artificial brightness unit is `ucd/m2` (microcandela), which is what the
  site publishes. 1.x labelled it `cd/m2`.
- Moon phase percentage is an integer (`8`), not `"8%"`.

## ClearOutsideAPY 1.0.1

- Removed Moon Meridian as a temporary fix
  - The brute-force method missed a case
  - Patching and debugging it would take hours which I currently don't have
  - Will be Patched Later
