import time
from time import sleep

import requests
from decouple import config

from google_calender import Google
from notion import Notion
from termcolor import colored

import os

from utilities import create_log


def main():
    # check if the env file exists
    check_for_env_file()

    # get the vars from .env file
    user_secret = config('ClientSecret', default=-1)
    database_id = config('DatabaseId', default=-1)
    title_header = config("TitleHeader", default=-1)
    date_header = config("DateHeader", default=-1)
    sleep_freq = None

    try:
        sleep_freq = config("Frequency", default=60, cast=int)
    except ValueError:
        create_log("Value of Frequency must be a number", "red")
        exit()

    calendar_name = config("CalendarName", default="notion")

    google_reminder = None
    try:
        google_reminder = config("GoogleReminder", default=False, cast=bool)
    except ValueError:
        create_log("GoogleReminder can be either True or False", "red");
        exit()

    google_reminder_time = None
    try:
        google_reminder_time = config("GoogleReminderTime", default=15, cast=int)
    except ValueError:
        create_log("GoogleReminderTime must be a number", "red")
        exit()

    # validates the existence of the vars
    check_env_vars(database_id, date_header, title_header, user_secret)

    # Create Notion and validates it
    notion = Notion(user_secret=user_secret,
                    database_id=database_id,
                    title_header=title_header,
                    date_header=date_header,
                    message_id_header="Message_ID")

    # Create Google and validates it
    google = Google(calender_name=calendar_name,
                    calender_reminder=google_reminder,
                    calender_reminder_time=google_reminder_time)

    main_loop(google, notion, sleep_freq)


def main_loop(google, notion, sleep_freq):
    while True:
        notion_events = notion.get_database()

        for notion_event in notion_events:
            handle_notion_event(google, notion, notion_event)

        check_if_delete_event(google, notion)

        create_log(f"Finished syncing, going sleep for {sleep_freq}", "green")
        sleep(sleep_freq)


def handle_notion_event(google, notion, notion_event):
    start_time = notion_event["due"]["start"]
    end_time = notion_event["due"]["end"]

    # create an event with start and end time
    if start_time is not None and end_time is not None and not notion_event["msg_id"]:
        create_event(google, notion, notion_event, start_time, end_time)

    # crete an event with only start time
    elif start_time is not None and not notion_event["msg_id"]:
        create_event(google, notion, notion_event, start_time, start_time)

    # update an event with start and end time
    elif notion_event["msg_id"] and start_time and end_time:
        patch_event(google, notion, notion_event, start_time, end_time)

    # update an event with only start time
    elif notion_event["msg_id"] and start_time:
        patch_event(google, notion, notion_event, start_time, start_time)

    # Delete event if the notion event has MessageID but no longer the start and end time
    if notion_event["msg_id"] and start_time is None and end_time is None:
        delete_event(google, notion, notion_event)


def check_if_delete_event(google, notion):
    # Check if the event was deleted in the notion
    events = google.get_events()
    for event in events:
        exists_in_notion = notion.check_if_exists(event["id"])
        if not exists_in_notion:
            google.delete_event(event["id"])


def delete_event(google, notion, notion_event):
    create_log(f"Deleting event'{notion_event}' because it has no start and end time", "yellow")
    google.delete_event(notion_event["msg_id"])
    notion.update_message_id("", notion_event["id"])


def patch_event(google, notion, notion_event, start, end):
    body_text = notion.get_body(notion_event["id"])
    google.patch_event(summary=notion_event["title"],
                       description=body_text,
                       start_time=start,
                       end_time=end,
                       event_id=notion_event["msg_id"])


def create_event(google, notion, notion_event, start, end):
    body_text = notion.get_body(notion_event["id"])
    calendar_id = google.create_event(summary=notion_event["title"],
                                      description=body_text,
                                      start_time=start,
                                      end_time=end)
    if calendar_id == -1:
        create_log(f"Time miss-match when creating event {notion_event['title']}", "red")
    else:
        notion.update_message_id(calendar_id, notion_event["id"])


def check_for_env_file():
    if not os.path.exists(".env"):
        create_log("missing .env file", "red")
        exit(-1)


def check_env_vars(database_id, date_header, title_header, user_secret):
    if user_secret == -1:
        handle_missing_env_var("ClientSecret")
    if database_id == -1:
        handle_missing_env_var("DatabaseId")
    if title_header == -1:
        handle_missing_env_var("TitleHeader")
    if date_header == -1:
        handle_missing_env_var("DateHeader")


def handle_missing_env_var(var_missing: str):
    create_log(f"'{var_missing}' missing in the .env", "red")
    exit(-1)


if __name__ == "__main__":
    while True:
        try:
            main()
        except requests.exceptions.ConnectionError as error:
            create_log(f"There was an error sending request to the website, details='{error.request}'", "red")
            time.sleep(10)

        # except Exception as e:
        #     create_log(f"There was an unexpected error '{e.args}'", "red")
        #     time.sleep(10)
