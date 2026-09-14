# Changelog

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
- `./build.sh` produces the PyPI source tarball and wheel.
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
