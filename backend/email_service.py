import os
import json
import base64
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import Config


def _get_access_token():
    """Exchange refresh token for a short-lived access token via OAuth2."""
    token_data = urllib.parse.urlencode({
        "client_id":     Config.GMAIL_CLIENT_ID,
        "client_secret": Config.GMAIL_CLIENT_SECRET,
        "refresh_token": Config.GMAIL_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read().decode())

    access_token = tokens.get("access_token")
    if not access_token:
        raise RuntimeError(f"[EMAIL] Failed to get access token: {tokens}")
    return access_token


def _send_via_gmail_api(to_email, subject, html_body):
    """Send an email using the Gmail REST API with OAuth2."""
    access_token = _get_access_token()

    # Build the MIME message
    msg = MIMEMultipart("alternative")
    msg["From"]    = Config.MAIL_DEFAULT_SENDER
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    # Gmail API expects base64url-encoded raw message
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    body = json.dumps({"raw": raw}).encode()

    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=body,
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())

    return result.get("id")


class EmailService:

    @staticmethod
    def send_verification_email(to_email, verification_code, full_name):
        """Send verification email via Gmail API"""
        try:
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 30px; }}
                    .code {{ font-size: 32px; font-weight: bold; color: #4CAF50; text-align: center; 
                             padding: 20px; background-color: #fff; border: 2px dashed #4CAF50; 
                             margin: 20px 0; letter-spacing: 5px; }}
                    .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Welcome to DGSpace!</h1>
                    </div>
                    <div class="content">
                        <h2>Hi {full_name},</h2>
                        <p>Thank you for registering with DGSpace. Please verify your email address by entering the code below:</p>
                        <div class="code">{verification_code}</div>
                        <p><strong>This code will expire in 15 minutes.</strong></p>
                        <p>If you didn't create an account with DGSpace, please ignore this email.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; 2026 DGSpace. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            msg_id = _send_via_gmail_api(
                to_email,
                "Verify Your Email - DGSpace",
                html_body,
            )
            print(f"[EMAIL] Verification email sent to {to_email}, id={msg_id}")
            return {'success': True, 'message': 'Verification email sent'}
        except Exception as e:
            print(f"[ERROR] Error sending email: {e}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def send_password_reset_email(to_email, reset_token, full_name):
        """Send password reset email via Gmail API"""
        try:
            reset_link = f"https://dgspace.up.railway.app/reset-password?token={reset_token}"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #FF5722; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 30px; }}
                    .button {{ display: inline-block; padding: 12px 30px; background-color: #FF5722; 
                              color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Password Reset Request</h1>
                    </div>
                    <div class="content">
                        <h2>Hi {full_name},</h2>
                        <p>We received a request to reset your password. Click the button below to create a new password:</p>
                        <p style="text-align: center;">
                            <a href="{reset_link}" class="button">Reset Password</a>
                        </p>
                        <p><strong>This link will expire in 1 hour.</strong></p>
                        <p>If you didn't request a password reset, please ignore this email.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; 2026 DGSpace. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            msg_id = _send_via_gmail_api(
                to_email,
                "Reset Your Password - DGSpace",
                html_body,
            )
            print(f"[EMAIL] Password reset email sent to {to_email}, id={msg_id}")
            return {'success': True, 'message': 'Password reset email sent'}
        except Exception as e:
            print(f"[ERROR] Error sending email: {e}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def send_print_completed_email(to_email, full_name, project_name, request_id):
        """Send print completion notification email via Gmail API"""
        try:
            pickup_link = f"https://dgspace-c5ff.up.railway.app/print-requests/{request_id}/"
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0; }}
                    .content {{ background-color: #f9f9f9; padding: 30px; border: 1px solid #e0e0e0; }}
                    .project {{ font-size: 1.1rem; font-weight: bold; color: #1a1a2e; background: #fff;
                                border-left: 4px solid #28a745; padding: 12px 16px; margin: 16px 0; }}
                    .button {{ display: inline-block; padding: 12px 30px; background-color: #28a745;
                               color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                    .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>&#x1F5A8;&#xFE0F; Your Print is Ready!</h1>
                    </div>
                    <div class="content">
                        <h2>Hi {full_name},</h2>
                        <p>Great news! Your 3D print request has been completed and is ready for pickup.</p>
                        <div class="project">&#x1F4E6; {project_name}</div>
                        <p>Please come to the DGSpace lab to pick up your print. If you have any questions, feel free to reply to this email or contact the lab staff.</p>
                        <p style="text-align:center">
                            <a href="{pickup_link}" class="button">View Request Details</a>
                        </p>
                    </div>
                    <div class="footer">
                        <p>&copy; 2026 DGSpace. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            msg_id = _send_via_gmail_api(
                to_email,
                f"Your 3D Print is Ready - {project_name}",
                html_body,
            )
            print(f"[EMAIL] Print completed email sent to {to_email}, id={msg_id}")
            return {'success': True, 'message': 'Print completed email sent'}
        except Exception as e:
            print(f"[ERROR] Error sending print completed email: {e}")
            return {'success': False, 'message': str(e)}
