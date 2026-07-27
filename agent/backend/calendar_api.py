from __future__ import print_function
import datetime
import os.path
import dateparser
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def normalize_datetime(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)

    return dt.isoformat()

def parse_start_end(text: str, duration_minutes=60):

    start = dateparser.parse(
        text,
        languages=["en", "de"],
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": "Europe/Vienna",
        }
    )

    if not start:
        return None, None

    end = start + timedelta(minutes=duration_minutes)

    return start, end

def get_calendar_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    return service

def check_conflicts(start_time, end_time):
    service = get_calendar_service()

    events = service.events().list(
        calendarId="primary",
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    return events.get("items", [])

def search_events(query):
    service = get_calendar_service()

    results = service.events().list(
        calendarId="primary",
        q=query,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    return results.get("items", [])

def create_event(summary, start_time, end_time):

    service = get_calendar_service()

    event = {
        "summary": summary,
        "start": {
            "dateTime": normalize_datetime(start_time),
            "timeZone": "Europe/Vienna"
        },
        "end": {
            "dateTime": normalize_datetime(end_time),
            "timeZone": "Europe/Vienna"
        },
    }

    created_event = service.events().insert(
        calendarId="primary",
        body=event
    ).execute()

    return created_event

def list_events(n=10):
    service = get_calendar_service()
    now = datetime.now(timezone.utc).isoformat()

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now,
        maxResults=n,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    return events_result.get("items", [])

def delete_event(event_id):
    service = get_calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()

def move_event(event_id, new_start, new_end):

    service = get_calendar_service()

    event = service.events().get(
        calendarId="primary",
        eventId=event_id
    ).execute()

    event["start"] = {
        "dateTime": new_start.isoformat(),
        "timeZone": "Europe/Vienna"
    }

    event["end"] = {
        "dateTime": new_end.isoformat(),
        "timeZone": "Europe/Vienna"
    }

    updated = service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event
    ).execute()

    return updated
