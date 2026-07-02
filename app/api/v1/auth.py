"""
Authentication endpoints: register, login (form OR JSON), token refresh.

Two login styles are supported:
  POST /auth/login          — OAuth2 form (username + password fields)
                              Used by Swagger UI "Authorize" button.
  POST /auth/login/json     — JSON body {"email": ..., "password": ...}
                              Used by curl/fetch with Content-Type: application/json.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db_session
from app.schemas.user import UserCreate, UserResponse, Token, LoginRequest
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.db.models import User as UserModel
from app.utils.limiter import rate_limit_login

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _authenticate_user(email: str, password: str, db: Session) -> UserModel:
    """Shared auth logic for both login endpoints."""
    user = db.query(UserModel).filter(UserModel.email == email.lower()).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    return user


def _make_token_response(user: UserModel) -> Token:
    return Token(
        access_token  = create_access_token(subject=user.email),
        refresh_token = create_refresh_token(subject=user.email),
        token_type    = "bearer",
    )


# ── register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db_session),
):
    """
    Register a new user.

    ```json
    { "email": "alice@example.com", "password": "secret123", "full_name": "Alice" }
    ```
    """
    if db.query(UserModel).filter(UserModel.email == user_data.email.lower()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="A user with this email already exists")

    user = UserModel(
        email           = user_data.email.lower(),
        hashed_password = hash_password(user_data.password),
        full_name       = user_data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── login: OAuth2 form (Swagger UI compatible) ────────────────────────────────

@router.post("/login", response_model=Token,
             summary="Login (OAuth2 form — use for Swagger Authorize)",
             dependencies=[Depends(rate_limit_login)])
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db_session),
):
    """
    Login with **form data** (`application/x-www-form-urlencoded`).

    - `username` field = your email address
    - `password` field = your password

    This is the standard OAuth2 format used by Swagger UI's **Authorize** button.

    ```bash
    curl -X POST http://localhost:8011/api/v1/auth/login \\
      -F "username=alice@example.com" \\
      -F "password=secret123"
    ```
    """
    user = _authenticate_user(form_data.username, form_data.password, db)
    return _make_token_response(user)


# ── login: JSON body (curl/fetch friendly) ────────────────────────────────────

@router.post("/login/json", response_model=Token,
             summary="Login (JSON body — use for curl / frontend fetch)",
             dependencies=[Depends(rate_limit_login)])
def login_json(
    body: LoginRequest,
    db: Session = Depends(get_db_session),
):
    """
    Login with a **JSON body** — easier to call from curl, Postman, or a JS frontend.

    ```json
    { "email": "alice@example.com", "password": "secret123" }
    ```

    ```bash
    curl -X POST http://localhost:8011/api/v1/auth/login/json \\
      -H "Content-Type: application/json" \\
      -d '{"email": "alice@example.com", "password": "secret123"}'
    ```
    """
    user = _authenticate_user(body.email, body.password, db)
    return _make_token_response(user)


# ── refresh ───────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=Token)
def refresh_token(
    user: UserModel = Depends(get_current_user),
):
    """Issue a fresh access + refresh token pair for the currently authenticated user."""
    return _make_token_response(user)
