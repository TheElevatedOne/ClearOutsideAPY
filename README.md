# ClearOutsideAPY

## Webscraper/API for ClearOutside.com

Python module for scraping and pulling data from clearoutside.com

Created using BeautifulSoup

## Usage

```python
from clear_outside_api import ClearOutsideAPI

api = ClearOutsideAPI(long, lat, view)
api.update()
result = api.pull()
```

> long -> longitude with two decimal places in either float or string type <br>
> lat -> latitude with two decimal places in either float or string type <br>
> view - string in three formats:
>> "midday" - start at 12pm/12:00; "midnight" - start at 12am/24:00; "current" - start at current time  

> `__init__` -> initializes the class, scrapes the website for the first time <br>
> `update()` -> scrapes the website <br>
> `pull()` -> parses and pulls the data; returns a giant dictionary

### Result Preview and Information

- Units are metric:
  - km/s for wind,
  - mm for rain,
  - etc.

```json
{
    "gen-info": {
        "last-gen": {   # Date & Time of last update
            "date": "19/02/25",
            "time": "04:26:05"
        },
        "forecast": {   # Range of dates
            "from-day": "19/02/25",
            "to-day": "25/02/25"
        },
        "timezone": "UTC+1.00"
    },
    "sky-quality": {  # Sky Quality for specified location
        "magnitude": "21.08",
        "bortle_class": "4",
        "brightness": [
            "0.4",
            "mcd/m2"
        ],
        "artif-brightness": [
            "227.54",
            "cd/m2"
        ]
    },
    "forecast": {
        "day-0": {
            "date": { 
                "long": "Wednesday",
                "short": "19"
            },
            "sun": {    # Sun times and ranges of darkness
                "rise": "06:46",
                "set": "17:15",
                "transit": "12:01",
                "civil-dark": [
                    "17:47",
                    "06:14"
                ],
                "nautical-dark": [
                    "18:23",
                    "05:38"
                ],
                "astro-dark": [
                    "18:59",
                    "05:02"
                ]
            },
            "moon": {   # Moon information
                "rise": "23:50",
                "set": "08:59",
                "phase": {
                    "name": "Waning Gibbous",
                    "percentage": "65%"
                },
                "meridian": {
                    "time": "04:29",
                    "altitude": "21.6",
                    "distance": "404161.0"
                }
            },
            "hours": {
                "12": {
                    "conditions": "ok",
                    "total-clouds": "46",  # Clouds are in percentages
                    "low-clouds": "43",
                    "mid-clouds": "0",
                    "high-clouds": "0",
                    "visibility": "0.0", # if 0, then the data is missing from the website
                    "fog": "0",
                    "prec-type": "none",
                    "prec-probability": "0",
                    "prec-amount": "0",
                    "wind": {
                        "speed": "8.05",
                        "direction": "north-west"
                    },
                    "frost": "frost",
                    "temperature": {
                        "general": "2",
                        "feels-like": "-1",
                        "dew-point": "-9"
                    },
                    "pressure": "43", # in mbar
                    "ozone": "1028" # in du
                },
                "11": {...}
            }
        },
        "day-1": {...}
    }
}
```

```
```
