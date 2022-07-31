from backend.webscraper import GetData
from backend.cli import parse
from backend.to_json import ToJson
from frontend.settings import SettingsWindow
from backend.read_config import Read


if __name__ == "__main__":
    args = parse()
    if args.settings:
        read = Read()

        location = read.load("location")
        night = read.load("night")
        celest = read.load("celest")
        days = read.load("day")

        if location is not None:
            SettingsWindow(location[0], location[1], location[2], celest, days, night)
        else:
            SettingsWindow()
    elif args.update:
        website = GetData()
        website.find_data()
        fc_dict = website.create_dict()
        ToJson(fc_dict).create_file()

