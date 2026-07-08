import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sender_email = "akshat.k@gsl.in"
receiver_email = "ping@tools.mxtoolbox.com"
app_password = os.environ.get("WORK_EMAIL_PASS")

message = MIMEMultipart()
message["From"] = sender_email
message["To"] = receiver_email
message["Subject"] = "Automated Work Test via SSL"
message.attach(MIMEText("Testing secure SSL port 465 from Codespaces.", "plain"))

try:
    print("Connecting to Google SMTP via Secure SSL (Port 465)...")
    # SMTP_SSL opens an encrypted connection immediately
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    
    print("Authenticating...")
    server.login(sender_email, app_password)
    
    print("Sending mail...")
    server.sendmail(sender_email, receiver_email, message.as_string())
    print("✅ Success! Your email has been delivered.")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
finally:
    try: server.quit()
    except: pass
