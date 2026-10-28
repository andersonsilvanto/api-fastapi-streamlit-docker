import base64
import hashlib
import hmac
import secrets


PASSWORD_HASH_ITERATIONS = 600_000
PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 8 characters and contain uppercase, lowercase, "
    "a number, and a special character."
)


def validate_password(password: str, development_mode: bool = False) -> None:
    if development_mode:
        if not 4 <= len(password) <= 8:
            raise ValueError(
                "Development passwords must contain between 4 and 8 characters."
            )
        return

    if (
        len(password) < 8
        or not any(character.isupper() for character in password)
        or not any(character.islower() for character in password)
        or not any(character.isdigit() for character in password)
        or not any(not character.isalnum() and not character.isspace() for character in password)
    ):
        raise ValueError(PASSWORD_POLICY_MESSAGE)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_HASH_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, encoded_salt, encoded_digest = password_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt)
        expected_digest = base64.urlsafe_b64decode(encoded_digest)
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(actual_digest, expected_digest)
