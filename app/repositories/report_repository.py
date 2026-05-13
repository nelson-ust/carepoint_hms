from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import date, datetime, timedelta
from typing import List, Optional, Any

from app.models.all_models import (
    Invoice, Payment, Patient, Visit, Admission, StaffProfile, 
    Diagnosis, InventoryStockItem, StockMovement, Department, 
    EmployeeShift
)
from app.core.enums import ShiftStatus

class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_financial_stats(self, start_date: Optional[date] = None, end_date: Optional[date] = None):
        query_invoices = self.db.query(
            func.sum(Invoice.total_amount).label("total_invoiced"),
            func.sum(Invoice.amount_paid).label("total_paid")
        )
        query_payments = self.db.query(func.sum(Payment.amount).label("total_revenue"))

        if start_date:
            query_invoices = query_invoices.filter(Invoice.invoice_date >= start_date)
            query_payments = query_payments.filter(Payment.paid_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query_invoices = query_invoices.filter(Invoice.invoice_date <= end_date)
            query_payments = query_payments.filter(Payment.paid_at <= datetime.combine(end_date, datetime.max.time()))

        return query_invoices.first(), query_payments.first()

    def get_clinical_stats(self):
        total_diagnoses = self.db.query(Diagnosis).count()
        top_diagnoses = (
            self.db.query(Diagnosis.diagnosis_name, func.count(Diagnosis.id).label("count"))
            .group_by(Diagnosis.diagnosis_name)
            .order_by(desc("count"))
            .limit(5)
            .all()
        )
        
        # Last 7 days visit trends
        today = date.today()
        seven_days_ago = today - timedelta(days=7)
        visit_trends = (
            self.db.query(func.date(Visit.date_created).label("date"), func.count(Visit.id).label("count"))
            .filter(Visit.date_created >= seven_days_ago)
            .group_by(func.date(Visit.date_created))
            .all()
        )

        return {
            "total_diagnoses": total_diagnoses,
            "top_diagnoses": [{"name": d.diagnosis_name, "count": d.count} for d in top_diagnoses],
            "visit_trends": [{"date": str(v.date), "count": v.count} for v in visit_trends]
        }

    def get_inventory_stats(self):
        total_items = self.db.query(InventoryStockItem).count()
        low_stock_items = self.db.query(InventoryStockItem).filter(InventoryStockItem.quantity_on_hand <= InventoryStockItem.reorder_level).count()
        total_stock_value = self.db.query(func.sum(InventoryStockItem.quantity_on_hand * InventoryStockItem.unit_cost)).scalar() or 0.0
        
        recent_movements = (
            self.db.query(StockMovement)
            .order_by(desc(StockMovement.date_created))
            .limit(5)
            .all()
        )

        return {
            "total_items": total_items,
            "low_stock_items": low_stock_items,
            "total_stock_value": float(total_stock_value),
            "recent_stock_movements": [
                {
                    "item_id": m.stock_item_id, 
                    "type": str(m.movement_type), 
                    "quantity": m.quantity,
                    "date": str(m.date_created)
                } for m in recent_movements
            ]
        }

    def get_workforce_stats(self):
        total_staff = self.db.query(StaffProfile).count()
        staff_by_dept = (
            self.db.query(Department.name, func.count(StaffProfile.id).label("count"))
            .join(StaffProfile, StaffProfile.department_id == Department.id)
            .group_by(Department.name)
            .all()
        )
        
        active_shifts = self.db.query(EmployeeShift).filter(EmployeeShift.status == ShiftStatus.ON_DUTY).count()

        return {
            "total_staff": total_staff,
            "staff_by_department": [{"name": s.name, "count": s.count} for s in staff_by_dept],
            "active_shifts_today": active_shifts
        }
