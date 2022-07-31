from tkinter import Tk
import tkinter as tk
from os import path
import os

from geopy.geocoders import Nominatim


class SettingsWindow:
    def __init__(self, lat=40.71, long=-74.01, location="New York", celest=0, day="3 Days (Default)", night=0):
        self.geolocator = Nominatim(user_agent="ClearOutsideWidget")
        self.lat = lat
        self.long = long
        self.location = location
        self.days = day

        self.window = Tk()
        self.window.geometry("400x180")
        self.window.title("Settings")

        self.save_and_update = tk.Button(self.window, text="Save and Update", cursor="hand2", command=lambda: self.save(
                                                                                                                True))
        self.save_and_update.grid(row=5, column=0, padx="10px", pady="20px")
        self.save_and_quit = tk.Button(self.window, text="Save and Quit", cursor="hand2", command=self.save)
        self.save_and_quit.grid(row=5, column=1, padx="10px", pady="20px")

        self.night_l = tk.Label(self.window, text='Show Only Night Hours? (21 - 4)')
        self.night_l.grid(row=0, column=0, padx="10px")
        self.celest_l = tk.Label(self.window, text='Show Sunrise/Sunset and Similar Events?')
        self.celest_l.grid(row=1, column=0, padx="10px")
        self.location_l = tk.Label(self.window, text='Current Location: %s.' % self.location)
        self.location_l.grid(row=2, column=0, padx="10px")
        self.day_l = tk.Label(self.window, text='Amount of days to show.')
        self.day_l.grid(row=3, column=0, padx="10px")

        self.loc = tk.Entry(self.window)
        self.day = None

        self.day_c = tk.StringVar()
        self.night_c = tk.IntVar()
        self.night_c.set(night)
        self.celest_c = tk.IntVar()
        self.celest_c.set(celest)

        self.choices()
        self.window.mainloop()

    def choices(self):
        night = tk.Checkbutton(self.window, variable=self.night_c, onvalue=1, offvalue=0)
        night.grid(row=0, column=1, padx="10px")

        celest = tk.Checkbutton(self.window, variable=self.celest_c, onvalue=1, offvalue=0)
        celest.grid(row=1, column=1, padx="10px")

        self.loc.bind('<Return>', self.location_get)
        self.loc.grid(row=2, column=1, padx="10px")

        options = [
            "1 Day",
            "2 Days",
            "3 Days (Default)",
            "4 Days",
            "5 Days",
            "6 Days",
            "7 Days (Max)"
        ]
        self.day_c.set(options[2])
        self.day = tk.OptionMenu(self.window, self.day_c, *options, command=self.getdays)
        self.day.grid(row=3, column=1, padx="10px")

    def location_get(self, value):
        value = self.loc.get()
        self.lat, self.long = round(self.geolocator.geocode(value).latitude, 2), round(self.geolocator.geocode(value)
                                                                                       .longitude, 2)
        self.location = self.geolocator.geocode(value).address.split(", ")[0]
        self.settext(str(self.lat) + " " + str(self.long), self.location)

    def settext(self, text, location):
        self.loc.delete(0, last=len(self.loc.get()))
        self.loc.insert(0, text)
        self.location_l.config(text='Current Location: %s' % self.location)
        return

    def getdays(self, day):
        if day != "3 Days (Default)":
            self.days = day

    def save(self, update=False):
        # script_path = path.dirname(__file__)
        # filepath = path.abspath(path.join(script_path, "..", "config.cfg"))
        filepath = "config.cfg"
        cfg = open(filepath, "w")
        cfg.write("Night: %i\n" % self.night_c.get())
        cfg.write("Celest: %i\n" % self.celest_c.get())
        cfg.write("Latitude: %f\n" % self.lat)
        cfg.write("Longitude: %f\n" % self.long)
        cfg.write("Location: %s\n" % self.location)
        cfg.write("Days: %s" % self.days)
        cfg.close()
        if update:
            os.system(os.path.join(os.getcwd(), "clearoutside-api.exe -u"))
        self.window.destroy()
