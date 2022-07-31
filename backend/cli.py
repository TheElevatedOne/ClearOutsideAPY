import argparse


def parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--settings", help="Show Settings Window", action="store_true")
    parser.add_argument("-u", "--update", help="Get New Data", action="store_true")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    parse()
