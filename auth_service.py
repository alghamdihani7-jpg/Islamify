import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# Hardcoded credentials for demo
VALID_CREDENTIALS = {
    'hani911h': 'QWEasdzxc123!'
}

ADMIN_EMAIL = 'alghamdihani7@gmail.com'

# In-memory OTP storage (in production, use Redis or database)
otp_storage = {}

def generate_otp():
    """Generate a 6-digit OTP"""
    return str(secrets.randbelow(1000000)).zfill(6)

def send_otp_email(email, otp):
    """Send OTP to user email (non-blocking for demo)"""
    try:
        # For demo/test: just log the OTP
        print(f"\n{'='*60}")
        print(f"📧 OTP EMAIL NOTIFICATION")
        print(f"{'='*60}")
        print(f"To: {email}")
        print(f"Subject: 🔐 Your Islamify Dashboard OTP")
        print(f"\nYour One-Time Password (OTP):")
        print(f"\n  ╔══════════════════════════════╗")
        print(f"  ║     OTP CODE: {otp}            ║")
        print(f"  ╚══════════════════════════════╝")
        print(f"\nExpires in: 10 minutes")
        print(f"{'='*60}\n")

        # For production, send real email asynchronously
        # import threading
        # thread = threading.Thread(target=_send_smtp, args=(email, otp, message))
        # thread.daemon = True
        # thread.start()

        return True

    except Exception as e:
        print(f"Error in OTP notification: {e}")
        return False

def store_otp(email, otp):
    """Store OTP with expiration"""
    otp_storage[email] = {
        'code': otp,
        'created_at': datetime.now(),
        'expires_at': datetime.now() + timedelta(minutes=10),
        'attempts': 0
    }

def verify_otp(email, otp):
    """Verify OTP code"""
    print(f"[DEBUG] Verifying OTP: email={email}, provided_otp={otp}, stored_keys={list(otp_storage.keys())}")

    if email not in otp_storage:
        print(f"[DEBUG] Email not in storage")
        return False, 'OTP not found or expired'

    otp_data = otp_storage[email]
    print(f"[DEBUG] Stored OTP: {otp_data['code']}, Provided: {otp}")

    # Check expiration
    if datetime.now() > otp_data['expires_at']:
        del otp_storage[email]
        return False, 'OTP expired'

    # Check attempts
    if otp_data['attempts'] >= 3:
        del otp_storage[email]
        return False, 'Too many failed attempts'

    # Verify code
    if otp_data['code'] == otp:
        del otp_storage[email]
        return True, 'OTP verified'

    otp_data['attempts'] += 1
    return False, 'Invalid OTP'

def verify_credentials(username, password):
    """Verify username and password"""
    return VALID_CREDENTIALS.get(username) == password

def get_masked_email(email):
    """Mask email for display"""
    parts = email.split('@')
    if len(parts[0]) > 2:
        masked = parts[0][0] + '*' * (len(parts[0]) - 2) + parts[0][-1]
    else:
        masked = parts[0]
    return f"{masked}@{parts[1]}"
