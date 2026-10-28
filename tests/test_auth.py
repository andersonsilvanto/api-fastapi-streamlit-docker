import asyncio
import time
import unittest
from unittest.mock import MagicMock, patch

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.auth import authenticated_claims, bootstrap_admin, require_scope
from backend.passwords import hash_password, validate_password, verify_password


SECRET = "test-only-signing-secret-with-more-than-32-characters"
ISSUER = "agrotech-test"
AUDIENCE = "agrotech-api-test"


def create_token(scope: str, secret: str = SECRET, expires_in: int = 300) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "smoke-test-user",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + expires_in,
            "scope": scope,
        },
        secret,
        algorithm="HS256",
    )


class RequireScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            "os.environ",
            {
                "JWT_SECRET_KEY": SECRET,
                "JWT_ISSUER": ISSUER,
                "JWT_AUDIENCE": AUDIENCE,
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def authenticate(self, token: str | None, must_change_password: bool = False):
        credentials = (
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            if token is not None
            else None
        )
        async def verify() -> dict:
            claims = await authenticated_claims(credentials)
            claims["must_change_password"] = must_change_password
            return await require_scope("items:write")(claims)

        return asyncio.run(verify())

    def test_accepts_valid_token_with_required_scope(self) -> None:
        claims = self.authenticate(create_token("items:read items:write"))
        self.assertEqual(claims["sub"], "smoke-test-user")

    def test_rejects_missing_token(self) -> None:
        with self.assertRaises(HTTPException) as context:
            self.authenticate(None)
        self.assertEqual(context.exception.status_code, 401)

    def test_rejects_invalid_signature(self) -> None:
        with self.assertRaises(HTTPException) as context:
            invalid_secret = "a-different-signing-secret-with-at-least-32-characters"
            self.authenticate(create_token("items:write", secret=invalid_secret))
        self.assertEqual(context.exception.status_code, 401)

    def test_rejects_expired_token(self) -> None:
        with self.assertRaises(HTTPException) as context:
            self.authenticate(create_token("items:write", expires_in=-1))
        self.assertEqual(context.exception.status_code, 401)

    def test_rejects_token_without_required_scope(self) -> None:
        with self.assertRaises(HTTPException) as context:
            self.authenticate(create_token("items:read"))
        self.assertEqual(context.exception.status_code, 403)

    def test_fails_closed_when_signing_secret_is_missing(self) -> None:
        with patch.dict("os.environ", {"JWT_SECRET_KEY": ""}):
            with self.assertRaises(HTTPException) as context:
                self.authenticate(create_token("items:write"))
        self.assertEqual(context.exception.status_code, 503)

    def test_requires_password_change_before_accessing_items(self) -> None:
        with self.assertRaises(HTTPException) as context:
            self.authenticate(
                create_token("items:write"),
                must_change_password=True,
            )
        self.assertEqual(context.exception.status_code, 428)


class PasswordPolicyTests(unittest.TestCase):
    def test_accepts_password_meeting_policy(self) -> None:
        validate_password("AgroTech!2026")

    def test_strong_policy_still_rejects_short_test_passwords(self) -> None:
        for password in ("", "123", "1234", "12345678"):
            with self.subTest(password=password):
                with self.assertRaises(ValueError):
                    validate_password(password)

    def test_rejects_password_missing_each_policy_requirement(self) -> None:
        for password in ("Short1!", "lowercase1!", "UPPERCASE1!", "NoNumber!!", "NoSpecial1"):
            with self.subTest(password=password):
                with self.assertRaises(ValueError):
                    validate_password(password)

    def test_password_hash_is_salted_and_verifiable(self) -> None:
        first_hash = hash_password("AgroTech!2026")
        second_hash = hash_password("AgroTech!2026")
        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(verify_password("AgroTech!2026", first_hash))
        self.assertFalse(verify_password("wrong-password", first_hash))


class BootstrapAdminTests(unittest.TestCase):
    def test_production_allows_admin_username_with_strong_password(self) -> None:
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        with patch.dict(
            "os.environ",
            {
                "APP_ENV": "production",
                "AUTH_DEFAULT_USERNAME": "admin",
                "AUTH_DEFAULT_PASSWORD": "AgroTech!2026",
            },
            clear=True,
        ), patch("backend.auth.passwords.hash_password", return_value="hashed-password"):
            bootstrap_admin(db)

        created_user = db.add.call_args.args[0]
        self.assertEqual(created_user.username, "admin")
        self.assertTrue(created_user.must_change_password)
        db.commit.assert_called_once()

    def test_production_rejects_default_password(self) -> None:
        db = MagicMock()

        with patch.dict(
            "os.environ",
            {
                "APP_ENV": "production",
                "AUTH_DEFAULT_USERNAME": "admin",
                "AUTH_DEFAULT_PASSWORD": "1234",
            },
            clear=True,
        ), self.assertRaises(RuntimeError):
            bootstrap_admin(db)


if __name__ == "__main__":
    unittest.main()
