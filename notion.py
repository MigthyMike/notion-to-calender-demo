import json
import time

import requests
from datetime import datetime
from termcolor import colored

from utilities import create_log


class Notion:
    def __init__(self,
                 user_secret: str,
                 database_id: str,
                 title_header: str,
                 date_header: str,
                 message_id_header: str):

        self.__UserSecret = user_secret
        self.__DatabaseId = database_id
        self.__TitleHeader = title_header
        self.__DateHeader = date_header
        self.__Message_IDHeader = message_id_header

        self.__NotionVersion = "2022-02-22"
        self.__Headers = {"Authorization": f"Bearer {user_secret}",
                          "Notion-Version": self.__NotionVersion}

        self.check_database()

    def check_database(self):
        create_log("Checking notion database.", "yellow")

        result = requests.get(f"https://api.notion.com/v1/databases/{self.__DatabaseId}",
                              headers=self.__Headers)

        if result.status_code != 200:
            create_log("There was a problem with getting Notion database!", "red")
            exit(-1)

        data = result.json()
        prop = data["properties"]

        if self.__DateHeader in prop and self.__TitleHeader in prop:
            create_log("Notion database OK.", "green")

            if self.__Message_IDHeader not in prop:
                self.create_header(self.__Message_IDHeader, "rich_text")

        else:
            create_log("Invalid rows in Notion database", "red")
            exit(-1)

    def create_header(self, header, data_type):
        create_log("Creating MessageID field in database.", "yellow")
        data = {"properties": {
            header:
                {
                    data_type: {}
                }
        }}
        result = requests.patch(f"https://api.notion.com/v1/databases/{self.__DatabaseId}",
                                headers=self.__Headers,
                                json=data)
        if result.status_code != 200:
            create_log(f"Failed to add the '{header} with datatype '{data_type}' to the notion database!", "red")
            exit(-1)
        else:
            create_log(f"'{self.__Message_IDHeader}' field created in notion database.", "green")

    def get_database(self) -> list:
        today = datetime.today().strftime('%Y-%m-%d')
        rule = {
            "filter": {
                "and": [
                    {
                        "property": self.__DateHeader,
                        "date": {
                            "is_not_empty": True
                        }
                    },
                    {
                        "property": self.__DateHeader,
                        "date": {
                            "on_or_after": today
                        }
                    }
                ]
            },
            "sorts": [
                {
                    "property": "Due",
                    "direction": "ascending"
                }
            ]
        }

        response = requests.post(url=f"https://api.notion.com/v1/databases/{self.__DatabaseId}/query",
                                 headers=self.__Headers,
                                 json=rule)

        if response.status_code != 200:
            create_log("problem getting events from the database!", "red")
            return []

        data = response.json()

        events = []
        for event in data["results"]:
            title = event["properties"][self.__TitleHeader]["title"][0]["text"]["content"]
            due = event["properties"][self.__DateHeader]["date"]
            event_id = event["id"]

            msg_id = None
            if len(event["properties"][self.__Message_IDHeader]["rich_text"]) > 0:
                msg_id = event["properties"][self.__Message_IDHeader]["rich_text"][0]["text"]["content"]

            events.append({"title": title,
                           "due": due,
                           "msg_id": msg_id,
                           "id": event_id})
        return events

    def update_message_id(self, google_calendar_id: str, page_id: str):
        data = {
            "properties": {
                self.__Message_IDHeader: {"rich_text": [{"text": {"content": google_calendar_id}}]}
            }
        }
        response = requests.patch(url=f"https://api.notion.com/v1/pages/{page_id}",
                                  headers=self.__Headers,
                                  json=data)

        if response.status_code != 200:
            create_log(f"Notion failed to update the {self.__Message_IDHeader}!", "red")
            exit(-1)

    def get_body(self, page_id: str):
        body_text = ""
        response = requests.get(url=f"https://api.notion.com/v1/blocks/{page_id}/children",
                                headers=self.__Headers)

        if response is not None:
            try:
                body = json.loads(response.text)
                for ob in body["results"]:
                    try:
                        body_text += ob["paragraph"]["text"][0]["text"]["content"] + "\n"
                    except IndexError:
                        continue
                    except KeyError:
                        continue
            except json.decoder.JSONDecodeError:
                pass

        return body_text

    def check_if_exists(self, event_id: str) -> bool:
        rule = {
            "filter": {
                "property": self.__Message_IDHeader,
                "rich_text": {
                    "equals": event_id
                }
            }
        }

        while True:
            response = requests.post(url=f"https://api.notion.com/v1/databases/{self.__DatabaseId}/query",
                                     headers=self.__Headers,
                                     json=rule)

            if response.status_code == 400:
                return False

            # there as an error
            try:
                response = json.loads(response.text)
            except json.decoder.JSONDecodeError:
                time.sleep(1)
                continue

            if not response["results"]:
                return False
            else:
                return True
