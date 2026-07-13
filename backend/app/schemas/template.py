from pydantic import BaseModel, field_serializer
from typing import Optional
from datetime import datetime


def _utc_iso(v: Optional[datetime]) -> Optional[str]:
    if v is None:
        return None
    return v.isoformat() + "Z"


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    template_content: str
    variables: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    template_content: Optional[str] = None
    variables: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    category: str
    template_content: str
    variables: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('created_at', 'updated_at')
    def serialize_dt(self, v: Optional[datetime], _info):
        return _utc_iso(v)


class BackupResponse(BaseModel):
    id: int
    router_id: int
    backup_type: str
    filename: str
    file_size: Optional[int] = None
    routeros_version: Optional[str] = None
    notes: Optional[str] = None
    is_restored: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('created_at')
    def serialize_dt(self, v: Optional[datetime], _info):
        return _utc_iso(v)


class AlertRuleCreate(BaseModel):
    name: str
    alert_type: str
    threshold: Optional[float] = None
    severity: str = "warning"
    notify_telegram: bool = True
    notify_email: bool = False
    is_active: bool = True


class AlertRuleResponse(BaseModel):
    id: int
    name: str
    alert_type: str
    threshold: Optional[float] = None
    severity: str
    notify_telegram: bool
    notify_email: bool
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('created_at')
    def serialize_dt(self, v: Optional[datetime], _info):
        return _utc_iso(v)


class AlertResponse(BaseModel):
    id: int
    router_id: Optional[int] = None
    alert_type: str
    severity: str
    title: str
    message: Optional[str] = None
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_comment: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('created_at', 'resolved_at')
    def serialize_dt(self, v: Optional[datetime], _info):
        return _utc_iso(v)
