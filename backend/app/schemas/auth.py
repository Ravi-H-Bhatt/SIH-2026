"""
Auth schemas — login request/response.
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    """
    Carries the *Supabase* access token obtained by the browser after the Google
    OAuth redirect. Only this token is trusted — the server re-derives the email,
    name and provider from Supabase, never from client-supplied fields.
    """

    access_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    role: str
