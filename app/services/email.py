"""Email service — sends transactional emails via Gmail API.

Uses the Firebase service account with domain-wide delegation to send
emails as noreply@instnews.net. No extra credentials needed beyond
FIREBASE_CREDENTIALS / FIREBASE_CREDENTIALS_JSON already configured.

Falls back to logging if credentials are not available (local dev).
"""

import base64
import json
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("signal.email")

SENDER_EMAIL = os.environ.get("GMAIL_SENDER", "noreply@instnews.net")
BASE_URL = os.environ.get("BASE_URL", "https://www.instnews.net")

_gmail_service = None


def _get_gmail_service():
    """Build Gmail API service using Firebase service account with delegation."""
    global _gmail_service
    if _gmail_service is not None:
        return _gmail_service

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        # Load credentials from the same source as Firebase
        creds_path = os.environ.get("FIREBASE_CREDENTIALS", "")
        creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")

        scopes = ["https://www.googleapis.com/auth/gmail.send"]

        if creds_path and os.path.exists(creds_path):
            credentials = service_account.Credentials.from_service_account_file(
                creds_path, scopes=scopes
            )
        elif creds_json:
            info = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=scopes
            )
        else:
            logger.warning("No service account credentials found for Gmail API")
            return None

        # Delegate to the sender email
        delegated = credentials.with_subject(SENDER_EMAIL)
        _gmail_service = build("gmail", "v1", credentials=delegated, cache_discovery=False)
        logger.info("Gmail API service initialized", extra={"sender": SENDER_EMAIL})
        return _gmail_service
    except Exception:
        logger.exception("Failed to initialize Gmail API service")
        return None


def _send_email(to_email, subject, html_body):
    """Send an email via Gmail API. Falls back to logging in dev."""
    service = _get_gmail_service()

    if service is None:
        logger.info("Email (dev mode — Gmail API not configured)",
                     extra={"to": to_email, "subject": subject})
        # Log a readable version for dev testing
        import re
        text = re.sub(r'<[^>]+>', '', html_body).strip()
        for line in text.split('\n'):
            line = line.strip()
            if line:
                logger.info(f"  {line}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"InstNews <{SENDER_EMAIL}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        logger.info("Email sent", extra={"to": to_email, "subject": subject})
    except Exception:
        logger.exception("Failed to send email", extra={"to": to_email})


def send_verification_email(email, token):
    """Send email verification link after signup."""
    verify_url = f"{BASE_URL}/api/auth/verify-email?token={token}"
    subject = "Verify your InstNews account"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;padding:32px;">
        <h2 style="color:#333;margin:0 0 16px;">Welcome to InstNews</h2>
        <p style="color:#555;line-height:1.6;">
            Please verify your email address to activate your account.
        </p>
        <a href="{verify_url}"
           style="display:inline-block;padding:12px 24px;background:#238636;color:#fff;
                  text-decoration:none;border-radius:6px;font-weight:600;margin:16px 0;">
            Verify Email
        </a>
        <p style="color:#888;font-size:13px;margin-top:24px;">
            This link expires in 24 hours. If you didn't create an account, you can ignore this email.
        </p>
        <p style="color:#888;font-size:12px;word-break:break-all;">
            Or copy this link: {verify_url}
        </p>
    </div>
    """
    _send_email(email, subject, html)


def send_password_reset_email(email, token):
    """Send password reset link."""
    reset_url = f"{BASE_URL}/?reset_token={token}"
    subject = "Reset your InstNews password"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;padding:32px;">
        <h2 style="color:#333;margin:0 0 16px;">Password Reset</h2>
        <p style="color:#555;line-height:1.6;">
            We received a request to reset your password. Click the button below to choose a new one.
        </p>
        <a href="{reset_url}"
           style="display:inline-block;padding:12px 24px;background:#238636;color:#fff;
                  text-decoration:none;border-radius:6px;font-weight:600;margin:16px 0;">
            Reset Password
        </a>
        <p style="color:#888;font-size:13px;margin-top:24px;">
            This link expires in 1 hour. If you didn't request a reset, you can ignore this email.
        </p>
    </div>
    """
    _send_email(email, subject, html)


def send_provider_conflict_email(email, existing_method, login_url=None):
    """Notify user their email is registered with a different auth provider."""
    login_url = login_url or BASE_URL
    method_labels = {
        "google": "Google sign-in",
        "wechat": "WeChat sign-in",
        "email": "email and password",
    }
    method_label = method_labels.get(existing_method, existing_method)

    subject = "InstNews — Account already exists"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:480px;margin:0 auto;padding:32px;">
        <h2 style="color:#333;margin:0 0 16px;">Account Already Exists</h2>
        <p style="color:#555;line-height:1.6;">
            An account with <strong>{email}</strong> is already registered using <strong>{method_label}</strong>.
        </p>
        <p style="color:#555;line-height:1.6;">
            Please sign in using {method_label} instead.
        </p>
        <a href="{login_url}"
           style="display:inline-block;padding:12px 24px;background:#238636;color:#fff;
                  text-decoration:none;border-radius:6px;font-weight:600;margin:16px 0;">
            Go to Login
        </a>
        <p style="color:#888;font-size:13px;margin-top:24px;">
            If you didn't try to create an account, you can safely ignore this email.
        </p>
    </div>
    """
    _send_email(email, subject, html)
