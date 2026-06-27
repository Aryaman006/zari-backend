"""
Authentication service — handles registration, login, token management,
email verification, and password reset.
"""
from typing import Optional
from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_email_verify_token,
    create_password_reset_token,
    decode_refresh_token,
    decode_email_verify_token,
    decode_password_reset_token,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest, LoginRequest
from app.services.email_service import EmailService
from app.core.config import settings


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.email_service = EmailService()

    async def register(self, data: RegisterRequest) -> dict:
        """Register a new customer account."""
        if await self.user_repo.email_exists(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        user = User(
            email=data.email.lower().strip(),
            phone=data.phone,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            password_hash=hash_password(data.password),
            role="customer",
            is_verified=True,
            is_active=True,
        )
        user = await self.user_repo.create(user)

        # Send verification email (fire-and-forget, don't fail registration)
        try:
            token = create_email_verify_token(user.email)
            await self.email_service.send_verification_email(user, token)
        except Exception:
            pass  # Log in production but don't block registration

        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "user": user,
        }

    async def login(self, data: LoginRequest) -> dict:
        """Authenticate user and return tokens."""
        user = await self.user_repo.get_by_email(data.email.lower().strip())

        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Please contact support.",
            )

        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "user": user,
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        """Issue a new access token from a valid refresh token."""
        try:
            payload = decode_refresh_token(refresh_token)
            user_id: str = payload.get("sub")
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive.",
            )

        return {
            "access_token": create_access_token(user.id, user.role),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "Bearer",
            "user": user,
        }

    async def verify_email(self, token: str) -> User:
        """Verify email address from token."""
        try:
            payload = decode_email_verify_token(token)
            email: str = payload.get("sub")
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token. Please request a new one.",
            )

        user = await self.user_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email is already verified."
            )

        await self.user_repo.update_instance(user, is_verified=True)
        return user

    async def resend_verification(self, email: str) -> None:
        """Resend email verification link."""
        user = await self.user_repo.get_by_email(email.lower())
        if not user:
            # Don't reveal whether email exists
            return
        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email is already verified."
            )
        token = create_email_verify_token(user.email)
        await self.email_service.send_verification_email(user, token)

    async def forgot_password(self, email: str) -> None:
        """Send password reset email."""
        user = await self.user_repo.get_by_email(email.lower())
        if not user:
            return  # Don't reveal whether email exists
        token = create_password_reset_token(user.email)
        await self.email_service.send_password_reset_email(user, token)

    async def reset_password(self, token: str, new_password: str) -> None:
        """Apply new password from reset token."""
        try:
            payload = decode_password_reset_token(token)
            email: str = payload.get("sub")
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token.",
            )

        user = await self.user_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        await self.user_repo.update_instance(user, password_hash=hash_password(new_password))
