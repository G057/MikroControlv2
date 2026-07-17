from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.router_access import get_visible_router_ids
from app.models.user import User
from app.models.alert import Alert, AlertRule
from app.schemas.template import AlertRuleCreate, AlertRuleResponse, AlertResponse

router = APIRouter()


class ResolveRequest(BaseModel):
    comment: Optional[str] = None


@router.get("/unresolved-count")
def unresolved_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events:view")),
):
    visible_ids = get_visible_router_ids(current_user, db)
    count_q = db.query(func.count(Alert.id)).filter(Alert.is_resolved == False)
    sev_q = db.query(Alert.severity, func.count(Alert.id)).filter(Alert.is_resolved == False)
    if visible_ids is not None:
        count_q = count_q.filter((Alert.router_id.is_(None)) | (Alert.router_id.in_(visible_ids)))
        sev_q = sev_q.filter((Alert.router_id.is_(None)) | (Alert.router_id.in_(visible_ids)))
    count = count_q.scalar()
    by_severity = dict(sev_q.group_by(Alert.severity).all())
    return {
        "total": count,
        "critical": by_severity.get("critical", 0),
        "warning": by_severity.get("warning", 0),
        "info": by_severity.get("info", 0),
    }


@router.get("/", response_model=List[AlertResponse])
def list_alerts(
    is_resolved: bool = None,
    severity: str = None,
    alert_type: str = None,
    router_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events:view")),
):
    visible_ids = get_visible_router_ids(current_user, db)
    query = db.query(Alert)
    if is_resolved is not None:
        query = query.filter(Alert.is_resolved == is_resolved)
    if severity:
        query = query.filter(Alert.severity == severity)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    if router_id:
        query = query.filter(Alert.router_id == router_id)
    if visible_ids is not None:
        query = query.filter((Alert.router_id.is_(None)) | (Alert.router_id.in_(visible_ids)))
    return [AlertResponse.model_validate(a) for a in query.order_by(Alert.created_at.desc()).limit(500).all()]


@router.put("/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    body: ResolveRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events:view")),
):
    from datetime import datetime, timezone
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    visible_ids = get_visible_router_ids(current_user, db)
    if visible_ids is not None and alert.router_id is not None and alert.router_id not in visible_ids:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = current_user.username
    if body and body.comment:
        alert.resolution_comment = body.comment
    db.commit()
    return {"detail": "Alerta resuelta"}


@router.put("/resolve-all")
def resolve_all_alerts(
    body: ResolveRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events:view")),
):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    comment = (body.comment if body and body.comment else None) or "Resolución masiva"
    query = db.query(Alert).filter(Alert.is_resolved == False)
    visible_ids = get_visible_router_ids(current_user, db)
    if visible_ids is not None:
        query = query.filter((Alert.router_id.is_(None)) | (Alert.router_id.in_(visible_ids)))
    query.update({
        "is_resolved": True,
        "resolved_at": now,
        "resolved_by": current_user.username,
        "resolution_comment": comment,
    })
    db.commit()
    return {"detail": "Todas las alertas resueltas"}


@router.get("/rules/", response_model=List[AlertRuleResponse])
def list_rules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [AlertRuleResponse.model_validate(r) for r in db.query(AlertRule).all()]


@router.post("/rules/", response_model=AlertRuleResponse)
def create_rule(
    data: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    rule = AlertRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return AlertRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:edit")),
):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    db.delete(rule)
    db.commit()
    return {"detail": "Regla eliminada"}
