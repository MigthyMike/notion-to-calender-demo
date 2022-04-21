import os
import pickle
import time

import google.auth.transport.requests
from apiclient import discovery
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime, timedelta

from utilities import create_log

from googleapiclient import errors


class Google:
    def __init__(self,
                 cred_location='creds/credentials.json',
                 token_location='creds/token.pickle',
                 calender_name="notion",
                 calender_reminder=False,
                 calender_reminder_time=15):
        self.__SCOPES = ['https://www.googleapis.com/auth/calendar']
        self.__CRED_LOCATION = cred_location
        self.__TOKEN_LOCATION = token_location
        self.__CALENDER_NAME = calender_name
        self.__CALENDER_ID = None

        self.__CALENDER_REMINDER = calender_reminder
        self.__CALENDER_REMINDER_TIME = calender_reminder_time

        # check if credentials.json is present
        self.__check_for_creds()

        self.__Google_Refresh = google.auth.transport.requests.Request()
        self.__Google_Flow = InstalledAppFlow.from_client_secrets_file(self.__CRED_LOCATION, self.__SCOPES)

        self.__Creds = self.__get_credentials()
        self.__Google_Service = discovery.build('calendar', 'v3', credentials=self.__Creds, static_discovery=False)

        # Checks if the calendar is present, if not it will be created
        self.__check_calendar()

    # check if the credentials.json exists
    def __check_for_creds(self):
        if not os.path.exists(self.__CRED_LOCATION):
            create_log(f"'{self.__CRED_LOCATION}' is missing!", "red")
            exit(-1)
        else:
            create_log("Google credentials present.", "green")

    # gets the token to access the Google api
    def __get_credentials(self):
        creds = None

        # get the credentials
        if os.path.exists(self.__TOKEN_LOCATION):
            create_log("Token present, loading...", "green")
            with open(self.__TOKEN_LOCATION, 'rb') as token:
                creds = pickle.load(token)

        # check if there is need to get or  refresh the token
        if not creds or not creds.valid:
            # check if it can refresh the creds automatically
            if creds and creds.expired and creds.refresh_token:
                create_log("Refreshing token automatically.", "green")
                try:
                    creds.refresh(self.__Google_Refresh)
                except google.auth.exceptions.RefreshError:

                    create_log("Auto refresh failed, manual refresh needed.", "red")
                    creds = self.__Google_Flow.run_console()
            else:
                # create a flow to login user
                create_log("Auto refresh failed, manual refresh needed.", "yellow")
                creds = self.__Google_Flow.run_console()

            # saves the credentials
            with open(self.__TOKEN_LOCATION, 'wb') as token:
                pickle.dump(creds, token)

        if creds.valid:
            create_log("Token loaded successfully.", "green")
            return creds
        else:
            create_log("Failed to load the credentials!", "red")
            exit(-1)

    # get the info about one event
    def get_event(self, event_id):
        if self.__Creds.expired:
            self.__Creds = self.__get_credentials()
            self.__Google_Service = discovery.build('calendar', 'v3', credentials=self.__Creds, static_discovery=False)

        event = self.__Google_Service.events().get(calendarId=self.__CALENDER_ID, eventId=event_id).execute()
        return event

    # returns all the events from the Google calendar
    def get_events(self):
        if self.__Creds.expired:
            self.__Creds = self.__get_credentials()
            self.__Google_Service = discovery.build('calendar', 'v3', credentials=self.__Creds, static_discovery=False)

        now = datetime.utcnow().isoformat() + 'Z'
        events_result = self.__Google_Service.events().list(
            calendarId=self.__CALENDER_ID,
            timeMin=now,
            maxResults=20,
            singleEvents=True,
            orderBy='startTime').execute()

        events = events_result.get('items', [])
        return events

    # Used to validate the calendar
    def __check_calendar(self):
        if self.__Creds.expired:
            self.__Creds = self.__get_credentials()
            self.__Google_Service = discovery.build('calendar', 'v3', credentials=self.__Creds, static_discovery=False)

        page_token = None
        while True:
            calendar_list = self.__Google_Service.calendarList().list(pageToken=page_token).execute()
            for calendar_list_entry in calendar_list['items']:
                if calendar_list_entry["summary"] == self.__CALENDER_NAME:
                    # found a calendar we need
                    self.__CALENDER_ID = calendar_list_entry["id"]
                    create_log(f"{self.__CALENDER_NAME} present", "green")
                    return

            # Need to create a calendar
            create_log(f"Calender not present, going to create calender '{self.__CALENDER_NAME}'", "yellow")

            calendar = {
                'summary': self.__CALENDER_NAME,
            }

            created_calendar = self.__Google_Service.calendars().insert(body=calendar).execute()

            create_log(f"Created a calender called {self.__CALENDER_NAME}.", "green")
            self.__CALENDER_ID = created_calendar["id"]

    # used to delete the event from the calendar
    def delete_event(self, event_id):
        if self.__Creds.expired:
            self.__Creds = self.__get_credentials()
            self.__Google_Service = discovery.build('calendar', 'v3', credentials=self.__Creds, static_discovery=False)

        event = self.__Google_Service.events().delete(calendarId=self.__CALENDER_ID, eventId=event_id).execute()
        return event

    def patch_event(self, summary, description, start_time, end_time, event_id):
        if self.__Creds.expired:
            self.__Creds = self.__get_credentials()
            self.__Google_Service = discovery.build('calendar', 'v3', credentials=self.__Creds, static_discovery=False)

        if len(start_time) == 10 and len(end_time) == 10:
            date = datetime.strptime(end_time, "%Y-%m-%d")
            modified_date = date + timedelta(days=1)
            end_time = datetime.strftime(modified_date, "%Y-%m-%d")
            date_type = "date"
        elif len(start_time) == 29 and len(end_time) == 29:
            date_type = "dateTime"
        else:
            return -1

        event = self.__crete_event(summary=summary,
                                   description=description,
                                   start_time=start_time,
                                   end_time=end_time,
                                   date_type=date_type)

        run = True
        while run:
            try:
                event = self.__Google_Service.events().patch(calendarId=self.__CALENDER_ID,
                                                             eventId=event_id,
                                                             body=event).execute()
                run = False
            except errors.HttpError as e:
                if e.status_code == 403:
                    create_log("Too many requests to google calendar, waiting 10 seconds", "yellow")
                    time.sleep(10)
                # if e.status_code == 404:
                #     create_log("Error when trying to patch event, probably deleted, creating new event", "yellow")
                #     event = self.__Google_Service.events().insert(calendarId=self.__CALENDER_ID, body=event).execute()
                #     create_log(f"Created event {event['summary']}", "green")

                else:
                    create_log(f"There was an error when sending the patch request to google calendar, trying again "
                               f"in 10 seconds '{e.status_code}', reason {e.reason}", "red")
                    time.sleep(10)

        return event

    def create_event(self, summary, description, start_time, end_time):
        if self.__Creds.expired:
            self.__Creds = self.__get_credentials()
            self.__Google_Service = discovery.build('calendar', 'v3', credentials=self.__Creds, static_discovery=False)

        if len(start_time) == 10 and len(end_time) == 10:
            date_type = "date"
        elif len(start_time) == 29 and len(end_time) == 29:
            date_type = "dateTime"
        else:
            return -1

        event = self.__crete_event(summary, description, start_time, end_time, date_type)

        event = self.__Google_Service.events().insert(calendarId=self.__CALENDER_ID, body=event).execute()

        create_log(f"Created event {event['summary']}", "green")
        return event.get("id")

    def __crete_event(self, summary, description, start_time, end_time, date_type):
        event = {
            'summary': summary,
            'description': description,
            f'start': {
                date_type: start_time,
            },
            'end': {
                date_type: end_time,
            },
            # 'recurrence': [
            #     'RRULE:FREQ=DAILY;COUNT=2'
            # ],
        }

        if self.__CALENDER_REMINDER:
            event["reminders"] = {
                                     'useDefault': False,
                                     'overrides': [
                                         {'method': 'popup', 'minutes': self.__CALENDER_REMINDER_TIME},
                                     ],
                                 }
        return event
