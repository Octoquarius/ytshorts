"""Aşama 4 (Adım 12) — Gmail bildirimi (App Password ile SMTP).

Yeni video yayına alındığında YouTube linkini içeren bir e-posta gönderir.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

import config

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def send(subject: str, body: str, to: str | None = None) -> None:
    """Gmail App Password ile bilgilendirme e-postası gönderir."""
    sender = config.GMAIL_ADDRESS
    password = config.GMAIL_APP_PASSWORD
    recipient = to or config.NOTIFY_TO
    if not (sender and password and recipient):
        print("[notify] Gmail ayarları eksik — bildirim atlanıyor.")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(sender, password)
        server.send_message(msg)
    print(f"[notify] E-posta gönderildi -> {recipient}")


def notify_published(account_name: str, title: str, youtube_url: str) -> None:
    """'Yeni video yayında' bildirimi."""
    send(
        subject=f"[{account_name}] Yeni Short yayında",
        body=(
            f"Kanal: {account_name}\n"
            f"Başlık: {title}\n"
            f"Link: {youtube_url}\n"
        ),
    )
