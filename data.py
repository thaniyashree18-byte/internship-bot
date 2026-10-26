"""Workbook, task bank, sample-data, and action-log helpers."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from faker import Faker

BASE_DIR = Path(__file__).resolve().parent
WORKBOOK_PATH = BASE_DIR / "interns.xlsx"
LOG_PATH = BASE_DIR / "logs.csv"

COLUMNS = [
    "ID", "Name", "Email", "GitHub_Username", "Track", "Task_Title",
    "Task_Description", "Modules", "Features", "Tech_Stack", "Join_Date",
    "Review1_Date", "Review1_Time", "Meet_Link", "Status", "Review_Count",
    "Last_Feedback", "Next_Task", "End_Date",
]

TASK_BANK: dict[str, list[dict[str, str]]] = {
    "Web": [
        {
            "title": "Responsive Portfolio Website",
            "description": "Build a polished, responsive portfolio for a fictional professional.",
            "modules": "Landing page; projects; contact form; responsive navigation",
            "features": "Mobile layout; accessible navigation; form validation; project filtering",
            "stack": "HTML, CSS, JavaScript",
        },
        {
            "title": "Community Events Portal",
            "description": "Create a small events portal where visitors can browse and save events.",
            "modules": "Event listing; event details; saved events; search",
            "features": "Category filters; responsive cards; empty states; local persistence",
            "stack": "HTML, CSS, JavaScript",
        },
    ],
    "Python": [
        {
            "title": "Personal Expense Tracker",
            "description": "Create a command-line or simple web tool for recording and summarizing expenses.",
            "modules": "Expense entry; categories; monthly summary; data storage",
            "features": "Input validation; date filtering; CSV export; clear error messages",
            "stack": "Python, pandas, SQLite",
        },
        {
            "title": "File Organizer Utility",
            "description": "Build a safe utility that organizes a chosen folder by file type.",
            "modules": "Folder scan; file classification; preview; execution report",
            "features": "Dry-run preview; collision handling; logs; configurable categories",
            "stack": "Python, pathlib, argparse",
        },
    ],
    "Data": [
        {
            "title": "Retail Sales Insights",
            "description": "Analyze a sample retail dataset and communicate useful business trends.",
            "modules": "Data cleaning; exploratory analysis; KPI calculations; visualization",
            "features": "Missing-value report; monthly trends; category comparison; insights summary",
            "stack": "Python, pandas, matplotlib, Jupyter",
        },
        {
            "title": "Public Transport Delay Analysis",
            "description": "Explore sample transport records to identify patterns in service delays.",
            "modules": "Data preparation; delay metrics; route comparison; visual report",
            "features": "Time-of-day analysis; outlier notes; clear charts; reproducible notebook",
            "stack": "Python, pandas, seaborn, Jupyter",
        },
    ],
    "ML": [
        {
            "title": "Customer Churn Predictor",
            "description": "Train and evaluate a baseline model that estimates customer churn risk.",
            "modules": "Data preparation; baseline model; evaluation; inference example",
            "features": "Train/test split; metric comparison; feature importance; model limitations",
            "stack": "Python, pandas, scikit-learn",
        },
        {
            "title": "Product Review Sentiment Classifier",
            "description": "Build a text-classification baseline for positive and negative product reviews.",
            "modules": "Text cleaning; vectorization; model training; evaluation",
            "features": "Reproducible split; precision/recall; example predictions; error analysis",
            "stack": "Python, pandas, scikit-learn, NLTK",
        },
    ],
    "Mobile": [
        {
            "title": "Habit Tracker App",
            "description": "Design a mobile-first habit tracker with clear daily progress.",
            "modules": "Habit setup; daily check-in; progress history; settings",
            "features": "Accessible controls; streak display; local storage; empty states",
            "stack": "React Native, TypeScript",
        },
        {
            "title": "Campus Navigator",
            "description": "Create a simple mobile guide to a fictional campus and its facilities.",
            "modules": "Location list; location details; saved places; search",
            "features": "Category filter; accessible layouts; saved places; map placeholder",
            "stack": "React Native, TypeScript",
        },
    ],
}


def empty_interns() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def load_interns(path: Path = WORKBOOK_PATH) -> pd.DataFrame:
    if not path.exists():
        return empty_interns()
    try:
        frame = pd.read_excel(path, engine="openpyxl")
    except (OSError, ValueError, ImportError) as exc:
        raise RuntimeError(f"Could not read {path.name}: {exc}") from exc
    for column in COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    frame = frame[COLUMNS]
    frame["Review_Count"] = pd.to_numeric(frame["Review_Count"], errors="coerce").fillna(0).astype(int)
    return frame


def save_interns(frame: pd.DataFrame, path: Path = WORKBOOK_PATH) -> None:
    missing = [column for column in COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Workbook is missing required columns: {', '.join(missing)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.stem}.tmp{path.suffix}")
    try:
        frame[COLUMNS].to_excel(temp_path, index=False, engine="openpyxl")
        os.replace(temp_path, path)
    except (OSError, ValueError, ImportError) as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Could not save {path.name}: {exc}") from exc


def log_action(action: str, status: str, details: str = "", intern_id: str = "") -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([{
        "Timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "Action": action,
        "Intern_ID": intern_id,
        "Status": status,
        "Details": details[:2000],
    }])
    row.to_csv(LOG_PATH, mode="a", header=not LOG_PATH.exists(), index=False, encoding="utf-8")


def load_logs() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame(columns=["Timestamp", "Action", "Intern_ID", "Status", "Details"])
    try:
        return pd.read_csv(LOG_PATH).fillna("")
    except (OSError, pd.errors.ParserError, UnicodeError) as exc:
        raise RuntimeError(f"Could not read logs.csv: {exc}") from exc


def assign_task(row: dict[str, Any], join_date: date) -> dict[str, Any]:
    track = str(row.get("Track", "")).strip()
    choices = TASK_BANK.get(track)
    if not choices:
        raise ValueError(f"Choose one of the supported tracks: {', '.join(TASK_BANK)}")
    task = choices[sum(ord(char) for char in str(row.get("ID", ""))) % len(choices)]
    assigned = dict(row)
    assigned.update({
        "Task_Title": task["title"],
        "Task_Description": task["description"],
        "Modules": task["modules"],
        "Features": task["features"],
        "Tech_Stack": task["stack"],
        "Join_Date": join_date.isoformat(),
        "Review1_Date": (join_date + timedelta(days=7)).isoformat(),
        "Review1_Time": "10:00",
        "Meet_Link": "",
        "Status": "Assigned",
        "Review_Count": 0,
        "Last_Feedback": "",
        "Next_Task": task["title"],
        "End_Date": (join_date + timedelta(days=21)).isoformat(),
    })
    return assigned


def generate_sample_interns(count: int = 100, start_date: date | None = None) -> pd.DataFrame:
    if count < 1 or count > 1000:
        raise ValueError("Sample count must be between 1 and 1000.")
    fake = Faker()
    first_id = 1
    if WORKBOOK_PATH.exists():
        current = load_interns()
        numeric_ids = pd.to_numeric(current["ID"], errors="coerce").dropna()
        if not numeric_ids.empty:
            first_id = int(numeric_ids.max()) + 1
    start = start_date or date.today()
    rows: list[dict[str, Any]] = []
    tracks = list(TASK_BANK)
    for index in range(count):
        full_name = fake.name()
        name_part = "".join(part.lower() for part in full_name.split() if part.isalpha())
        row = {
            "ID": f"INT-{first_id + index:04d}",
            "Name": full_name,
            "Email": f"{name_part}{first_id + index}@example.com",
            "GitHub_Username": fake.unique.user_name()[:39],
            "Track": tracks[index % len(tracks)],
        }
        rows.append(assign_task(row, start))
    return pd.DataFrame(rows, columns=COLUMNS)
