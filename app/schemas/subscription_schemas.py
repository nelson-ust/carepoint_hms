# app/schemas/subscription_schemas.py
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.core.enums import SubscriptionStatus, SubscriptionInterval

class SubscriptionPlanReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    code: str
    description: Optional[str] = None
    price: Decimal
    currency: str
    interval: SubscriptionInterval
    
    max_facilities: int
    max_users: int
    max_patients: Optional[int] = None
    
    has_clinical: bool
    has_inpatient: bool
    has_laboratory: bool
    has_pharmacy: bool
    has_inventory: bool
    has_billing: bool
    has_reporting: bool
    has_appointments: bool
    has_patient_portal: bool
    has_insurance: bool
    has_radiology: bool
    has_surgical: bool
    has_hr: bool
    has_dietary: bool
    has_ambulance: bool
    has_compliance: bool
    
    is_active: bool

class TenantSubscriptionReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    tenant_id: int
    plan_id: int
    status: SubscriptionStatus
    start_date: datetime
    end_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    auto_renew: bool
    
    plan: Optional[SubscriptionPlanReadSchema] = None

class SubscriptionPlanCreateSchema(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    price: Decimal
    currency: str = "NGN"
    interval: SubscriptionInterval = SubscriptionInterval.MONTHLY
    
    max_facilities: int = 1
    max_users: int = 10
    max_patients: Optional[int] = None
    
    has_clinical: bool = True
    has_inpatient: bool = False
    has_laboratory: bool = False
    has_pharmacy: bool = False
    has_inventory: bool = False
    has_billing: bool = True
    has_reporting: bool = False
    has_appointments: bool = True
    has_patient_portal: bool = False
    has_insurance: bool = False
    has_radiology: bool = False
    has_surgical: bool = False
    has_hr: bool = False
    has_dietary: bool = False
    has_ambulance: bool = False
    has_compliance: bool = False
    
    is_active: bool = True

class SubscriptionPlanUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    max_facilities: Optional[int] = None
    max_users: Optional[int] = None
    max_patients: Optional[int] = None
    
    has_clinical: Optional[bool] = None
    has_inpatient: Optional[bool] = None
    has_laboratory: Optional[bool] = None
    has_pharmacy: Optional[bool] = None
    has_inventory: Optional[bool] = None
    has_billing: Optional[bool] = None
    has_reporting: Optional[bool] = None
    has_appointments: Optional[bool] = None
    has_patient_portal: Optional[bool] = None
    has_insurance: Optional[bool] = None
    has_radiology: Optional[bool] = None
    has_surgical: Optional[bool] = None
    has_hr: Optional[bool] = None
    has_dietary: Optional[bool] = None
    has_ambulance: Optional[bool] = None
    has_compliance: Optional[bool] = None
    
    is_active: Optional[bool] = None

class SubscriptionStatusSchema(BaseModel):
    tenant_id: int
    plan_name: str
    plan_code: str
    subscription_status: SubscriptionStatus
    expires_at: Optional[datetime] = None
    enabled_features: List[str]
    max_users: int
    max_facilities: int
