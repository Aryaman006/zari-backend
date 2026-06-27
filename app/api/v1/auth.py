from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from app.core.dependencies import DbSession, CurrentUser, CurrentVerifiedUser
from app.schemas.auth import (
    RegisterRequest, LoginRequest, RefreshTokenRequest,
    ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest,
    ResendVerificationRequest, TokenResponse, MessageResponse, UserResponse
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: DbSession):
    """Register a new customer account."""
    service = AuthService(db)
    result = await service.register(data)
    return result


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: DbSession):
    """Authenticate and receive JWT tokens."""
    service = AuthService(db)
    return await service.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshTokenRequest, db: DbSession):
    """Refresh access token using a valid refresh token."""
    service = AuthService(db)
    return await service.refresh_token(data.refresh_token)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(data: VerifyEmailRequest, db: DbSession):
    """Verify email address from the link sent to the user's email."""
    service = AuthService(db)
    await service.verify_email(data.token)
    return {"message": "Email verified successfully. You can now log in."}


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(data: ResendVerificationRequest, db: DbSession):
    """Resend email verification link."""
    service = AuthService(db)
    await service.resend_verification(data.email)
    return {"message": "Verification email sent. Please check your inbox."}


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(data: ForgotPasswordRequest, db: DbSession):
    """Request a password reset email."""
    service = AuthService(db)
    await service.forgot_password(data.email)
    return {"message": "If this email is registered, a password reset link has been sent."}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: ResetPasswordRequest, db: DbSession):
    """Reset password using a token from the reset email."""
    service = AuthService(db)
    await service.reset_password(data.token, data.password)
    return {"message": "Password reset successfully. You can now log in with your new password."}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    """Get the currently authenticated user's profile."""
    return current_user
