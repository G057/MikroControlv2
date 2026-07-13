from pydantic import BaseModel, field_serializer
from typing import Optional, List
from datetime import datetime


def _utc_iso(v: Optional[datetime]) -> Optional[str]:
    if v is None:
        return None
    return v.isoformat() + "Z"


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#3B82F6"


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    color: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('created_at')
    def serialize_dt(self, v: Optional[datetime], _info):
        return _utc_iso(v)


class TagCreate(BaseModel):
    name: str
    color: str = "#10B981"


class TagResponse(BaseModel):
    id: int
    name: str
    color: str

    class Config:
        from_attributes = True


class RouterCreate(BaseModel):
    name: str
    hostname: str
    ip_address: str
    mac_address: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    access_method: str = "ip_public"
    access_port: int = 8728
    use_ssl: bool = False
    api_username: str = "admin"
    api_password: Optional[str] = None
    group_id: Optional[int] = None
    tag_ids: List[int] = []
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    notes: Optional[str] = None
    wg_address: Optional[str] = None
    wg_endpoint: Optional[str] = None
    wg_public_key: Optional[str] = None


class RouterUpdate(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    access_method: Optional[str] = None
    access_port: Optional[int] = None
    use_ssl: Optional[bool] = None
    api_username: Optional[str] = None
    api_password: Optional[str] = None
    group_id: Optional[int] = None
    tag_ids: Optional[List[int]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    notes: Optional[str] = None


class RouterResponse(BaseModel):
    id: int
    name: str
    hostname: str
    ip_address: str
    mac_address: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    routeros_version: Optional[str] = None
    identity: Optional[str] = None
    access_method: str
    access_port: int
    use_ssl: bool
    api_username: str
    group_id: Optional[int] = None
    tag_ids: list = []
    is_online: bool
    last_seen: Optional[datetime] = None
    cpu_usage: Optional[float] = None
    ram_usage: Optional[float] = None
    ram_total: Optional[float] = None
    temperature: Optional[float] = None
    voltage: Optional[float] = None
    uptime: Optional[str] = None
    hdd_free: Optional[float] = None
    hdd_total: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    notes: Optional[str] = None
    wg_address: Optional[str] = None
    wg_endpoint: Optional[str] = None
    wg_public_key: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('last_seen', 'created_at', 'updated_at')
    def serialize_dt(self, v: Optional[datetime], _info):
        return _utc_iso(v)
