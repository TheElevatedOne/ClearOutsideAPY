"""CLI: python -m clear_outside_apy LAT LON"""

from __future__ import annotations

import argparse
import json
import sys

from . import ClearOutsideAPY, __version__
from .client import VIEWS
from .exceptions import ClearOutsideError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clear-outside-apy",
        description="Download and parse a clearoutside.com forecast.",
    )
    parser.add_argument("lat", help="Latitude (decimal degrees)")
    parser.add_argument("lon", help="Longitude (decimal degrees)")
    parser.add_argument(
        "--view",
        choices=VIEWS,
        default="midday",
        help="Hour alignment (default: midday)",
    )
    parser.add_argument(
        "--experimental",
        action="store_true",
        help="Include Met.no / 7Timer extra rows",
    )
    parser.add_argument(
        "--imperial",
        action="store_true",
        help="Keep miles / mph instead of converting to km / km/h",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    try:
        client = ClearOutsideAPY(
            args.lat,
            args.lon,
            view=args.view,
            experimental=args.experimental,
            metric=not args.imperial,
            timeout=args.timeout,
        )
        json.dump(client.pull(), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    except ClearOutsideError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
