"""
Pydantic schemas for user models.

Uses a lenient email validator that accepts any syntactically valid address,
including reserved/test TLDs like .test, .local, .example — which strict
RFC validators (e.g. pydantic-email-validator) reject.
"""

from datetime import datetime
from typing import Optional, Annotated
import re
from pydantic import BaseModel, Field, AfterValidator


def _lenient_email(v: str) -> str:
    """
    Validate email structure only — no TLD registry lookups.
    Accepts: user@host.tld  where tld is 1+ alpha chars.
    Normalises to lowercase.
    """
    if not isinstance(v, str):
        raise ValueError("Email must be a string")
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{1,}$'
    if not re.match(pattern, v.strip()):
        raise ValueError(f"'{v}' is not a valid email address")
    return v.strip().lower()


LenientEmail = Annotated[str, AfterValidator(_lenient_email)]


class UserBase(BaseModel):
    email: LenientEmail
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """JSON body login — alternative to OAuth2 form."""
    email: LenientEmail
    password: str
