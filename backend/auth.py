import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend import models, passwords

DEVELOPMENT_JWT_SECRET = "admin_secret_key_123"
TOKEN_LIFETIME_MINUTES = 15

bearer_scheme = HTTPBearer(auto_error=False)


def bootstrap_admin(db: Session) -> None:
    username = os.getenv("AUTH_DEFAULT_USERNAME", "admin")
    default_password = os.getenv("AUTH_DEFAULT_PASSWORD", "1234")
    app_environment = os.getenv("APP_ENV", "production").lower()
    if app_environment != "development":
        if not os.getenv("AUTH_DEFAULT_USERNAME") or not os.getenv("AUTH_DEFAULT_PASSWORD"):
            raise RuntimeError(
                "Production must set AUTH_DEFAULT_USERNAME and AUTH_DEFAULT_PASSWORD."
            )
        try:
            passwords.validate_password(default_password)
        except ValueError as error:
            raise RuntimeError(
                "Production bootstrap password must meet the password policy."
            ) from error

    if db.query(models.User).filter_by(username=username).first():
        return

    db.add(
        models.User(
            username=username,
            password_hash=passwords.hash_password(default_password),
            must_change_password=True,
        )
    )
    db.commit()


def verify_user_password(user: models.User, password: str) -> bool:
    return passwords.verify_password(password, user.password_hash)


def invalid_login() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


def password_policy_error(error: Exception | str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(error),
    )


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "")
    app_environment = os.getenv("APP_ENV", "production").lower()
    if app_environment == "development" and secret == DEVELOPMENT_JWT_SECRET:
        return secret
    if not secret or len(secret) < 32 or secret.startswith("REPLACE_WITH_"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT authentication is not configured with a strong secret",
        )
    return secret


def create_access_token(user: models.User, scopes: list[str]) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user.username,
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_LIFETIME_MINUTES),
        "iss": os.getenv("JWT_ISSUER", "agrotech-enterprise"),
        "aud": os.getenv("JWT_AUDIENCE", "agrotech-api"),
        "scope": scopes,
        "must_change_password": user.must_change_password,
    }
    return jwt.encode(claims, _jwt_secret(), algorithm="HS256")


async def authenticated_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return jwt.decode(
            credentials.credentials,
            _jwt_secret(),
            algorithms=["HS256"],
            issuer=os.getenv("JWT_ISSUER", "agrotech-enterprise"),
            audience=os.getenv("JWT_AUDIENCE", "agrotech-api"),
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.InvalidTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def require_scope(required_scope: str) -> Callable[..., Any]:
    async def verify_bearer_token(
        claims: dict[str, Any] = Depends(authenticated_claims),
    ) -> dict[str, Any]:
        if claims.get("must_change_password"):
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail={
                    "code": "password_change_required",
                    "message": "Change the default password before using this resource.",
                },
            )

        token_scopes = claims.get("scope", [])
        scopes = token_scopes.split() if isinstance(token_scopes, str) else token_scopes
        if not isinstance(scopes, list) or required_scope not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token requires the {required_scope} scope",
            )

        return claims

    return verify_bearer_token


def get_user_for_claims(db: Session, claims: dict[str, Any]) -> models.User:
    user = db.query(models.User).filter_by(username=claims.get("sub")).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
