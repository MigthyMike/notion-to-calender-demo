from termcolor import colored
from datetime import datetime


def create_log(msg, colour):
    time_stamp = datetime.now().strftime("%Y-%m-%d, %H:%M")
    print(colored(f"{time_stamp} -> {msg}", colour))
