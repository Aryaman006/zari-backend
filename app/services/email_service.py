"""
Email service using Resend API for transactional emails.
"""
import logging
from typing import Optional

import resend

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY

    def _is_configured(self) -> bool:
        return bool(settings.RESEND_API_KEY)

    async def send_verification_email(self, user: User, token: str) -> None:
        """Send email verification link."""
        if not self._is_configured():
            logger.warning("Email service not configured — skipping verification email")
            return

        verify_url = f"{settings.CUSTOMER_FRONTEND_URL}/verify-email?token={token}"
        html = f"""
        <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: auto; padding: 40px 20px;">
          <h1 style="color: #6B1F3A; margin-bottom: 8px;">Verify your email</h1>
          <p style="color: #555; font-size: 16px;">Hello {user.first_name},</p>
          <p style="color: #555; font-size: 16px;">
            Thank you for joining Zari & Jasi! Please verify your email address to complete your registration.
          </p>
          <a href="{verify_url}"
             style="display: inline-block; margin: 24px 0; padding: 14px 32px;
                    background: linear-gradient(135deg, #6B1F3A, #C9A84C);
                    color: #fff; text-decoration: none; border-radius: 8px;
                    font-weight: 600; font-size: 16px;">
            Verify Email Address
          </a>
          <p style="color: #999; font-size: 13px;">
            This link expires in 24 hours. If you didn't create an account, you can safely ignore this email.
          </p>
          <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
          <p style="color: #ccc; font-size: 12px;">© 2025 Zari & Jasi. All rights reserved.</p>
        </div>
        """

        try:
            resend.Emails.send({
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
                "to": [user.email],
                "subject": "Verify your email — Zari & Jasi",
                "html": html,
            })
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {e}")

    async def send_password_reset_email(self, user: User, token: str) -> None:
        """Send password reset link."""
        if not self._is_configured():
            logger.warning("Email service not configured — skipping password reset email")
            return

        reset_url = f"{settings.CUSTOMER_FRONTEND_URL}/reset-password?token={token}"
        html = f"""
        <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: auto; padding: 40px 20px;">
          <h1 style="color: #6B1F3A; margin-bottom: 8px;">Reset your password</h1>
          <p style="color: #555; font-size: 16px;">Hello {user.first_name},</p>
          <p style="color: #555; font-size: 16px;">
            We received a request to reset the password for your Zari & Jasi account.
          </p>
          <a href="{reset_url}"
             style="display: inline-block; margin: 24px 0; padding: 14px 32px;
                    background: linear-gradient(135deg, #6B1F3A, #C9A84C);
                    color: #fff; text-decoration: none; border-radius: 8px;
                    font-weight: 600; font-size: 16px;">
            Reset Password
          </a>
          <p style="color: #999; font-size: 13px;">
            This link expires in 1 hour. If you didn't request a password reset, please ignore this email.
          </p>
          <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
          <p style="color: #ccc; font-size: 12px;">© 2025 Zari & Jasi. All rights reserved.</p>
        </div>
        """

        try:
            resend.Emails.send({
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
                "to": [user.email],
                "subject": "Reset your password — Zari & Jasi",
                "html": html,
            })
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {e}")

    async def send_order_confirmation_email(self, user: User, order_id: str, total: float) -> None:
        """Send order confirmation."""
        if not self._is_configured():
            return

        order_url = f"{settings.CUSTOMER_FRONTEND_URL}/account/orders/{order_id}"
        html = f"""
        <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: auto; padding: 40px 20px;">
          <h1 style="color: #6B1F3A; margin-bottom: 8px;">Order Confirmed! 🎉</h1>
          <p style="color: #555; font-size: 16px;">Hello {user.first_name},</p>
          <p style="color: #555; font-size: 16px;">
            Thank you for your order! We're preparing it with love.
          </p>
          <div style="background: #f9f5f0; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0; color: #555;"><strong>Order ID:</strong> #{order_id[:8].upper()}</p>
            <p style="margin: 8px 0 0; color: #555;"><strong>Total:</strong> ₹{total:,.2f}</p>
          </div>
          <a href="{order_url}"
             style="display: inline-block; margin: 24px 0; padding: 14px 32px;
                    background: linear-gradient(135deg, #6B1F3A, #C9A84C);
                    color: #fff; text-decoration: none; border-radius: 8px;
                    font-weight: 600; font-size: 16px;">
            Track Your Order
          </a>
          <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
          <p style="color: #ccc; font-size: 12px;">© 2025 Zari & Jasi. All rights reserved.</p>
        </div>
        """

        try:
            resend.Emails.send({
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
                "to": [user.email],
                "subject": f"Order Confirmed — #{order_id[:8].upper()} | Zari & Jasi",
                "html": html,
            })
        except Exception as e:
            logger.error(f"Failed to send order confirmation to {user.email}: {e}")
