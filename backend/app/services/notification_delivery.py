"""Best-effort asynchronous external delivery; event ingestion never waits for it."""
import logging
import threading
import json
from datetime import datetime, timezone
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.monitoring import Notification, NotificationDelivery

logger = logging.getLogger(__name__)
_thread = None
_stop_event = threading.Event()


def _direct_event_selected(notification, selected: set[str]) -> bool:
    if notification.notification_type == "app_login":
        return "app_login" in selected
    if notification.notification_type == "router_offline":
        return "router_offline" in selected
    return notification.severity in selected


def _deliver_pending():
    from app.api.v1.settings import _get_all
    import httpx
    db = SessionLocal()
    try:
        settings = _get_all(db)
        # Only claim notifications with no prior Telegram attempt. The previous
        # implementation repeatedly scanned the oldest delivered rows and could
        # starve all notifications after the first 100.
        pending = db.query(Notification).outerjoin(
            NotificationDelivery,
            and_(NotificationDelivery.notification_id == Notification.id,
                 NotificationDelivery.channel == "telegram"),
        ).filter(
            Notification.severity.in_(("critical", "warning", "recovery")),
            NotificationDelivery.id.is_(None),
            Notification.telegram_required == True,
            Notification.suppressed_at.is_(None),
            or_(Notification.available_after.is_(None), Notification.available_after <= datetime.now(timezone.utc)),
        ).order_by(Notification.id).limit(100).all()
        for notification in pending:
            delivery = NotificationDelivery(notification_id=notification.id, channel="telegram")
            db.add(delivery)
            try:
                # Commit the unique claim before contacting Telegram so another
                # backend process cannot send the same notification.
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            if settings.get("notify_telegram_enabled") != "true":
                delivery.success = False
                delivery.error = "telegram_disabled"
            elif notification.severity == "critical" and settings.get("notify_critical_alert", "true") != "true":
                delivery.error = "critical_disabled"
            elif notification.severity == "warning" and settings.get("notify_warning_alert", "true") != "true":
                delivery.error = "warning_disabled"
            elif notification.notification_type == "router_offline" and settings.get("notify_router_offline", "true") != "true":
                delivery.error = "router_offline_disabled"
            elif notification.notification_type in ("router_online", "auto_recovery") and settings.get("notify_router_online", "true") != "true":
                delivery.error = "router_online_disabled"
            token, chat_id = settings.get("telegram_bot_token", ""), settings.get("telegram_chat_id", "")
            if delivery.error:
                pass
            elif not token or not chat_id:
                delivery.error = "telegram_not_configured"
            else:
                try:
                    response = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                        "chat_id": chat_id, "text": f"<b>{notification.title}</b>\n{notification.message}", "parse_mode": "HTML"}, timeout=10)
                    delivery.response_code = response.status_code
                    delivery.success = response.is_success
                    if not delivery.success:
                        delivery.error = response.text[:500]
                except Exception as exc:
                    delivery.error = str(exc)[:500]
            db.commit()

        try:
            direct_types = set(json.loads(settings.get("telegram_direct_event_types", "[]")))
        except (TypeError, ValueError, json.JSONDecodeError):
            direct_types = set()
        direct_pending = db.query(Notification).outerjoin(
            NotificationDelivery,
            and_(NotificationDelivery.notification_id == Notification.id,
                 NotificationDelivery.channel == "telegram_direct"),
        ).filter(
            NotificationDelivery.id.is_(None),
            Notification.suppressed_at.is_(None),
            or_(Notification.available_after.is_(None), Notification.available_after <= datetime.now(timezone.utc)),
        ).order_by(Notification.id).limit(100).all()
        for notification in direct_pending:
            if not _direct_event_selected(notification, direct_types):
                continue
            delivery = NotificationDelivery(notification_id=notification.id, channel="telegram_direct")
            db.add(delivery)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            token, chat_id = settings.get("telegram_bot_token", ""), settings.get("telegram_direct_chat_id", "")
            if settings.get("telegram_direct_enabled") != "true":
                delivery.error = "telegram_direct_disabled"
            elif not token or not chat_id:
                delivery.error = "telegram_direct_not_configured"
            else:
                try:
                    response = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                        "chat_id": chat_id, "text": f"<b>{notification.title}</b>\n{notification.message}", "parse_mode": "HTML"}, timeout=10)
                    delivery.response_code = response.status_code
                    delivery.success = response.is_success
                    if not delivery.success:
                        delivery.error = response.text[:500]
                except Exception as exc:
                    delivery.error = str(exc)[:500]
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("Notification delivery cycle failed")
    finally:
        db.close()


def _run():
    while not _stop_event.wait(5):
        _deliver_pending()


def start_notification_delivery():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_run, daemon=True, name="notification-delivery")
    _thread.start()
