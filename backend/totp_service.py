"""backend.totp_service

TOTP (Time-based One-Time Password) two-factor authentication service.
Implements RFC 6238 and is compatible with standard authenticator apps
such as Google Authenticator / Microsoft Authenticator / Duo.

Flow:
    1. After a successful password login, call setup_totp() to get a QR-code URI.
    2. After the user scans the QR code, call confirm_totp() with the first code
         to activate TOTP.
    3. On subsequent logins (after password verification), call verify_totp() to
         validate the 6-digit code.
    4. Call disable_totp() to turn off 2FA.
"""

import pyotp
import qrcode
import base64
import io
from typing import Optional
from database import db

APP_NAME = "DGSpace"


class TotpService:

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_secret(email: str, user_type: str) -> Optional[str]:
        """Read the user's TOTP secret from DB.

        Includes inactive secrets so the user can scan + confirm activation.
        """
        row = db.fetch_one(
            "SELECT secret FROM totp_secrets WHERE email = %s AND user_type = %s",
            (email, user_type),
        )
        return row["secret"] if row else None

    # ------------------------------------------------------------------
    # 1) Generate/refresh secret and return QR Code data URI
    # ------------------------------------------------------------------

    @staticmethod
    def setup_totp(email: str, user_type: str) -> dict:
        """
        Generate a new TOTP secret for the user and write it to the database
        (is_active=FALSE until confirmed).

        Returns an otpauth URI and a Base64-encoded PNG QR code for the frontend.

        Returns:
            {
                "success": True,
                "secret": "BASE32SECRET...",
                "otpauth_uri": "otpauth://totp/...",
                "qr_code_base64": "data:image/png;base64,..."
            }
        """
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=email, issuer_name=APP_NAME)

    # Generate PNG QR code and encode to base64
        img = qrcode.make(uri)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode()
        qr_data_uri = f"data:image/png;base64,{b64}"

    # Remove any existing secret, then insert the new secret (inactive)
        db.execute_query(
            "DELETE FROM totp_secrets WHERE email = %s AND user_type = %s",
            (email, user_type),
        )
        db.execute_query(
            """
            INSERT INTO totp_secrets (email, user_type, secret, is_active)
            VALUES (%s, %s, %s, FALSE)
            """,
            (email, user_type, secret),
        )

        return {
            "success": True,
            "secret": secret,          # for manual entry / backup
            "otpauth_uri": uri,
            "qr_code_base64": qr_data_uri,
        }

    # ------------------------------------------------------------------
    # 2) Confirm first code after scan → activate 2FA
    # ------------------------------------------------------------------

    @staticmethod
    def confirm_totp(email: str, user_type: str, code: str) -> dict:
        """
        Validate the user's first TOTP code.
        If valid, set is_active=TRUE to activate 2FA.
        """
        secret = TotpService._get_secret(email, user_type)
        if not secret:
            return {"success": False, "message": "No 2FA setup found. Please call setup first."}

        totp = pyotp.TOTP(secret)
        # valid_window=1 allows ±1 time-step (±30s) to tolerate clock drift
        if not totp.verify(code, valid_window=1):
            return {"success": False, "message": "Invalid code. Please try again."}

        db.execute_query(
            "UPDATE totp_secrets SET is_active = TRUE WHERE email = %s AND user_type = %s",
            (email, user_type),
        )
        return {"success": True, "message": "2FA enabled successfully."}

    # ------------------------------------------------------------------
    # 3) Verify TOTP code during login
    # ------------------------------------------------------------------

    @staticmethod
    def verify_totp(email: str, user_type: str, code: str) -> dict:
        """
        Validate the 6-digit TOTP code at login time (when 2FA is active).

        Returns:
            {"success": True/False, "message": "..."}
        """
        row = db.fetch_one(
            "SELECT secret FROM totp_secrets WHERE email = %s AND user_type = %s AND is_active = TRUE",
            (email, user_type),
        )
        if not row:
            # No active 2FA → skip (do not block login)
            return {"success": True, "required": False}

        totp = pyotp.TOTP(row["secret"])
        if totp.verify(code, valid_window=1):
            return {"success": True, "required": True}
        return {"success": False, "required": True, "message": "Invalid or expired 2FA code."}

    # ------------------------------------------------------------------
    # 4) Disable 2FA
    # ------------------------------------------------------------------

    @staticmethod
    def disable_totp(email: str, user_type: str) -> dict:
        """Delete the user's TOTP secret and disable 2FA."""
        db.execute_query(
            "DELETE FROM totp_secrets WHERE email = %s AND user_type = %s",
            (email, user_type),
        )
        return {"success": True, "message": "2FA disabled."}

    # ------------------------------------------------------------------
    # 5) Get 2FA status
    # ------------------------------------------------------------------

    @staticmethod
    def get_totp_status(email: str, user_type: str) -> dict:
        """Return whether 2FA is enabled for the given user."""
        row = db.fetch_one(
            "SELECT is_active FROM totp_secrets WHERE email = %s AND user_type = %s",
            (email, user_type),
        )
        if not row:
            return {"enabled": False}
        return {"enabled": bool(row["is_active"])}
