"""Token verification for the synthetic modern inventory service.

Tokens are validated against the platform identity provider's published keys;
no credentials or signing material live in this repository.
"""

import os

IDENTITY_ISSUER = os.environ.get("IDENTITY_ISSUER")
IDENTITY_AUDIENCE = os.environ.get("IDENTITY_AUDIENCE")


def verify_bearer_token(authorization_header: str | None) -> dict | None:
    """Return the principal for a valid bearer token, or None if it is not valid.

    The real implementation validates the signature against the issuer's JWKS
    and checks issuer, audience, and expiry. This fixture keeps the shape
    without embedding any key material.
    """
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return None

    token = authorization_header.removeprefix("Bearer ").strip()
    if not token:
        return None

    claims = _decode_and_verify(token)
    if claims is None:
        return None

    return {"subject": claims["sub"], "roles": claims.get("roles", [])}


def _decode_and_verify(token: str) -> dict | None:
    """Placeholder for JWKS-based verification; never trusts an unverified token."""
    raise NotImplementedError(
        "Synthetic fixture: wire this to the platform identity provider's JWKS."
    )
