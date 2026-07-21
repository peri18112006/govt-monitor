import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, MAIL_TO

logger = logging.getLogger("govt_monitor.mailer")


def send_new_items_email(site_name: str, site_url: str, items_with_blurbs: list) -> bool:
    """
    items_with_blurbs: list of dicts like {"title": ..., "url": ..., "blurb": ...}
    Sends ONE email listing all newly detected items for this site, each with
    its own direct link and a short AI-written explanation.
    Returns True on success, False on failure (never raises).
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not MAIL_TO:
        logger.warning("Email not configured (missing GMAIL_ADDRESS / GMAIL_APP_PASSWORD / MAIL_TO). Skipping send.")
        return False

    count = len(items_with_blurbs)
    subject_bit = items_with_blurbs[0]["title"][:60] if count == 1 else f"{count} new updates"
    subject = f"🔔 {site_name} — {subject_bit}"

    lines = [
        f"New update(s) detected on: {site_name}",
        f"Page monitored: {site_url}",
        "",
        "=" * 60,
        "",
    ]

    for idx, item in enumerate(items_with_blurbs, start=1):
        lines.append(f"{idx}. {item['title']}")
        lines.append(f"   What this means: {item['blurb']}")
        lines.append(f"   Link: {item['url']}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("This is an automated alert from your Govt Site Monitor.")

    body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = MAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, MAIL_TO, msg.as_string())
        logger.info(f"Email sent for {count} new item(s) on {site_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email for {site_name}: {e}")
        return False
