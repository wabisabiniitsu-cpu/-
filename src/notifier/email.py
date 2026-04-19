"""SMTP でレポートを HTML メール送信する。"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


def send_report(
    recipients: list[str],
    subject: str,
    html_body: str,
    markdown_body: str,
    smtp: dict[str, str],
    attachments: list[Path] | None = None,
) -> None:
    if not recipients:
        raise ValueError("report.recipients が空です。")
    sender = smtp.get("SMTP_FROM") or smtp.get("SMTP_USER")
    if not sender:
        raise ValueError("SMTP_FROM または SMTP_USER を設定してください。")
    host = smtp.get("SMTP_HOST")
    if not host:
        raise ValueError("SMTP_HOST が未設定です。")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(markdown_body)
    msg.add_alternative(html_body, subtype="html")

    for path in attachments or []:
        data = path.read_bytes()
        maintype, subtype = (
            ("text", "html") if path.suffix == ".html" else ("application", "octet-stream")
        )
        msg.add_attachment(
            data, maintype=maintype, subtype=subtype, filename=path.name
        )

    port = int(smtp.get("SMTP_PORT") or 587)
    user = smtp.get("SMTP_USER")
    password = smtp.get("SMTP_PASSWORD")
    context = ssl.create_default_context()

    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context) as s:
            if user and password:
                s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.ehlo()
            s.starttls(context=context)
            s.ehlo()
            if user and password:
                s.login(user, password)
            s.send_message(msg)
