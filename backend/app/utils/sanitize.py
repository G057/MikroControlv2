import re

def sanitize_error(msg: str, ip: str = "", hostname: str = "") -> str:
    """Reemplaza IP y hostname del router en mensajes de error."""
    s = msg
    if ip:
        s = s.replace(ip, "[OCULTO]")
    if hostname:
        s = s.replace(hostname, "[OCULTO]")
    s = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP]', s)
    return s
