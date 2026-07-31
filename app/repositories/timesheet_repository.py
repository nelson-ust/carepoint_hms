from typing import List, Optional, Tuple
from datetime import date
from decimal import Decimal

from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session, joinedload

from app.models.all_models import Timesheet, TimesheetEntry
from app.schemas.timesheet_schemas import TimesheetCreateSchema, TimesheetUpdateSchema, TimesheetEntryCreateSchema

class TimesheetRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, timesheet_id: int) -> Optional[Timesheet]:
        stmt = (
            select(Timesheet)
            .options(joinedload(Timesheet.entries))
            .where(Timesheet.id == timesheet_id)
        )
        return self.db.scalars(stmt).unique().first()

    def list_timesheets(
        self, staff_profile_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> Tuple[List[Timesheet], int]:
        stmt = select(Timesheet).options(joinedload(Timesheet.entries))
        count_stmt = select(Timesheet)

        if staff_profile_id:
            stmt = stmt.where(Timesheet.staff_profile_id == staff_profile_id)
            count_stmt = count_stmt.where(Timesheet.staff_profile_id == staff_profile_id)

        stmt = stmt.order_by(Timesheet.period_start.desc()).offset(skip).limit(limit)

        total = len(self.db.scalars(count_stmt).all())
        items = list(self.db.scalars(stmt).unique().all())
        return items, total

    def create(self, data: TimesheetCreateSchema) -> Timesheet:
        # Calculate totals from entries
        total_reg = sum((e.regular_hours for e in data.entries), Decimal("0.00"))
        total_ot = sum((e.overtime_hours for e in data.entries), Decimal("0.00"))
        total_night = sum((e.night_hours for e in data.entries), Decimal("0.00"))
        total_weekend = sum((e.weekend_hours for e in data.entries), Decimal("0.00"))
        total_holiday = sum((e.holiday_hours for e in data.entries), Decimal("0.00"))
        absences = sum((1 for e in data.entries if e.is_absent), 0)

        timesheet = Timesheet(
            staff_profile_id=data.staff_profile_id,
            period_start=data.period_start,
            period_end=data.period_end,
            notes=data.notes,
            total_regular_hours=total_reg,
            total_overtime_hours=total_ot,
            total_night_hours=total_night,
            total_weekend_hours=total_weekend,
            total_holiday_hours=total_holiday,
            absence_days=absences
        )
        self.db.add(timesheet)
        self.db.flush()

        for entry_data in data.entries:
            entry = TimesheetEntry(
                timesheet_id=timesheet.id,
                work_date=entry_data.work_date,
                regular_hours=entry_data.regular_hours,
                overtime_hours=entry_data.overtime_hours,
                night_hours=entry_data.night_hours,
                weekend_hours=entry_data.weekend_hours,
                holiday_hours=entry_data.holiday_hours,
                is_absent=entry_data.is_absent,
                is_leave=entry_data.is_leave,
                note=entry_data.note
            )
            self.db.add(entry)
            
        self.db.commit()
        self.db.refresh(timesheet)
        return timesheet

    def update(self, timesheet: Timesheet, data: TimesheetUpdateSchema) -> Timesheet:
        if data.notes is not None:
            timesheet.notes = data.notes

        if data.entries is not None:
            # Delete existing entries
            del_stmt = delete(TimesheetEntry).where(TimesheetEntry.timesheet_id == timesheet.id)
            self.db.execute(del_stmt)

            # Insert new entries
            for entry_data in data.entries:
                entry = TimesheetEntry(
                    timesheet_id=timesheet.id,
                    work_date=entry_data.work_date,
                    regular_hours=entry_data.regular_hours,
                    overtime_hours=entry_data.overtime_hours,
                    night_hours=entry_data.night_hours,
                    weekend_hours=entry_data.weekend_hours,
                    holiday_hours=entry_data.holiday_hours,
                    is_absent=entry_data.is_absent,
                    is_leave=entry_data.is_leave,
                    note=entry_data.note
                )
                self.db.add(entry)

            # Update totals
            timesheet.total_regular_hours = sum((e.regular_hours for e in data.entries), Decimal("0.00"))
            timesheet.total_overtime_hours = sum((e.overtime_hours for e in data.entries), Decimal("0.00"))
            timesheet.total_night_hours = sum((e.night_hours for e in data.entries), Decimal("0.00"))
            timesheet.total_weekend_hours = sum((e.weekend_hours for e in data.entries), Decimal("0.00"))
            timesheet.total_holiday_hours = sum((e.holiday_hours for e in data.entries), Decimal("0.00"))
            timesheet.absence_days = sum((1 for e in data.entries if e.is_absent), 0)

        self.db.commit()
        self.db.refresh(timesheet)
        return timesheet

    def delete(self, timesheet: Timesheet) -> None:
        self.db.delete(timesheet)
        self.db.commit()
