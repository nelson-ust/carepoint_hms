# app/seeds/__init__.py
"""
Idempotent seed scripts for Carepoint HMS bootstrap data.

Two layers:
- ``seed_security_baseline`` — permissions / roles / role-permission map /
  optional bootstrap superuser.
- ``seed_demo_data``         — full demo dataset (facility, departments,
  SDPs, wards/beds, drugs, lab tests, billable services, notification
  templates, sample patients). Composes services + Pydantic schemas.
"""

from app.seeds.security_seed import (
    DEFAULT_PERMISSIONS,
    DEFAULT_ROLES,
    DEFAULT_ROLE_PERMISSIONS,
    reset_user_password,
    seed_security_baseline,
)
from app.seeds.seed_data import seed_demo_data

__all__ = [
    "DEFAULT_PERMISSIONS",
    "DEFAULT_ROLES",
    "DEFAULT_ROLE_PERMISSIONS",
    "reset_user_password",
    "seed_security_baseline",
    "seed_demo_data",
]
