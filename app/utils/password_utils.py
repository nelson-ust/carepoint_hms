# utils/password_utils.py
from __future__ import annotations

"""
Password hashing, verification, and validation utilities.

Purpose
-------
This module centralizes password-related logic for the application.

Features
--------
- secure password hashing using Passlib CryptContext
- password verification
- hash upgrade / rehash checks
- password strength validation
- random temporary password generation

Notes
-----
- Passwords are hashed using bcrypt through Passlib.
- Plain-text passwords should never be stored in the database.
- Validation here is intentionally application-level and can be adjusted to
  match your organization's password policy.
"""

import secrets
import string
from typing import Optional

from passlib.context import CryptContext


# Shared password context used application-wide.
# This keeps hashing and verification consistent across all modules.
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def normalize_password(password: str) -> str:
    """
    Normalize a password input before validation or hashing.

    Args:
        password: Raw password input.

    Returns:
        str: Normalized password.

    Raises:
        ValueError: If the password is missing or blank.
    """
    if password is None:
        raise ValueError("Password cannot be None.")

    normalized = password.strip()
    if not normalized:
        raise ValueError("Password cannot be empty.")

    return normalized


def validate_password_strength(
    password: str,
    *,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digit: bool = True,
    require_special: bool = False,
) -> None:
    """
    Validate password strength against a configurable policy.

    Args:
        password: Plain-text password.
        min_length: Minimum required password length.
        require_uppercase: Whether uppercase letters are required.
        require_lowercase: Whether lowercase letters are required.
        require_digit: Whether numeric characters are required.
        require_special: Whether special characters are required.

    Raises:
        ValueError: If the password fails validation.
    """
    normalized = normalize_password(password)

    if len(normalized) < min_length:
        raise ValueError(f"Password must be at least {min_length} characters long.")

    if require_uppercase and not any(char.isupper() for char in normalized):
        raise ValueError("Password must contain at least one uppercase letter.")

    if require_lowercase and not any(char.islower() for char in normalized):
        raise ValueError("Password must contain at least one lowercase letter.")

    if require_digit and not any(char.isdigit() for char in normalized):
        raise ValueError("Password must contain at least one digit.")

    if require_special and not any(not char.isalnum() for char in normalized):
        raise ValueError("Password must contain at least one special character.")


def hash_password(password: str) -> str:
    """
    Hash a plain-text password.

    Args:
        password: Plain-text password.

    Returns:
        str: Secure password hash.

    Raises:
        ValueError: If the password is empty.
    """
    normalized = normalize_password(password)
    return pwd_context.hash(normalized)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored hash.

    Args:
        plain_password: User-supplied plain-text password.
        hashed_password: Stored password hash.

    Returns:
        bool: True if the password matches, otherwise False.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        normalized = normalize_password(plain_password)
        return pwd_context.verify(normalized, hashed_password)
    except Exception:
        # Fail closed on malformed hashes or invalid input.
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Check whether a stored hash should be upgraded.

    This is useful when password hashing policy changes over time.

    Args:
        hashed_password: Stored password hash.

    Returns:
        bool: True if the hash should be replaced with a newer one.
    """
    if not hashed_password:
        return False

    try:
        return pwd_context.needs_update(hashed_password)
    except Exception:
        return False


def verify_and_update_password(
    plain_password: str,
    hashed_password: str,
) -> tuple[bool, Optional[str]]:
    """
    Verify a password and return an upgraded hash if rehashing is needed.

    Args:
        plain_password: User-supplied password.
        hashed_password: Existing stored hash.

    Returns:
        tuple[bool, Optional[str]]:
            - bool: Whether verification succeeded
            - Optional[str]: New hash if rehash is needed, otherwise None
    """
    if not plain_password or not hashed_password:
        return False, None

    try:
        normalized = normalize_password(plain_password)
        verified, new_hash = pwd_context.verify_and_update(normalized, hashed_password)
        return verified, new_hash
    except Exception:
        return False, None


def generate_temporary_password(
    *,
    length: int = 12,
    include_special: bool = True,
) -> str:
    """
    Generate a random temporary password.

    Args:
        length: Desired password length.
        include_special: Whether to include special characters.

    Returns:
        str: Generated temporary password.

    Raises:
        ValueError: If the requested length is too short.
    """
    if length < 8:
        raise ValueError("Temporary password length must be at least 8 characters.")

    alphabet = string.ascii_letters + string.digits
    if include_special:
        alphabet += "!@#$%^&*()-_=+?"

    # Generate until the password satisfies the default strength policy.
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        try:
            validate_password_strength(
                password,
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digit=True,
                require_special=include_special,
            )
            return password
        except ValueError:
            continue


def password_policy_summary(
    *,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digit: bool = True,
    require_special: bool = False,
) -> dict[str, object]:
    """
    Return a machine-readable summary of the current password policy.

    Returns:
        dict[str, object]: Password policy metadata.
    """
    return {
        "min_length": min_length,
        "require_uppercase": require_uppercase,
        "require_lowercase": require_lowercase,
        "require_digit": require_digit,
        "require_special": require_special,
    }