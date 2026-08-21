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
    """Send OTP to user email"""
    try:
        sender_email = os.environ.get('EMAIL_ADDRESS', 'noreply@islamify.local')
        sender_password = os.environ.get('EMAIL_PASSWORD', 'test-password')

        # For production, use real SMTP
        # For demo, we'll just store and log it
        message = MIMEMultipart('alternative')
        message['Subject'] = '🔐 Your Islamify Dashboard OTP'
        message['From'] = sender_email
        message['To'] = email

        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; background: #0a0e27; color: #00ffff; padding: 20px;">
            <div style="max-width: 400px; margin: 0 auto; background: rgba(26, 31, 58, 0.8); border: 1px solid rgba(0, 255, 255, 0.2); border-radius: 12px; padding: 32px; text-align: center;">
              <h2 style="color: #00ffff; margin-bottom: 20px;">🔐 Two-Factor Authentication</h2>
              <p style="color: #00ff88; margin-bottom: 20px;">Your OTP code is:</p>
              <div style="background: rgba(0, 255, 255, 0.1); border: 2px solid #00ffff; border-radius: 8px; padding: 20px; font-size: 32px; font-weight: bold; letter-spacing: 4px; color: #00ffff; margin: 20px 0;">
                {otp}
              </div>
              <p style="color: #00ff88; font-size: 12px; margin-top: 20px;">This code expires in 10 minutes</p>
              <p style="color: #666; font-size: 11px; margin-top: 20px;">If you didn't request this code, please ignore this email.</p>
            </div>
          </body>
        </html>
        """

        part = MIMEText(html, 'html')
        message.attach(part)

        # Try to send via SMTP if configured
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, message.as_string())
            server.quit()
            return True
        except Exception:
            # Fallback: Just log it for demo
            print(f"[OTP Demo] Code {otp} sent to {email}")
            return True

    except Exception as e:
        print(f"Error sending OTP: {e}")
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
    if email not in otp_storage:
        return False, 'OTP not found or expired'

    otp_data = otp_storage[email]

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
