import json
import re
import fnmatch
from sqlalchemy.orm import Session
from app.models.settings import SystemSetting
from app.models.role import Role

# Orden estable de categorías de eventos (subsystemas de RouterOS).
EVENT_CATEGORIES = [
    {"key": "account", "label": "Cuenta / Login"},
    {"key": "system", "label": "Sistema"},
    {"key": "dhcp", "label": "DHCP"},
    {"key": "dns", "label": "DNS"},
    {"key": "firewall", "label": "Firewall"},
    {"key": "nat", "label": "NAT"},
    {"key": "pppoe", "label": "PPPoE"},
    {"key": "interface", "label": "Interfaces"},
    {"key": "wireless", "label": "Wireless"},
    {"key": "route", "label": "Rutas"},
    {"key": "script", "label": "Scripts"},
    {"key": "vpn", "label": "VPN (IPsec/L2TP/OVPN)"},
    {"key": "other", "label": "Otros"},
]

# Palabras clave por categoría (la primera coincidencia en 'topics' determina la categoría).
_CATEGORY_KEYWORDS = [
    ("account", "account"),
    ("dhcp", "dhcp"),
    ("dns", "dns"),
    ("firewall", "firewall"),
    ("nat", "nat"),
    ("pppoe", "pppoe"),
    ("wireless", "wireless"),
    ("interface", "interface"),
    ("route", "route"),
    ("script", "script"),
    ("vpn", ("ipsec", "l2tp", "ovpn", "sstp", "pptp")),
    ("system", "system"),
]


def classify_category(topics: str) -> str:
    """Mapea el campo 'topics' de un evento de RouterOS a una categoría conocida."""
    t = (topics or "").lower()
    for category, kw in _CATEGORY_KEYWORDS:
        if isinstance(kw, tuple):
            if any(k in t for k in kw):
                return category
        elif kw in t:
            return category
    return "other"


# Mapea el alert_type de una alerta de salud a una categoría de eventos.
_ALERT_TYPE_CATEGORY = {
    "interface_down": "interface",
    "high_cpu": "system",
    "low_disk": "system",
    "high_temp": "system",
    "backup_failed": "system",
    "router_online": "system",
    "router_offline": "system",
}


def classify_alert_category(alert_type: str) -> str:
    """Mapea el alert_type de una alerta de salud a una categoría conocida."""
    return _ALERT_TYPE_CATEGORY.get((alert_type or "").lower(), "system")


def load_exclusion_filters(db: Session) -> list:
    """Carga las reglas de exclusión de eventos desde system_settings."""
    row = db.query(SystemSetting).filter(SystemSetting.key == "event_exclusion_filters").first()
    if not row or not row.value:
        return []
    try:
        data = json.loads(row.value)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def event_matches_filter(message: str, topics: str, filt: dict) -> bool:
    """Evalúa una regla de exclusión contra un evento según su modo y campo."""
    pattern = (filt.get("pattern") or "").strip()
    if not pattern:
        return False
    mode = filt.get("mode", "contains")
    field = filt.get("field", "message")

    if field == "message":
        targets = [message or ""]
    elif field == "topics":
        targets = [topics or ""]
    else:
        targets = [message or "", topics or ""]

    for text in targets:
        text = text or ""
        try:
            if mode == "regex":
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            elif mode == "wildcard":
                rx = re.compile(re.escape(pattern).replace(r"\*", ".*").replace(r"\?", "."), re.IGNORECASE)
                if rx.search(text):
                    return True
            else:  # contains
                if pattern.lower() in text.lower():
                    return True
        except re.error:
            try:
                if fnmatch.fnmatch(text.lower(), pattern.lower()):
                    return True
            except Exception:
                return False
    return False


def is_event_excluded(message: str, topics: str, filters: list) -> bool:
    for f in filters:
        if f.get("enabled", True) and event_matches_filter(message, topics, f):
            return True
    return False


def load_role_event_categories(role_name: str, db: Session) -> list:
    """Devuelve las categorías de eventos que el rol puede ver. Vacío = ve todo."""
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        return []
    return role.get_event_categories()


def filter_rules_for_role(rules: list, role_name: str) -> list:
    """De una lista de reglas (cada una con campo opcional 'roles'), devuelve las que
    aplican al rol: las de 'roles' vacío (globales, para todos) y las que incluyen al rol."""
    out = []
    for r in rules:
        roles = r.get("roles") or []
        if not roles or role_name in roles:
            out.append(r)
    return out
