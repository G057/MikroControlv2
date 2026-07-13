from pydantic import BaseModel, field_serializer
from typing import Optional
from datetime import datetime


def _utc_iso(v: Optional[datetime]) -> Optional[str]:
    if v is None:
        return None
    return v.isoformat() + "Z"


class InventoryCreate(BaseModel):
    item_type: str
    name: str
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    client_name: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None


class InventoryUpdate(BaseModel):
    item_type: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    client_name: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class InventoryResponse(BaseModel):
    id: int
    item_type: str
    name: str
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    client_name: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('created_at', 'updated_at')
    def serialize_dt(self, v: Optional[datetime], _info):
        return _utc_iso(v)
