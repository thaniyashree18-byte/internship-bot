"""HTML email delivery. Dry-run mode stores messages locally without sending."""

from __future__ import annotations

import os
import re
import smtplib
import ssl
import uuid
from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path

from dotenv import load_dotenv

from data import BASE_DIR, log_action

load_dotenv()
OUTBOX_DIR = BASE_DIR / "outbox"


def _html_document(body: str) -> str:
    safe_body = escape(body)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Internship Program</title></head>"
        "<body style=\"font-family:Arial,sans-serif;line-height:1.6;color:#1f2937;"
        "max-width:720px;margin:32px auto;padding:24px\">"
        f"<main>{safe_body.replace(chr(10), '<br>')}</main>"
        "<p style=\"margin-top:32px;color:#64748b\">Internship Program Team</p>"
        "</body></html>"
    )


def _save_outbox(recipient: str, subject: str, html_body: str) -> Path:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    recipient_label = re.sub(r"[^a-zA-Z0-9_.-]", "_", recipient)[:48] or "recipient"
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{recipient_label}_{uuid.uuid4().hex[:8]}.html"
    path = OUTBOX_DIR / filename
    document = (
        "<!doctype html><html><head><meta charset=\"utf-8\"></head><body>"
        f"<p><strong>To:</strong> {escape(recipient)}<br>"
        f"<strong>Subject:</strong> {escape(subject)}</p><hr>{html_body}</body></html>"
    )
    path.write_text(document, encoding="utf-8")
    return path


def send_email(
    recipient: str,
    subject: str,
    body: str,
    *,
    dry_run: bool = True,
    allow_live_delivery: bool = False,
) -> str:
    if not recipient or "@" not in recipient:
        raise ValueError("A valid recipient email address is required.")
    html_body = _html_document(body)
    if dry_run:
        path = _save_outbox(recipient, subject, html_body)
        log_action("email", "saved", f"Dry-run email saved to {path.name}.")
        return f"Saved to outbox/{path.name}"

    test_email = os.getenv("TEST_EMAIL", "").strip()
    target = recipient if allow_live_delivery else test_email
    if not target or "@" not in target:
        raise ValueError("Set TEST_EMAIL in .env to send a test copy, or explicitly enable live delivery.")
    sender = os.getenv("GMAIL_USER", "").strip()
    password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    if not sender or not password:
        raise RuntimeError("Configure GMAIL_USER and GMAIL_APP_PASSWORD in .env before sending mail.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = target
    message.set_content(body)
    message.add_alternative(html_body, subtype="html")
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        log_action("email", "error", f"SMTP delivery failed ({type(exc).__name__}).")
        raise RuntimeError(f"Email delivery failed: {exc}") from exc
    mode = "live" if allow_live_delivery else "test"
    log_action("email", "sent", f"{mode} email sent to {target}.")
    return f"Sent to {target}"
