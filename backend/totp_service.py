"""
TOTP (Time-based One-Time Password) 二次验证服务
基于 RFC 6238，兼容 Google Authenticator / Microsoft Authenticator / Duo 等所有标准 TOTP 应用

流程：
  1. 用户登录成功后调用 setup_totp() 获取二维码 URI
  2. 用户扫码绑定后调用 confirm_totp() 验证第一个 TOTP 码以激活
  3. 以后每次登录，在密码验证通过后调用 verify_totp() 校验 6 位码
  4. 可调用 disable_totp() 关闭 2FA
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
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _get_secret(email: str, user_type: str) -> Optional[str]:
        """从数据库读取该用户的 TOTP 密钥（未激活的也读出来，供扫码确认）"""
        row = db.fetch_one(
            "SELECT secret FROM totp_secrets WHERE email = %s AND user_type = %s",
            (email, user_type),
        )
        return row["secret"] if row else None

    # ------------------------------------------------------------------
    # 1. 生成 / 刷新密钥并返回二维码数据 URI
    # ------------------------------------------------------------------

    @staticmethod
    def setup_totp(email: str, user_type: str) -> dict:
        """
        为用户生成新的 TOTP 密钥，写入数据库（is_active=FALSE 等待确认），
        返回 otpauth URI 和 Base64 PNG 二维码，供前端展示。

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

        # 生成 PNG 二维码并编码为 base64
        img = qrcode.make(uri)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode()
        qr_data_uri = f"data:image/png;base64,{b64}"

        # 删除旧密钥（如果有），插入新密钥（未激活）
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
            "secret": secret,          # 供手动输入备用
            "otpauth_uri": uri,
            "qr_code_base64": qr_data_uri,
        }

    # ------------------------------------------------------------------
    # 2. 用户扫码后输入第一个验证码 → 激活 2FA
    # ------------------------------------------------------------------

    @staticmethod
    def confirm_totp(email: str, user_type: str, code: str) -> dict:
        """
        验证用户提交的 TOTP 码是否正确，正确则将 is_active 置为 TRUE（激活 2FA）。
        """
        secret = TotpService._get_secret(email, user_type)
        if not secret:
            return {"success": False, "message": "未找到 2FA 设置，请先调用 setup"}

        totp = pyotp.TOTP(secret)
        # valid_window=1 允许前后各一个时间窗口（±30s），防止时钟偏差
        if not totp.verify(code, valid_window=1):
            return {"success": False, "message": "验证码不正确，请重试"}

        db.execute_query(
            "UPDATE totp_secrets SET is_active = TRUE WHERE email = %s AND user_type = %s",
            (email, user_type),
        )
        return {"success": True, "message": "2FA 已成功启用"}

    # ------------------------------------------------------------------
    # 3. 登录时验证 TOTP 码
    # ------------------------------------------------------------------

    @staticmethod
    def verify_totp(email: str, user_type: str, code: str) -> dict:
        """
        在用户已激活 2FA 的情况下，验证登录时提交的 6 位 TOTP 码。

        Returns:
            {"success": True/False, "message": "..."}
        """
        row = db.fetch_one(
            "SELECT secret FROM totp_secrets WHERE email = %s AND user_type = %s AND is_active = TRUE",
            (email, user_type),
        )
        if not row:
            # 用户没有激活 2FA，跳过（不阻断登录）
            return {"success": True, "required": False}

        totp = pyotp.TOTP(row["secret"])
        if totp.verify(code, valid_window=1):
            return {"success": True, "required": True}
        return {"success": False, "required": True, "message": "2FA 验证码错误或已过期"}

    # ------------------------------------------------------------------
    # 4. 关闭 2FA
    # ------------------------------------------------------------------

    @staticmethod
    def disable_totp(email: str, user_type: str) -> dict:
        """删除用户的 TOTP 密钥，关闭 2FA。"""
        db.execute_query(
            "DELETE FROM totp_secrets WHERE email = %s AND user_type = %s",
            (email, user_type),
        )
        return {"success": True, "message": "2FA 已关闭"}

    # ------------------------------------------------------------------
    # 5. 查询 2FA 状态
    # ------------------------------------------------------------------

    @staticmethod
    def get_totp_status(email: str, user_type: str) -> dict:
        """返回该用户的 2FA 启用状态。"""
        row = db.fetch_one(
            "SELECT is_active FROM totp_secrets WHERE email = %s AND user_type = %s",
            (email, user_type),
        )
        if not row:
            return {"enabled": False}
        return {"enabled": bool(row["is_active"])}
