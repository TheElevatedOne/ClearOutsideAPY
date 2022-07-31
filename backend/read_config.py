from os import path


class Read:
    def __init__(self):
        self.value = None

        # script_path = path.dirname(__file__)
        # filepath = path.abspath(path.join(script_path, "..", "config.cfg"))
        filepath = "config.cfg"
        try:
            self.config = open(filepath, "r")
            self.file = self.read()
        except:
            self.value = "Empty"

    def load(self, value):
        if self.value == "Empty":
            return

        if value == "url":
            url = "https://clearoutside.com/forecast/%s/%s?view=midday" % (str(round(float(self.file[2][1]), 2)),
                                                                         str(round(float(self.file[3][1]), 2)))
            return url
        elif value == "location":
            return round(float(self.file[2][1]), 2), round(float(self.file[3][1]), 2), self.file[4][1]
        elif value == "night":
            return bool(int(self.file[0][1]))
        elif value == "celest":
            return bool(int(self.file[1][1]))
        else:
            return int(self.file[5][1][0])

    def read(self):
        file = [x.strip().split(": ") for x in self.config.readlines()]
        return file
