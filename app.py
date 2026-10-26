"""Streamlit front end for the AI Internship Automation System."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ai import create_orientation, create_review, create_welcome
from data import (
    COLUMNS,
    TASK_BANK,
    WORKBOOK_PATH,
    assign_task,
    generate_sample_interns,
    load_interns,
    load_logs,
    log_action,
    save_interns,
)
from github_review import fetch_repository_report
from mailer import send_email
from scheduler import MAX_REVIEWS, already_logged, create_meet_link, due_intern_ids, next_review_date

load_dotenv()
st.set_page_config(page_title="Internship Automation", page_icon="🎓", layout="wide")


def get_frame() -> pd.DataFrame:
    if "interns_frame" not in st.session_state:
        st.session_state.interns_frame = load_interns()
    return st.session_state.interns_frame


def persist(frame: pd.DataFrame) -> None:
    save_interns(frame)
    st.session_state.interns_frame = frame


def row_dict(row: pd.Series) -> dict[str, Any]:
    return row.to_dict()


def mail_options() -> tuple[bool, bool]:
    dry_run = st.sidebar.toggle("Dry run (save to outbox)", value=True)
    live_delivery = False
    if not dry_run:
        live_delivery = st.sidebar.checkbox(
            "Allow delivery to intern addresses",
            value=False,
            help="When unchecked, messages are sent only to TEST_EMAIL.",
        )
        if not live_delivery and not os.getenv("TEST_EMAIL", "").strip():
            st.sidebar.warning("Set TEST_EMAIL in .env before sending test copies.")
    return dry_run, live_delivery


def deliver(recipient: str, subject: str, body: str, dry_run: bool, live_delivery: bool) -> str:
    return send_email(
        recipient, subject, body, dry_run=dry_run, allow_live_delivery=live_delivery
    )


def send_welcome_for_row(
    frame: pd.DataFrame, index: int, dry_run: bool, live_delivery: bool
) -> str:
    row = row_dict(frame.loc[index])
    body = create_welcome(row)
    result = deliver(
        str(row.get("Email", "")),
        f"Welcome to the {row.get('Track', '')} Internship Program",
        body,
        dry_run,
        live_delivery,
    )
    log_action("welcome_email", "success", result, str(row.get("ID", "")))
    return result


def send_orientation_for_row(
    frame: pd.DataFrame, index: int, dry_run: bool, live_delivery: bool
) -> str:
    row = row_dict(frame.loc[index])
    body = create_orientation(row)
    result = deliver(
        str(row.get("Email", "")),
        f"Project orientation: {row.get('Task_Title', 'Internship project')}",
        body,
        dry_run,
        live_delivery,
    )
    if str(frame.at[index, "Status"]).lower() != "completed":
        frame.at[index, "Status"] = "Active"
        persist(frame)
    log_action(
        "orientation",
        "success",
        f"orientation_sent {result}",
        str(row.get("ID", "")),
    )
    return result


def send_review_for_row(
    frame: pd.DataFrame, index: int, dry_run: bool, live_delivery: bool
) -> str:
    row = row_dict(frame.loc[index])
    review_number = int(row.get("Review_Count", 0) or 0) + 1
    report = "No GitHub username provided; review uses the project requirements and fallback guidance."
    if str(row.get("GitHub_Username", "")).strip():
        try:
            report = fetch_repository_report(
                str(row["GitHub_Username"]), str(row.get("Task_Title", ""))
            )
        except (RuntimeError, ValueError) as exc:
            report = (
                f"GitHub review could not retrieve evidence: {exc}\n"
                "Do not assume implementation details; provide provisional guidance."
            )
    feedback = create_review(row, report, review_number)
    is_final = review_number >= MAX_REVIEWS
    subject = (
        "Internship completion and certificate"
        if is_final
        else f"Internship review {review_number} feedback"
    )
    if is_final:
        feedback += (
            "\n\nCongratulations on completing the internship! Your certificate message is: "
            f"This certifies that {row.get('Name', 'the intern')} has completed the "
            f"{row.get('Track', '')} internship project."
        )
    result = deliver(str(row.get("Email", "")), subject, feedback, dry_run, live_delivery)
    frame.at[index, "Review_Count"] = review_number
    frame.at[index, "Last_Feedback"] = feedback
    if is_final:
        frame.at[index, "Status"] = "Completed"
        frame.at[index, "Next_Task"] = ""
        action = "completion_email"
    else:
        next_date = next_review_date(date.fromisoformat(str(row.get("Review1_Date"))[:10]))
        frame.at[index, "Review1_Date"] = next_date.isoformat()
        frame.at[index, "Next_Task"] = (
            f"Review {review_number + 1}: {row.get('Task_Title', '')}"
        )
        action = f"review_{review_number}"
    log_action(action, "success", f"review_sent {result}", str(row.get("ID", "")))
    persist(frame)
    return result


def create_review_invite(
    frame: pd.DataFrame, index: int, dry_run: bool, live_delivery: bool
) -> str:
    row = row_dict(frame.loc[index])
    try:
        review_date = date.fromisoformat(str(row.get("Review1_Date"))[:10])
    except ValueError as exc:
        raise ValueError("Assign a valid review date before creating an invite.") from exc
    raw_time = row.get("Review1_Time", "")
    if hasattr(raw_time, "strftime"):
        review_time = raw_time.strftime("%H:%M")
    else:
        time_text = str(raw_time).strip()
        try:
            review_time = datetime.strptime(time_text[:8], "%H:%M:%S").strftime("%H:%M")
        except ValueError:
            try:
                review_time = datetime.strptime(time_text[:5], "%H:%M").strftime("%H:%M")
            except ValueError as exc:
                raise ValueError("Enter a valid review time such as 10:00.") from exc
    meet_link = create_meet_link(
        str(row.get("Task_Title", "Internship review")),
        review_date,
        review_time,
        str(row.get("Email", "")),
    )
    frame.at[index, "Meet_Link"] = meet_link
    body = (
        f"Hi {row.get('Name', 'there')},\n\n"
        f"Your first internship review is scheduled for {review_date.isoformat()} at "
        f"{review_time} ({os.getenv('TIMEZONE', 'Asia/Kolkata')}).\n"
        f"Join the meeting: {meet_link}\n\n"
        "Please have your public GitHub repository and a short progress update ready."
    )
    result = deliver(
        str(row.get("Email", "")), "Your first internship review", body,
        dry_run, live_delivery,
    )
    log_action(
        "review_invite",
        "success",
        f"review_invite_sent {result}; date={review_date.isoformat()}",
        str(row.get("ID", "")),
    )
    persist(frame)
    return result


def process_due_items(
    frame: pd.DataFrame, virtual_date: date, dry_run: bool, live_delivery: bool
) -> tuple[int, list[str]]:
    due_orientation = due_intern_ids(frame, virtual_date, "orientation")
    due_reviews = due_intern_ids(frame, virtual_date, "review")
    processed = 0
    errors: list[str] = []
    for index in due_orientation:
        intern_id = str(frame.at[index, "ID"])
        if not already_logged("orientation", intern_id, "orientation_sent"):
            try:
                send_orientation_for_row(frame, index, dry_run, live_delivery)
                processed += 1
            except (RuntimeError, ValueError, OSError) as exc:
                log_action("orientation", "error", str(exc), intern_id)
                errors.append(f"Orientation for {intern_id}: {exc}")
    for index in due_reviews:
        intern_id = str(frame.at[index, "ID"])
        review_action = f"review_{int(frame.at[index, 'Review_Count'] or 0) + 1}"
        if not already_logged(review_action, intern_id, "review_sent"):
            try:
                send_review_for_row(frame, index, dry_run, live_delivery)
                processed += 1
            except (RuntimeError, ValueError, OSError) as exc:
                log_action(review_action, "error", str(exc), intern_id)
                errors.append(f"Review for {intern_id}: {exc}")
    return processed, errors


st.title("🎓 AI Internship Automation System")
frame = get_frame()
today = st.session_state.setdefault("virtual_date", date.today())
if isinstance(today, str):
    today = date.fromisoformat(today)

with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Page",
        ["Dashboard", "Interns", "Assign Tasks", "Send Mails", "Reviews", "Logs"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption(f"Virtual date: **{today.isoformat()}**")
    dry_run, live_delivery = mail_options()
    if st.button("Simulate next day", width="stretch"):
        next_date = today + timedelta(days=1)
        st.session_state.virtual_date = next_date
        processed, errors = process_due_items(frame, next_date, dry_run, live_delivery)
        st.session_state.simulation_result = (processed, errors, next_date.isoformat())
        st.rerun()
    if st.button("Simulate next week", width="stretch"):
        next_date = today + timedelta(days=7)
        st.session_state.virtual_date = next_date
        processed, errors = process_due_items(frame, next_date, dry_run, live_delivery)
        st.session_state.simulation_result = (processed, errors, next_date.isoformat())
        st.rerun()
    simulation_result = st.session_state.pop("simulation_result", None)
    if simulation_result:
        processed, errors, simulated_date = simulation_result
        st.sidebar.success(f"Simulated {simulated_date}; processed {processed} due item(s).")
        for error in errors:
            st.sidebar.error(error)


if page == "Dashboard":
    total = len(frame)
    completed = int((frame["Status"].astype(str).str.lower() == "completed").sum()) if total else 0
    active = int((frame["Status"].astype(str).str.lower() == "active").sum()) if total else 0
    assigned = int((frame["Status"].astype(str).str.lower() == "assigned").sum()) if total else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total interns", total)
    c2.metric("Assigned", assigned)
    c3.metric("Active", active)
    c4.metric("Completed", completed)
    left, right = st.columns([1, 2])
    with left:
        st.subheader("Intern status")
        if total:
            status_counts = frame["Status"].replace("", "Unassigned").fillna("Unassigned").value_counts()
            st.bar_chart(status_counts, alt="Interns grouped by current status")
        else:
            st.info("Add interns or generate sample data to get started.")
    with right:
        st.subheader("Intern directory")
        track_filter = st.multiselect("Filter by track", sorted(TASK_BANK), default=[])
        status_filter = st.multiselect(
            "Filter by status", sorted(frame["Status"].dropna().astype(str).unique()), default=[]
        )
        visible = frame.copy()
        if track_filter:
            visible = visible[visible["Track"].isin(track_filter)]
        if status_filter:
            visible = visible[visible["Status"].astype(str).isin(status_filter)]
        st.dataframe(visible, hide_index=True, alt="Intern directory with active filters")
    st.caption(f"Workbook: {WORKBOOK_PATH.name} · Demo date advances in this session.")

elif page == "Interns":
    st.subheader("Intern records")
    upload = st.file_uploader("Import an Excel workbook", type=["xlsx"])
    if upload is not None and st.button("Import uploaded workbook"):
        try:
            imported = pd.read_excel(upload, engine="openpyxl")
            for column in COLUMNS:
                if column not in imported.columns:
                    imported[column] = ""
            imported = imported[COLUMNS]
            persist(imported)
            log_action("excel_import", "success", f"Imported {len(imported)} interns.")
            st.success(f"Imported {len(imported)} intern records.")
            st.rerun()
        except (ValueError, OSError, ImportError) as exc:
            st.error(f"Import failed: {exc}")
    if st.button("Generate 100 sample interns", type="primary"):
        try:
            samples = generate_sample_interns(100, today)
            combined = pd.concat([frame, samples], ignore_index=True)
            persist(combined)
            log_action("sample_generation", "success", f"Generated {len(samples)} sample interns.")
            st.success("Added 100 sample interns. Reserved example.com addresses are non-deliverable.")
            st.rerun()
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(f"Could not generate sample interns: {exc}")

    with st.expander("Add an intern manually"):
        with st.form("add_intern"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            github = st.text_input("GitHub username")
            track = st.selectbox("Track", list(TASK_BANK))
            join_date = st.date_input("Join date", value=today)
            submitted = st.form_submit_button("Add intern")
        if submitted:
            if not name.strip() or "@" not in email:
                st.error("Enter a name and a valid email address.")
            else:
                new_id = f"INT-{(len(frame) + 1):04d}"
                new_row = assign_task(
                    {"ID": new_id, "Name": name.strip(), "Email": email.strip(),
                     "GitHub_Username": github.strip(), "Track": track},
                    join_date,
                )
                persist(pd.concat([frame, pd.DataFrame([new_row])], ignore_index=True))
                log_action("intern_added", "success", f"Added {name}.", new_id)
                st.success(f"Added {name} with a {track} task.")
                st.rerun()
    st.caption("Edit cells below, then save changes to interns.xlsx.")
    edited = st.data_editor(
        frame,
        num_rows="dynamic",
        key="intern_editor",
        alt="Editable internship records",
    )
    if st.button("Save intern table"):
        try:
            persist(edited)
            log_action("intern_table_saved", "success", f"Saved {len(edited)} records.")
            st.success("Intern records saved.")
        except (RuntimeError, ValueError) as exc:
            st.error(f"Save failed: {exc}")

elif page == "Assign Tasks":
    st.subheader("Track-based task assignment")
    st.write("Task bank tracks: " + ", ".join(TASK_BANK))
    unassigned = frame[
        frame["Task_Title"].astype(str).str.strip().eq("")
        | frame["Join_Date"].astype(str).str.strip().eq("")
    ] if not frame.empty else frame
    st.info(f"{len(unassigned)} intern(s) need an assignment.")
    assignment_date = st.date_input("Default joining date", value=today, key="assignment_date")
    if st.button("Assign tasks to unassigned interns", type="primary", disabled=unassigned.empty):
        try:
            updated = frame.copy()
            for index in unassigned.index:
                updated.loc[index] = assign_task(row_dict(updated.loc[index]), assignment_date)
            persist(updated)
            log_action("task_assignment", "success", f"Assigned tasks to {len(unassigned)} interns.")
            st.success(f"Assigned tasks to {len(unassigned)} interns.")
            st.rerun()
        except (RuntimeError, ValueError) as exc:
            st.error(f"Assignment failed: {exc}")
    if not frame.empty:
        st.dataframe(
            frame[["ID", "Name", "Track", "Task_Title", "Join_Date", "Review1_Date"]],
            hide_index=True,
            alt="Intern task assignments and dates",
        )

elif page == "Send Mails":
    st.subheader("Welcome and orientation emails")
    if frame.empty:
        st.info("Add interns before sending mail.")
    else:
        selected = st.multiselect(
            "Select interns",
            frame.index.tolist(),
            format_func=lambda index: f"{frame.at[index, 'ID']} — {frame.at[index, 'Name']}",
            key="mail_selection",
        )
        mail_kind = st.radio("Email type", ["Welcome", "Orientation"], horizontal=True)
        if st.button(f"Send {mail_kind.lower()} email(s)", disabled=not selected):
            progress = st.progress(0)
            status = st.empty()
            successes = 0
            for position, index in enumerate(selected, start=1):
                try:
                    if mail_kind == "Welcome":
                        result = send_welcome_for_row(frame, index, dry_run, live_delivery)
                    else:
                        result = send_orientation_for_row(frame, index, dry_run, live_delivery)
                    status.write(f"{frame.at[index, 'Name']}: {result}")
                    successes += 1
                except (RuntimeError, ValueError, OSError) as exc:
                    log_action(f"{mail_kind.lower()}_email", "error", str(exc), str(frame.at[index, "ID"]))
                    status.error(f"{frame.at[index, 'Name']}: {exc}")
                progress.progress(position / len(selected))
            st.success(f"Processed {successes} of {len(selected)} email(s).")

        st.divider()
        st.subheader("Process what is due")
        if st.button("Run due orientations and reviews", type="secondary"):
            progress = st.progress(0)
            processed, errors = process_due_items(frame, today, dry_run, live_delivery)
            progress.progress(1)
            for error in errors:
                st.error(error)
            st.success(f"Processed due items for {today.isoformat()}.")
            st.rerun()

elif page == "Reviews":
    st.subheader("Review management")
    if frame.empty:
        st.info("Add interns to schedule or conduct reviews.")
    else:
        eligible = frame[frame["Task_Title"].astype(str).str.strip().ne("")]
        selected = st.selectbox(
            "Intern",
            eligible.index.tolist(),
            format_func=lambda index: f"{frame.at[index, 'ID']} — {frame.at[index, 'Name']}",
        ) if not eligible.empty else None
        if selected is not None:
            current = frame.loc[selected]
            st.write(
                f"**Project:** {current['Task_Title']} · **Review count:** "
                f"{current['Review_Count']} / {MAX_REVIEWS} · **Next review:** {current['Review1_Date']}"
            )
            if st.button("Schedule / send first review invite", disabled=not str(current["Email"]).strip()):
                try:
                    result = create_review_invite(frame, selected, dry_run, live_delivery)
                    st.success(result)
                except (RuntimeError, ValueError, OSError) as exc:
                    st.error(f"Could not schedule review: {exc}")
            if st.button("Run review now", disabled=str(current["Status"]).lower() == "completed"):
                try:
                    result = send_review_for_row(frame, selected, dry_run, live_delivery)
                    st.success(result)
                    st.rerun()
                except (RuntimeError, ValueError, OSError) as exc:
                    st.error(f"Review failed: {exc}")
            if current["Last_Feedback"]:
                st.markdown("**Latest feedback**")
                st.text(str(current["Last_Feedback"]))
            st.caption("Reviews run weekly. Review three marks the intern Completed.")
        st.dataframe(
            eligible[["ID", "Name", "Status", "Review_Count", "Review1_Date", "Meet_Link"]],
            hide_index=True,
            alt="Review schedule and status by intern",
        )

elif page == "Logs":
    st.subheader("Action logs")
    try:
        logs = load_logs()
        if logs.empty:
            st.info("No actions logged yet.")
        else:
            actions = st.multiselect("Filter actions", sorted(logs["Action"].astype(str).unique()))
            statuses = st.multiselect("Filter outcomes", sorted(logs["Status"].astype(str).unique()))
            visible = logs
            if actions:
                visible = visible[visible["Action"].isin(actions)]
            if statuses:
                visible = visible[visible["Status"].isin(statuses)]
            st.dataframe(
                visible.sort_values("Timestamp", ascending=False),
                hide_index=True,
                alt="Application action log",
            )
    except RuntimeError as exc:
        st.error(str(exc))
