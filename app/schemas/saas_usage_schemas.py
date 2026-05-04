from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class TenantUsageReadSchema(BaseModel):
    id: int
    tenant_id: int
    user_count: int
    storage_usage_bytes: int
    api_call_count: int
    transaction_count: int
    sms_count: int
    email_count: int
    login_count: int
    last_sync_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
