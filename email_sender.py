import smtplib
import ssl
from email.message import EmailMessage
from dotenv import load_dotenv
import os

load_dotenv()  # loads .env into environment

# ================= CONFIG =================
EMAIL_SENDER = "tender.alerts007@gmail.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")   # Gmail App Password
EMAIL_RECEIVER = "viratkalshan@gmail.com"
temp="vansh.kalshan@in.gt.com"
# ========================================

def send_job_email(title, link, ref_no=None, country=None,
                   process=None, deadline=None):
    msg = EmailMessage()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = "New Tender Match"

    body = [
        "New tender notice matched your keywords:\n",
        f"Title: {title}",
    ]

    if deadline:
        body.append(f"Deadline: {deadline}")

    body.append(f"\nLink:\n{link}")

    msg.set_content("\n".join(body))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
    
