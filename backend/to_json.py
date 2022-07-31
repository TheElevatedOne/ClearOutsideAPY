import json


class ToJson:
    def __init__(self, fc_dict):
        self.fc_dict = fc_dict

    def create_file(self):
        json_object = json.dumps(self.fc_dict, indent=4)
        file = open("current_data.json", "w")
        file.write(json_object)
        file.close()


