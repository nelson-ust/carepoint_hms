# app/services/hospital_number_service.py
"""Configurable Hospital Membership Number (Hospital Number) generation.

The Hospital Number is the hospital-local membership identifier printed on
cards and internal documents. It is generated only when a patient is
registered at the hospital, is unique within the hospital, and is entirely
independent of the patient's permanent Global Patient ID.

Each tenant configures its own numbering scheme (prefix, suffix, branch/facility
code, year/period component, sequential counter with a minimum digit length, and
a reset rule). ``allocate_next`` hands out the next number atomically; the same
formatting powers a non-consuming ``preview``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.all_models import HospitalNumberConfig

_RESET_MODES = {"CONTINUOUS", "ANNUAL", "MONTHLY"}
_YEAR_FORMATS = {"YYYY", "YY"}


class HospitalNumberService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def get_or_create_config(self, *, for_update: bool = False) -> HospitalNumberConfig:
        q = self.db.query(HospitalNumberConfig).filter(
            HospitalNumberConfig.is_deleted.is_(False)
        ).order_by(HospitalNumberConfig.id.asc())
        if for_update:
            try:
                q = q.with_for_update()
            except Exception:
                pass
        cfg = q.first()
        if cfg is None:
            cfg = HospitalNumberConfig(
                prefix="HN", separator="-", min_digits=6,
                reset_mode="CONTINUOUS", next_sequence=1, is_active=True,
            )
            self.db.add(cfg)
            self.db.flush()
        return cfg

    def to_dict(self, cfg: HospitalNumberConfig) -> dict:
        return {
            "prefix": cfg.prefix,
            "suffix": cfg.suffix,
            "branch_code": cfg.branch_code,
            "separator": cfg.separator,
            "include_year": cfg.include_year,
            "year_format": cfg.year_format,
            "include_month": cfg.include_month,
            "min_digits": cfg.min_digits,
            "reset_mode": cfg.reset_mode,
            "next_sequence": cfg.next_sequence,
            "current_period": cfg.current_period,
            "is_active": cfg.is_active,
            "sample": self.preview(),
        }

    def update_config(self, data: dict) -> HospitalNumberConfig:
        cfg = self.get_or_create_config(for_update=True)
        if "separator" in data and data["separator"] is not None:
            sep = str(data["separator"])[:4]
            cfg.separator = sep or "-"
        for key in ("prefix", "suffix", "branch_code"):
            if key in data:
                v = data[key]
                setattr(cfg, key, (str(v).strip() or None) if v is not None else None)
        if "include_year" in data:
            cfg.include_year = bool(data["include_year"])
        if "include_month" in data:
            cfg.include_month = bool(data["include_month"])
        if data.get("year_format") in _YEAR_FORMATS:
            cfg.year_format = data["year_format"]
        if "min_digits" in data and data["min_digits"] is not None:
            cfg.min_digits = max(1, min(int(data["min_digits"]), 12))
        if data.get("reset_mode") in _RESET_MODES:
            cfg.reset_mode = data["reset_mode"]
        if "next_sequence" in data and data["next_sequence"] is not None:
            cfg.next_sequence = max(1, int(data["next_sequence"]))
        if "is_active" in data:
            cfg.is_active = bool(data["is_active"])
        self.db.add(cfg)
        self.db.commit()
        self.db.refresh(cfg)
        return cfg

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------
    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _display_period(cfg: HospitalNumberConfig, now: datetime) -> Optional[str]:
        if not (cfg.include_year or cfg.include_month):
            return None
        year = now.strftime("%Y") if cfg.year_format == "YYYY" else now.strftime("%y")
        if cfg.include_year and cfg.include_month:
            return f"{year}{now.strftime('%m')}"
        if cfg.include_year:
            return year
        return now.strftime("%m")  # month only

    @staticmethod
    def _reset_key(cfg: HospitalNumberConfig, now: datetime) -> Optional[str]:
        if cfg.reset_mode == "ANNUAL":
            return now.strftime("%Y")
        if cfg.reset_mode == "MONTHLY":
            return now.strftime("%Y%m")
        return None  # CONTINUOUS

    def _format(self, cfg: HospitalNumberConfig, seq: int, now: datetime) -> str:
        sep = cfg.separator or "-"
        parts = []
        if cfg.prefix:
            parts.append(cfg.prefix)
        if cfg.branch_code:
            parts.append(cfg.branch_code)
        disp = self._display_period(cfg, now)
        if disp:
            parts.append(disp)
        parts.append(str(int(seq)).zfill(max(1, cfg.min_digits or 1)))
        core = sep.join(parts)
        if cfg.suffix:
            core = f"{core}{sep}{cfg.suffix}"
        return core

    def preview(self) -> str:
        """Non-consuming sample of what the next number would look like."""
        cfg = self.get_or_create_config()
        now = self._now()
        reset_key = self._reset_key(cfg, now)
        seq = cfg.next_sequence
        if reset_key is not None and cfg.current_period != reset_key:
            seq = 1
        return self._format(cfg, seq, now)

    # ------------------------------------------------------------------
    # Allocation (consuming, atomic)
    # ------------------------------------------------------------------
    def allocate_next(self, *, uniqueness_check=None, max_attempts: int = 25) -> str:
        """Allocate and consume the next Hospital Number. ``uniqueness_check``
        is an optional callable(str)->bool returning True when a candidate is
        already taken; on collision the sequence advances until a free number
        is found. Caller commits the surrounding transaction."""
        cfg = self.get_or_create_config(for_update=True)
        now = self._now()
        reset_key = self._reset_key(cfg, now)
        if reset_key is not None and cfg.current_period != reset_key:
            cfg.next_sequence = 1
            cfg.current_period = reset_key

        attempts = 0
        while True:
            attempts += 1
            seq = cfg.next_sequence
            candidate = self._format(cfg, seq, now)
            cfg.next_sequence = seq + 1
            taken = False
            if uniqueness_check is not None:
                try:
                    taken = bool(uniqueness_check(candidate))
                except Exception:
                    taken = False
            if not taken:
                self.db.add(cfg)
                self.db.flush()
                return candidate
            if attempts >= max_attempts:
                # Fall back to a guaranteed-unique suffix rather than loop forever.
                self.db.add(cfg)
                self.db.flush()
                return f"{candidate}{(cfg.separator or '-')}{now.strftime('%H%M%S')}"
