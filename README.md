# ClearOutsideAPY

## Webscraper/API for ClearOutside.com

Python module for scraping and parsing data from [clearoutside.com](https://clearoutside.com)

Created using [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/), [requests](https://pypi.org/project/requests/) and [html5lib](https://pypi.org/project/html5lib/).

## Installation
From repo:
```
pip install git+https://github.com/TheElevatedOne/ClearOutsideAPY.git
```

## Usage

```python
from clear_outside_apy import ClearOutsideAPY

api = ClearOutsideAPY(lat: str, long: str, view: str = "midday")
api.update()
result = api.pull()
```
- `lat` -> latitude with two decimal places
- `long` -> longitude with two decimal places
  - ex. `lat = "43.16", long = "-75.84"` -> [New York](https://clearoutside.com/forecast/43.16/-75.84)  
- `view` -> string in three formats: 
  - `midday` -> start at 12pm/12:00
  - `midnight` -> start at 12am/24:00
  - `current` -> start at current time
    

- `__init__` -> initializes the class, scrapes the website for the first time <br>
- `update()` -> scrapes the website <br>
- `pull()` -> parses and pulls the data; returns a giant dictionary

## Output Preview

### Units:
**This Module outputs everything in Metric Units and European/Military time (24h)**
- Date format: dd/MM/yy,
- Sky Quality:
  - Brightness - millicandela per meter squared,
  - Artificial Brightness - candela per meter squared,
- Distance/Visibility: kilometers; (if showing 0.0, data is missing from the website),
- Rain: millimeters,
- Speed: kilometers per hour
- Temperature: degrees Celsius
- Pressure: millibars
- Ozone: Dobson Unit (du)

### Result:
Showing a piece of resulting dictionary in json format.

The entire dictionary is around 4000 lines long in json format as it shows 17 types of information per hour in a day for 24 hours and 7 days.

```json
```
