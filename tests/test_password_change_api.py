import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from backend.main import change_password
from backend.schemas import ChangePasswordRequest


class DevelopmentPasswordLengthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            os.environ,
            {"APP_ENV": "development"},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

        self.db = MagicMock()
        self.user = SimpleNamespace(
            username="password-test-user",
            password_hash="existing-hash",
            must_change_password=True,
        )
        self.user_lookup = patch(
            "backend.auth.get_user_for_claims", return_value=self.user
        )
        self.user_lookup.start()
        self.addCleanup(self.user_lookup.stop)
        self.current_password = patch(
            "backend.auth.verify_user_password", return_value=True
        )
        self.current_password.start()
        self.addCleanup(self.current_password.stop)
        self.same_password = patch(
            "backend.passwords.verify_password", return_value=False
        )
        self.same_password.start()
        self.addCleanup(self.same_password.stop)
        self.password_hash = patch(
            "backend.passwords.hash_password", return_value="new-password-hash"
        )
        self.password_hash.start()
        self.addCleanup(self.password_hash.stop)
        self.access_token = patch(
            "backend.auth.create_access_token", return_value="new-access-token"
        )
        self.access_token.start()
        self.addCleanup(self.access_token.stop)

    def change_password(self, new_password: str):
        return change_password(
            ChangePasswordRequest(
                current_password="current-password",
                new_password=new_password,
            ),
            claims={"sub": self.user.username},
            db=self.db,
        )

    def test_rejects_empty_and_passwords_shorter_than_four_characters(self) -> None:
        for password in ("", "123"):
            with self.subTest(password=password):
                with self.assertRaises(HTTPException) as context:
                    self.change_password(password)
                self.assertEqual(context.exception.status_code, 422)

    def test_rejects_passwords_longer_than_eight_characters(self) -> None:
        with self.assertRaises(HTTPException) as context:
            self.change_password("123456789")
        self.assertEqual(context.exception.status_code, 422)

    def test_accepts_passwords_within_four_to_eight_character_range(self) -> None:
        for password in ("1234", "1234568", "12345678"):
            with self.subTest(password=password):
                response = self.change_password(password)
                self.assertFalse(response["must_change_password"])


if __name__ == "__main__":
    unittest.main()
