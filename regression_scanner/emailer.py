"""Email alerts using an SMTP SSL connection (e.g., Gmail App Password)."""
import os
import smtplib
from email.message import EmailMessage


def send_email(subject: str, body: str, *, html_body: str | None = None) -> None:
    keys = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "ALERT_TO"]
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        raise RuntimeError("Missing email settings: " + ", ".join(missing))
    message = EmailMessage()
    message["From"] = os.environ["SMTP_USER"]
    message["To"] = os.environ["ALERT_TO"]
    message["Subject"] = subject
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"]), timeout=30) as smtp:
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)
