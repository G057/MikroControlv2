from sqlalchemy.orm import Session
from app.models.audit import AuditLog


def log_audit(
    db: Session,
    username: str,
    action: str,
    resource_type: str,
    resource_id: int = None,
    resource_name: str = None,
    details: dict = None,
    user_id: int = None,
    ip_address: str = None,
):
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(entry)
