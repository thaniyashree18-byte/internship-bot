"""Virtual-date lifecycle actions and optional Google Calendar Meet creation."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv

from data import BASE_DIR, log_action

load_dotenv()
MAX_REVIEWS = 3


def create_meet_link(title: str, review_date: date, review_time: str, intern_email: str) -> str:
    credential_file = BASE_DIR / "credentials.json"
    if credential_file.exists():
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_file(
                str(credential_file),
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
            timezone = os.getenv("TIMEZONE", "Asia/Kolkata")
            start_at = datetime.combine(review_date, datetime.strptime(review_time, "%H:%M").time())
            end_at = start_at + timedelta(minutes=30)
            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
            event = service.events().insert(
                calendarId="primary",
                conferenceDataVersion=1,
                body={
                    "summary": f"Internship review: {title}",
                    "start": {"dateTime": start_at.isoformat(), "timeZone": timezone},
                    "end": {"dateTime": end_at.isoformat(), "timeZone": timezone},
                    "attendees": [{"email": intern_email}],
                    "conferenceData": {
                        "createRequest": {
                            "requestId": f"intern-review-{review_date.isoformat()}-{quote(intern_email)}",
                            "conferenceSolutionKey": {"type": "hangoutsMeet"},
                        }
                    },
                },
            ).execute()
            meet_link = event.get("hangoutLink", "")
            if meet_link:
                log_action("calendar", "success", "Google Calendar Meet event created.")
                return meet_link
            log_action("calendar", "fallback", "Google Calendar event did not return a Meet link.")
        except Exception as exc:
            log_action("calendar", "fallback", f"Calendar API unavailable ({type(exc).__name__}).")
    else:
        log_action("calendar", "fallback", "credentials.json not found; generated placeholder Meet URL.")
    return f"https://meet.google.com/lookup/intern-{quote(intern_email.lower())}-{review_date.strftime('%Y%m%d')}"


def already_logged(action: str, intern_id: str, marker: str) -> bool:
    from data import load_logs

    logs = load_logs()
    if logs.empty:
        return False
    match = logs[
        (logs["Action"] == action)
        & (logs["Intern_ID"].astype(str) == str(intern_id))
        & (logs["Details"].astype(str).str.contains(marker, regex=False))
    ]
    return not match.empty


def due_intern_ids(frame: Any, virtual_date: date, action: str) -> list[int]:
    due: list[int] = []
    if frame.empty:
        return due
    date_column = "Join_Date" if action == "orientation" else "Review1_Date"
    for index, row in frame.iterrows():
        if str(row.get("Status", "")).lower() == "completed":
            continue
        value = row.get(date_column, "")
        try:
            target_date = value.date() if isinstance(value, datetime) else date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            continue
        if virtual_date >= target_date:
            due.append(index)
    return due


def next_review_date(current: date) -> date:
    return current + timedelta(days=7)
