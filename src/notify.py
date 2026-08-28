"""Stage 4 (Step 12) — Gmail notification (SMTP with App Password).

Sends an email containing the YouTube link when a new video is published.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

import config

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def send(subject: str, body: str, to: str | None = None) -> None:
    """Sends a notification email using a Gmail App Password."""
    sender = config.GMAIL_ADDRESS
    password = config.GMAIL_APP_PASSWORD
    recipient = to or config.NOTIFY_TO
    if not (sender and password and recipient):
        print("[notify] Gmail settings missing — skipping notification.")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(sender, password)
        server.send_message(msg)
    print(f"[notify] Email sent -> {recipient}")


def notify_published(account_name: str, title: str, youtube_url: str) -> None:
    """'New video published' notification."""
    send(
        subject=f"[{account_name}] New Short published",
        body=(
            f"Channel: {account_name}\n"
            f"Title: {title}\n"
            f"Link: {youtube_url}\n"
        ),
    )
