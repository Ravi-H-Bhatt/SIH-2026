"""
Supabase Auth token verification — the server side of Google Sign-In.

Flow
----
1. Browser runs the Google OAuth redirect against Supabase Auth
   (`supabase.auth.signInWithOAuth({ provider: "google" })`).
2. Supabase returns a *Supabase* access token to the browser.
3. Browser POSTs that token to `POST /api/v1/auth/google`.
4. This module verifies the token **server-side** and returns the identity.
5. The API then issues our own short-lived application JWT.

Why verify by calling Supabase instead of decoding locally
----------------------------------------------------------
Supabase projects sign access tokens either with a shared HS256 secret or with
rotating asymmetric keys, depending on project age and settings. Calling
`GET /auth/v1/user` with the token delegates signature *and* revocation checking
to Supabase, so this keeps working across both schemes and honours a signed-out
session immediately. Sign-in is infrequent, so the extra round-trip is cheap.

Never trust any field the browser sends about itself — email, name and provider
are read exclusively from this verified response.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SupabaseAuthError(Exception):
    """Raised when a Supabase access token cannot be verified."""


@dataclass(frozen=True)
class VerifiedIdentity:
    """An identity confirmed by Supabase Auth."""

    subject: str
    email: str
    email_verified: bool
    full_name: Optional[str]
    avatar_url: Optional[str]
    provider: Optional[str]

    @property
    def email_domain(self) -> str:
        return self.email.rsplit("@", 1)[-1].lower() if "@" in self.email else ""


class SupabaseAuthVerifier:
    def __init__(self) -> None:
        self._base = (settings.SUPABASE_URL or "").rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(settings.GOOGLE_AUTH_ENABLED and settings.supabase_auth_configured)

    def verify_access_token(self, access_token: str) -> VerifiedIdentity:
        """
        Confirms `access_token` with Supabase and returns the verified identity.

        Raises SupabaseAuthError for anything less than a fully verified,
        email-bearing account.
        """
        if not self.enabled:
            raise SupabaseAuthError(
                "Google sign-in is not configured on this server. "
                "Set SUPABASE_URL and SUPABASE_ANON_KEY."
            )
        if not access_token or not access_token.strip():
            raise SupabaseAuthError("No access token supplied.")

        try:
            response = httpx.get(
                f"{self._base}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    # Supabase requires the anon key alongside the user token.
                    "apikey": settings.SUPABASE_ANON_KEY or "",
                },
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("Supabase Auth verification request failed: %s", exc)
            raise SupabaseAuthError("Could not reach the identity provider.") from exc

        if response.status_code in (401, 403):
            raise SupabaseAuthError("Sign-in session is invalid or has expired.")
        if response.status_code >= 400:
            logger.warning(
                "Supabase Auth returned %s: %s", response.status_code, response.text[:300]
            )
            raise SupabaseAuthError("Identity provider rejected the session.")

        try:
            payload: Dict[str, Any] = response.json()
        except ValueError as exc:
            raise SupabaseAuthError("Malformed response from identity provider.") from exc

        return self._to_identity(payload)

    @staticmethod
    def _to_identity(payload: Dict[str, Any]) -> VerifiedIdentity:
        subject = payload.get("id")
        email = (payload.get("email") or "").strip().lower()
        if not subject or not email:
            raise SupabaseAuthError("Identity provider did not return an email address.")

        metadata = payload.get("user_metadata") or {}
        app_metadata = payload.get("app_metadata") or {}

        # Supabase exposes confirmation as a timestamp; user_metadata carries the
        # provider's own claim. Treat either as sufficient.
        email_verified = bool(
            payload.get("email_confirmed_at")
            or payload.get("confirmed_at")
            or metadata.get("email_verified")
        )

        provider = app_metadata.get("provider")
        if not provider:
            providers = app_metadata.get("providers") or []
            provider = providers[0] if providers else None

        full_name = (
            metadata.get("full_name")
            or metadata.get("name")
            or " ".join(
                part for part in (metadata.get("given_name"), metadata.get("family_name")) if part
            ).strip()
            or None
        )

        return VerifiedIdentity(
            subject=str(subject),
            email=email,
            email_verified=email_verified,
            full_name=full_name,
            avatar_url=metadata.get("avatar_url") or metadata.get("picture"),
            provider=provider,
        )


supabase_auth = SupabaseAuthVerifier()
