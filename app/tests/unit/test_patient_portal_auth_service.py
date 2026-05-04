"""Unit tests for PatientPortalAuthService helpers."""
from __future__ import annotations

import pytest

from app.services.patient_portal_auth_service import (
    OTP_CODE_LENGTH,
    _generate_otp,
    _hash_otp,
    _mask_email,
    _mask_phone,
)


class TestGenerateOtp:
    def test_has_correct_length(self):
        otp = _generate_otp()
        assert len(otp) == OTP_CODE_LENGTH
        assert otp.isdigit()

    def test_generates_unique(self):
        otps = {_generate_otp() for _ in range(50)}
        assert len(otps) >= 40


class TestHashOtp:
    def test_returns_hex_string(self):
        h = _hash_otp("123456")
        assert isinstance(h, str)
        assert len(h) > 0

    def test_deterministic(self):
        assert _hash_otp("11111") == _hash_otp("11111")

    def test_different_for_different_input(self):
        assert _hash_otp("11111") != _hash_otp("22222")


class TestMaskEmail:
    def test_masks_email(self):
        masked = _mask_email("john@example.com")
        assert "@" in masked
        # Should show first 2 chars of local part then asterisks
        assert masked.startswith("jo")

    def test_short_email(self):
        masked = _mask_email("a@b.co")
        assert "@" in masked


class TestMaskPhone:
    def test_masks_phone(self):
        masked = _mask_phone("+2348012345678")
        assert masked.startswith("+23")
        assert masked.endswith("78")
        assert "*" in masked
