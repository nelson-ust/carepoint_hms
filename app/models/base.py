# carepoint_hms/app/models/base.py
from __future__ import annotations

"""
carepoint_hms.app.models.base

Shared SQLAlchemy base classes for the Carepoint HMS project.

Purpose
-------
This module provides the foundational ORM classes used by all database models
in the application.

It defines:

1. `Base`
   - The root declarative base class for all ORM models.
   - Automatically generates table names in snake_case.

2. `BaseTable`
   - An abstract base model that includes common audit fields and soft-delete
     support for all business tables.

Design goals
------------
- Use SQLAlchemy 2.x typed ORM style
- Keep model definitions consistent across modules
- Centralize common columns such as timestamps and auditing fields
- Support soft deletion
- Make future extensions easier

Typical usage
-------------
Example:

    from sqlalchemy.orm import Mapped, mapped_column
    from sqlalchemy import String
    from app.models.base import BaseTable

    class Patient(BaseTable):
        full_name: Mapped[str] = mapped_column(String(255), nullable=False)

Notes
-----
- `BaseTable` is abstract and does not create a database table on its own.
- All concrete models should inherit from `BaseTable` unless there is a very
  specific reason not to.
"""

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


def utc_now() -> datetime:
    """
    Return the current UTC datetime.

    This function is used as the default factory for timestamp columns so that
    each inserted row gets a fresh timestamp at creation/update time.
    """
    return datetime.now(timezone.utc)


def camel_to_snake(name: str) -> str:
    """
    Convert a CamelCase class name to snake_case.

    Examples
    --------
    Patient -> patient
    VisitFlowStep -> visit_flow_step
    TwoFactorChallenge -> two_factor_challenge
    """
    step_1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step_1).lower()


class MasterBase(DeclarativeBase):
    """
    Declarative base for tables that reside in the Master Database.
    """
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return camel_to_snake(cls.__name__)

class TenantBase(DeclarativeBase):
    """
    Declarative base for tables that reside in individual Tenant Databases.
    """
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return camel_to_snake(cls.__name__)


class BaseTable:
    """
    Mixin-style reusable base for business entities.
    """
    __abstract__ = True
    """
    Abstract reusable base model for business entities.

    Common fields included
    ----------------------
    id
        Integer primary key.

    is_active
        Logical active/inactive state for records that may be disabled without
        being deleted.

    is_deleted
        Soft delete flag. A deleted record remains in the database for
        recovery/auditing purposes.

    date_created
        UTC timestamp showing when the row was created.

    date_updated
        UTC timestamp showing when the row was last updated.

    date_deleted
        UTC timestamp showing when the row was soft-deleted.

    created_by_id
        Optional user ID of the actor who created the record.

    updated_by_id
        Optional user ID of the actor who last updated the record.

    deleted_by_id
        Optional user ID of the actor who soft-deleted the record.

    Why this exists
    ---------------
    Most HMS models need auditability. Rather than redefining these columns
    repeatedly, they are centralized here.

    Notes
    -----
    - This class is abstract and does not map to a physical table.
    - The `*_by_id` fields are intentionally simple integer references for
      flexibility. You may later convert them into explicit foreign keys to
      the users table if preferred.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Primary key identifier for the record.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
        doc="Indicates whether the record is currently active.",
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
        doc="Soft delete flag. True means the record is logically deleted.",
    )

    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
        doc="UTC timestamp when the record was created.",
    )

    date_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        doc="UTC timestamp when the record was last updated.",
    )

    date_deleted: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the record was soft-deleted.",
    )

    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        doc="Optional user ID of the actor who created this record.",
    )

    updated_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        doc="Optional user ID of the actor who last updated this record.",
    )

    @property
    def created_at(self) -> datetime:
        return self.date_created

    @property
    def updated_at(self) -> datetime:
        return self.date_updated


    deleted_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        doc="Optional user ID of the actor who soft-deleted this record.",
    )

    def soft_delete(self, deleted_by_id: Optional[int] = None) -> None:
        """
        Soft-delete the current record.

        Parameters
        ----------
        deleted_by_id:
            Optional ID of the user performing the delete action.
        """
        self.is_deleted = True
        self.is_active = False
        self.date_deleted = utc_now()
        self.deleted_by_id = deleted_by_id

    def restore(self) -> None:
        """
        Restore a previously soft-deleted record.
        """
        self.is_deleted = False
        self.is_active = True
        self.date_deleted = None
        self.deleted_by_id = None

    @property
    def is_soft_deleted(self) -> bool:
        """
        Convenience property for checking soft delete state.
        """
        return self.is_deleted is True

class MasterTable(MasterBase, BaseTable):
    """
    Abstract base for business tables in the Master DB.
    """
    __abstract__ = True

class TenantTable(TenantBase, BaseTable):
    """
    Abstract base for business tables in a Tenant DB.
    """
    __abstract__ = True
    

'''
utils/audit_util.py
utils/date_time.py
utils/email_utils.py
utils/file_utils.py
utils/helpers.py
utils/otp_utils.py
utils/password_utils.py
utils/pagination.py
utils/password_util.py
utils/queue_number.py
utils/report_util.py
utils/sms_util.py
utils/validators.py
utils/visit_code.py

'''    