"""Quick SMTP connection test — sends a test email to yourself."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASSWORD", "")

print(f"Testing SMTP as: {SMTP_USER}")
print(f"Host: {SMTP_HOST}:{SMTP_PORT}")

msg = MIMEMultipart()
msg["Subject"] = "Job Hunt Bot — SMTP Test"
msg["From"]    = f"Bhuvan Thatthari <{SMTP_USER}>"
msg["To"]      = SMTP_USER   # send to yourself
msg.attach(MIMEText(
    "Your job hunt bot email automation is working correctly!\n\n"
    "bhuvanthatthari@gmail.com is configured and ready to send cold emails, "
    "cover letters, and follow-ups.",
    "plain"
))

try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, SMTP_USER, msg.as_string())
    print("\nSMTP OK — test email sent to", SMTP_USER)
except Exception as e:
    print(f"\nSMTP FAILED: {e}")
