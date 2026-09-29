from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from .config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    subject: str
    organization_id: str | None
    role: str
    scopes: frozenset[str]
    client_id: str | None = None

    def require_role(self, role: str) -> None:
        if self.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required"
            )

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes and self.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing scope: {scope}"
            )


@lru_cache
def jwks_client(domain: str) -> PyJWKClient:
    return PyJWKClient(f"https://{domain}/.well-known/jwks.json")


def _decode(token: str, settings: Settings) -> dict:
    try:
        signing_key = jwks_client(settings.auth0_domain).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=settings.auth0_issuer or f"https://{settings.auth0_domain}/",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token"
        ) from exc


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    if settings.atlas_auth_mode == "demo":
        return AuthContext(
            subject="demo-user",
            organization_id=settings.atlas_demo_org_id,
            role=settings.atlas_demo_role,
            scopes=frozenset({"test-results:write"}),
            client_id="demo-client",
        )
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    claims = _decode(credentials.credentials, settings)
    roles = claims.get("https://atlas.local/roles", [])
    scope = claims.get("scope", "").split()
    return AuthContext(
        subject=claims.get("sub", ""),
        organization_id=claims.get("org_id"),
        role="admin" if "admin" in roles else "member",
        scopes=frozenset(scope),
        client_id=claims.get("azp") or claims.get("client_id"),
    )


def require_admin(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    auth.require_role("admin")
    return auth
