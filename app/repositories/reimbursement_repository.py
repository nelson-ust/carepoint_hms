from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.all_models import ReimbursementRequest
from app.schemas.reimbursement_schemas import ReimbursementCreateSchema, ReimbursementUpdateSchema

class ReimbursementRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, request_id: int) -> Optional[ReimbursementRequest]:
        return self.db.scalars(
            select(ReimbursementRequest)
            .options(selectinload(ReimbursementRequest.account))
            .where(ReimbursementRequest.id == request_id)
        ).first()

    def list_requests(
        self, staff_profile_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> Tuple[List[ReimbursementRequest], int]:
        stmt = select(ReimbursementRequest).options(selectinload(ReimbursementRequest.account))
        if staff_profile_id:
            stmt = stmt.where(ReimbursementRequest.staff_profile_id == staff_profile_id)
        
        stmt = stmt.order_by(ReimbursementRequest.id.desc())
        
        total = len(self.db.scalars(stmt).all())
        items = list(self.db.scalars(stmt.offset(skip).limit(limit)).all())
        return items, total

    def create(self, data: ReimbursementCreateSchema) -> ReimbursementRequest:
        req = ReimbursementRequest(
            staff_profile_id=data.staff_profile_id,
            expense_date=data.expense_date,
            amount=data.amount,
            category=data.category,
            description=data.description,
            receipt_url=data.receipt_url,
            account_id=data.account_id,
        )
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

    def update(self, req: ReimbursementRequest, data: ReimbursementUpdateSchema) -> ReimbursementRequest:
        if data.expense_date is not None:
            req.expense_date = data.expense_date
        if data.amount is not None:
            req.amount = data.amount
        if data.category is not None:
            req.category = data.category
        if data.description is not None:
            req.description = data.description
        if data.receipt_url is not None:
            req.receipt_url = data.receipt_url
        if data.account_id is not None:
            req.account_id = data.account_id
            
        self.db.commit()
        self.db.refresh(req)
        return req

    def delete(self, req: ReimbursementRequest) -> None:
        self.db.delete(req)
        self.db.commit()
