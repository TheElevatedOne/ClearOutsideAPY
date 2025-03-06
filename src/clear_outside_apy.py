import requests
from bs4 import BeautifulSoup


class ClearOutsideAPY:
    def __init__(self, lat: str, long: str, view: str = "midday") -> None:
        """
        ClearOutsideAPI(lat: str, long: str, view: str = "midday")
        lat - latitude with 2 decimal places
        long - longitude with 2 decimal places
        view: "current" for current hour at the beginning
              "midday" for midday at the beginning
              "midnight" for midnight at the beginning
        """
        if len(long) < 4 or len(lat) < 4:
            raise SystemExit("Parameter long or lat is badly specified")

        self.url = f"https://clearoutside.com/forecast/{lat}/{long}?view={view}"
        request = requests.get(self.url)
        self.soup = BeautifulSoup(request.content, "html5lib")

        pass

    def update(self) -> None:
        """
        Update Weather Information
        Pull New Data From The Website
        """
        request = requests.get(self.url)
        self.soup = BeautifulSoup(request.content, "html5lib")

    def pull(self) -> dict:
        """
        Function to pull data/web-scrape
        """
        content = self.soup.find("div", attrs={"class": "container content"})

        # sky_quality
        skyq_raw = content.find("span", {"class": "btn"}).get_text()
        skyq_raw = (skyq_raw.split(": ")[1] + " ").split(". ")
        skyq_raw.pop()
        skyq_raw = [x.replace("\xa0", "").split(" ") for x in skyq_raw]
        skyq = {
            "magnitude": skyq_raw[0][0],
            "bortle_class": skyq_raw[1][1],
            "brightness": [skyq_raw[2][0], skyq_raw[2][1]],
            "artif-brightness": [skyq_raw[3][0], skyq_raw[3][1].replace("\u03bc", "")],
        }

        # Website last update
        geninfo_raw = content.find("h2").get_text().split(". ")
        geninfo_raw = [x.split(" ") for x in geninfo_raw]
        geninfo = {
            "last-gen": {
                "date": geninfo_raw[0][1],
                "time": geninfo_raw[0][2],
            },
            "forecast": {"from-day": geninfo_raw[1][1], "to-day": geninfo_raw[1][-1]},
            "timezone": geninfo_raw[-1][1],
        }

        # forecast
        forecast_days_raw = content.find("div", {"class": "fc"}).findAll(
            "div", {"class": "fc_day"}
        )

        forecast = {"gen-info": geninfo, "sky-quality": skyq, "forecast": {}}

        for q, day in enumerate(forecast_days_raw):
            date_raw = day.find("div", {"class": "fc_day_date"}).get_text().split(" ")
            date = {"long": date_raw[0], "short": date_raw[1]}

            moon_raw = day.find("div", {"class": "fc_moon"})
            moon_phase_raw = [
                moon_raw.find("span", {"class": "fc_moon_phase"}).get_text(),
                moon_raw.find("span", {"class": "fc_moon_percentage"}).get_text(),
            ]
            moon_meridian_raw = moon_raw["data-content"].split(" ")
            moon = {
                "rise": moon_meridian_raw[-7],
                "set": moon_meridian_raw[-2],
                "phase": {"name": moon_phase_raw[0], "percentage": moon_phase_raw[1]},
            }

            sunlight_raw_ = (
                day.find("div", {"class": "fc_daylight"}).get_text().split(".")
            )
            sunlight_raw_.pop(1)
            sunlight_raw = []
            for i in sunlight_raw_:
                t = i.split(" ")
                [sunlight_raw.append(x.replace(",", "")) for x in t]
            sunlight = {
                "rise": sunlight_raw[3],
                "set": sunlight_raw[5],
                "transit": sunlight_raw[7],
                "civil-dark": [sunlight_raw[11], sunlight_raw[13]],
                "nautical-dark": [sunlight_raw[17], sunlight_raw[19]],
                "astro-dark": [sunlight_raw[23], sunlight_raw[25]],
            }

            hours_raw = [
                x.get_text()[1:].split(" ")
                for x in day.find("div", {"class": "fc_hours fc_hour_ratings"}).findAll(
                    "li"
                )
            ]
            details_raw_ = [
                x.findAll("li")
                for x in day.find("div", {"class": "fc_detail hidden-xs"}).findAll(
                    "div", {"class": "fc_detail_row"}
                )
            ]
            details_raw = []
            for c, i in enumerate(details_raw_):
                match c:
                    case 4:  # iss - not implementing yet
                        continue
                    case 7:  # precip
                        x = []
                        for j in i:
                            x.append(j["title"].replace(" ", "-").lower())
                    case 10:  # wind
                        x = []
                        for j in i:
                            w_dir = j["class"][1]
                            w_speed = j.get_text()
                            x.append([w_dir, w_speed])
                    case 11:  # frost
                        x = []
                        for j in i:
                            frost = "none"
                            if j["class"] != "fc_none":
                                frost = "frost"
                            x.append(frost)
                    case _:  # general
                        if (c == 12) or (c == 13) or (c == 14):
                            x = [x.get_text() for x in i]
                        else:
                            x = [x.get_text().replace("-", "0") for x in i]
                details_raw.append(x)

            hours = {}
            for c, h in enumerate(hours_raw):
                hours[str(h[0])] = {
                    "conditions": h[1].lower(),
                    "total-clouds": details_raw[0][c],
                    "low-clouds": details_raw[1][c],
                    "mid-clouds": details_raw[2][c],
                    "high-clouds": details_raw[3][c],
                    "visibility": str(round(int(details_raw[4][c]) * 1.609344, 2)),
                    "fog": details_raw[5][c],
                    "prec-type": details_raw[6][c],
                    "prec-probability": details_raw[7][c],
                    "prec-amount": details_raw[8][c],
                    "wind": {
                        "speed": str(round(int(details_raw[9][c][1]) * 1.609344, 2)),
                        "direction": details_raw[9][c][0],
                    },
                    "frost": details_raw[10][c],
                    "temperature": {
                        "general": details_raw[11][c],
                        "feels-like": details_raw[12][c],
                        "dew-point": details_raw[13][c],
                    },
                    "rel-humidity": details_raw[14][c],
                    "pressure": details_raw[15][c],
                    "ozone": details_raw[16][c],
                }
            day = {"date": date, "sun": sunlight, "moon": moon, "hours": hours}

            forecast["forecast"][f"day-{q}"] = day

        return forecast
