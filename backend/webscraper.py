from bs4 import BeautifulSoup
from backend.read_config import Read
import requests, os, webbrowser


class GetData:
    def __init__(self):
        read = Read()
        url = read.load("url")
        req_data = requests.get(url)
        self.soup = BeautifulSoup(req_data.content, "html.parser")
        if not self.soup:
            webbrowser.open(url)

        self.day_range = read.load("day")
        self.current_fc = []
        for day in range(self.day_range):
            self.current_fc.append({})
        self.hours_info = []

        self.celest = read.load("celest")
        self.night = read.load("night")

    def find_data(self):
        current_data = []

        for day in range(self.day_range):
            current_data += self.soup.find_all("div", id="day_%i" % day)

        for day in range(self.day_range):
            self.current_fc[day]["Day"] = current_data[day].find_next('div', class_="fc_day_date").find_all('span')[
                0].get_text()
            self.current_fc[day]["Date"] = \
                current_data[day].find_next('div', class_="fc_day_date").get_text().split()[1]
            self.current_fc[day]["Weather"] = {}

            # Hours, Total Cloud, Rain Probability, Wind Speed, Temperature, Humidity
            self.hours_info.append([
                current_data[day].find_all_next("div", class_="fc_hour_ratings")[0].find_all_next("ul"),
                current_data[day].find_all_next("div", class_="fc_moonlight")[0].find_next(
                    "span").get_text()])

    def create_dict(self):
        for day in range(self.day_range):
            hours = [x.split() for x in [x.get_text() for x in self.hours_info[day][0][0]] if x != " "]
            hours.pop()
            
            celestial_time = self.hours_info[day][1].split(". ")

            total_cloud = [x + "%" for x in [x.get_text() for x in self.hours_info[day][0][1]] if x != " "]
            rain_prob = [x + "%" for x in [x.get_text() for x in self.hours_info[day][0][9]] if x != " "]
            wind_speed = [str(round(int(x) * 1.609, 1)) + " kmh" for x in [x.get_text() for x in self.hours_info[day][0][11]
                                                                       ] if x != " " and x != "\n"]
            temp = [x for x in [x.get_text() for x in self.hours_info[day][0][13]] if x != " "]
            humid = [x + "%" for x in [x.get_text() for x in self.hours_info[day][0][16]] if x != " "]
            
            names = ["Status", "Total-Cloud", "Rain-Probability", "Wind-Speed", "Temperature",
                     "Humidity"]
            
            counter = 0

            self.current_fc[day]["Celestial-Time"] = celestial_time

            for hour in hours:
                ct = hour[0]
                if self.night:
                    if ct in ["21", "22", "23", "00", "01", "02", "03", "04"]:
                        self.add_to_dict(names, ct, day, counter, [hour, total_cloud, rain_prob,
                                                                   wind_speed, temp, humid])
                else:
                    self.add_to_dict(names, ct, day, counter, [hour, total_cloud, rain_prob,
                                                               wind_speed, temp, humid])
                counter += 1
        return self.current_fc

    def add_to_dict(self, names, ct, day, counter, stuff):
        self.current_fc[day]["Weather"][ct] = {}
        for name in names:
            if names.index(name) == 0:
                self.current_fc[day]["Weather"][ct][name] = stuff[0][1]
            elif names.index(name) == 2:
                self.current_fc[day]["Weather"][ct][name] = stuff[1][counter]
            elif names.index(name) == 3:
                self.current_fc[day]["Weather"][ct][name] = stuff[2][counter]
            elif names.index(name) == 4:
                self.current_fc[day]["Weather"][ct][name] = stuff[3][counter]
            elif names.index(name) == 5:
                self.current_fc[day]["Weather"][ct][name] = stuff[4][counter]
            else:
                self.current_fc[day]["Weather"][ct][name] = stuff[5][counter]
