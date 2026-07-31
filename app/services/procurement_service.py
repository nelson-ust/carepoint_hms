from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import ProcurementRequisitionStatus, RequestTypeCode
from app.models.all_models import PurchaseRequisition, RequestForQuotation, PurchaseOrder
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.procurement_schemas import (
    PurchaseRequisitionCreateSchema, 
    PurchaseRequisitionUpdateSchema, 
    PurchaseRequisitionSubmitSchema,
    RequestForQuotationCreateSchema,
    PurchaseOrderCreateSchema
)
from app.services.approval_service import ApprovalRequestService
from app.schemas.approval_schemas import ApprovalRequestCreateSchema

class ProcurementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProcurementRepository(db)
        self.approval_service = ApprovalRequestService(db)

    def get_requisition(self, requisition_id: int) -> PurchaseRequisition:
        requisition = self.repository.get_requisition_by_id(requisition_id)
        if not requisition:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procurement requisition not found")
        return requisition

    def list_requisitions(self, department_id: int = None, skip: int = 0, limit: int = 100) -> Tuple[List[PurchaseRequisition], int]:
        return self.repository.list_requisitions(department_id, skip, limit)

    def get_stats(self) -> dict:
        """Live supply-chain KPIs for the procurement dashboard."""
        open_statuses = [
            ProcurementRequisitionStatus.DRAFT,
            ProcurementRequisitionStatus.SUBMITTED,
            ProcurementRequisitionStatus.DEPARTMENT_APPROVED,
            ProcurementRequisitionStatus.FINANCE_APPROVED,
        ]
        pending_statuses = [
            ProcurementRequisitionStatus.SUBMITTED,
            ProcurementRequisitionStatus.DEPARTMENT_APPROVED,
        ]
        return {
            "open_requisitions": self.repository.count_requisitions_by_statuses(open_statuses),
            "pending_approval": self.repository.count_requisitions_by_statuses(pending_statuses),
            "low_stock_items": self.repository.count_low_stock_items(),
            "total_requisitions": self.repository.count_all_requisitions(),
            "total_estimated_value": self.repository.sum_estimated_total(open_statuses),
        }

    def department_name_map(self) -> dict:
        return self.repository.department_name_map()

    def staff_name_map(self) -> dict:
        return self.repository.staff_name_map()

    def create_requisition(
        self,
        data: PurchaseRequisitionCreateSchema,
        requested_by_user_id: int | None = None,
    ) -> PurchaseRequisition:
        # Attribute the requisition to the requester's staff profile. If the
        # payload didn't carry one, resolve it from the authenticated user;
        # if that user has no staff profile the column stays null (the model
        # allows it) so admins can still raise requisitions.
        if not data.requested_by_staff_id and requested_by_user_id:
            from app.models.all_models import StaffProfile
            sp = (
                self.db.query(StaffProfile)
                .filter(
                    StaffProfile.user_id == requested_by_user_id,
                    StaffProfile.is_deleted.is_(False),
                )
                .first()
            )
            if sp:
                data.requested_by_staff_id = sp.id
        return self.repository.create_requisition(data)

    def update_requisition(self, requisition_id: int, data: PurchaseRequisitionUpdateSchema) -> PurchaseRequisition:
        requisition = self.get_requisition(requisition_id)
        if requisition.status != ProcurementRequisitionStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requisitions can be modified"
            )
        return self.repository.update_requisition(requisition, data)

    def delete_requisition(self, requisition_id: int) -> None:
        requisition = self.get_requisition(requisition_id)
        if requisition.status != ProcurementRequisitionStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requisitions can be deleted"
            )
        self.repository.delete_requisition(requisition)

    def submit_requisition(self, requisition_id: int, data: PurchaseRequisitionSubmitSchema, user_id: int) -> PurchaseRequisition:
        requisition = self.get_requisition(requisition_id)
        if requisition.status != ProcurementRequisitionStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requisitions can be submitted"
            )

        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            request_type=RequestTypeCode.PROCUREMENT,
            subject_id=requisition.id,
            title=data.title,
        )
        
        self.approval_service.submit(approval_payload, requester_user_id=user_id)
        self.db.refresh(requisition)
        return requisition

    # ── RFQ Service Methods ───────────────────────────────────────────

    def create_rfq(self, data: RequestForQuotationCreateSchema) -> RequestForQuotation:
        rfq = self.repository.create_rfq(data)
        self.db.commit()
        return rfq

    # ── PO Service Methods ────────────────────────────────────────────

    def create_po(self, data: PurchaseOrderCreateSchema) -> PurchaseOrder:
        # Business Rule: If PO is from RFQ, validate RFQ exists
        if data.rfq_id:
            rfq = self.repository.get_rfq_by_id(data.rfq_id)
            if not rfq:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Request for quotation not found"
                )


        po = self.repository.create_po(data)
        self.db.commit()
        return po
