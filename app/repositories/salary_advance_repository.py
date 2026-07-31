from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from app.models.all_models import SalaryAdvance
from app.schemas.salary_advance_schemas import SalaryAdvanceCreateSchema, SalaryAdvanceUpdateSchema

class SalaryAdvanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, request_id: int) -> Optional[SalaryAdvance]:
        return self.db.scalars(
            select(SalaryAdvance)
            .options(selectinload(SalaryAdvance.account))
            .where(SalaryAdvance.id == request_id)
        ).first()

    def list_requests(
        self, staff_profile_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> Tuple[List[SalaryAdvance], int]:
        stmt = select(SalaryAdvance).options(selectinload(SalaryAdvance.account))
        if staff_profile_id:
            stmt = stmt.where(SalaryAdvance.staff_profile_id == staff_profile_id)
        
        stmt = stmt.order_by(SalaryAdvance.id.desc())
        
        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0
        
        items = list(self.db.scalars(stmt.offset(skip).limit(limit)).all())
        return items, total

    def create(self, data: SalaryAdvanceCreateSchema) -> SalaryAdvance:
        advance = SalaryAdvance(
            staff_profile_id=data.staff_profile_id,
            amount=data.amount,
            reason=data.reason,
            repayment_month=data.repayment_month,
            account_id=data.account_id,
        )
        self.db.add(advance)
        self.db.commit()
        self.db.refresh(advance)
        return advance

    def update(self, advance: SalaryAdvance, data: SalaryAdvanceUpdateSchema) -> SalaryAdvance:
        if data.amount is not None:
            advance.amount = data.amount
        if data.reason is not None:
            advance.reason = data.reason
        if data.repayment_month is not None:
            advance.repayment_month = data.repayment_month
        if getattr(data, "account_id", None) is not None:
            advance.account_id = data.account_id
            
        self.db.commit()
        self.db.refresh(advance)
        return advance

    def delete(self, advance: SalaryAdvance) -> None:
        self.db.delete(advance)
        self.db.commit()
