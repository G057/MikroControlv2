import os
import re
from datetime import datetime


BACKUP_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "backups"))
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def validate_backup_schedule(days: str, time_str: str) -> tuple[str, str]:
    selected = []
    if days:
        for day in days.split(","):
            day = day.strip()
            if day not in {"0", "1", "2", "3", "4", "5", "6"} or day in selected:
                raise ValueError("Los días de backup deben ser valores únicos entre 0 (lunes) y 6 (domingo)")
            selected.append(day)
    if not _TIME_RE.fullmatch(time_str):
        raise ValueError("La hora de backup debe tener formato HH:MM")
    return ",".join(sorted(selected, key=int)), time_str


def should_run_backup_schedule(days: str, time_str: str, now: datetime | None = None) -> bool:
    try:
        selected, time_str = validate_backup_schedule(days, time_str)
    except ValueError:
        return False
    now = now or datetime.now()
    if selected and str(now.weekday()) not in selected:
        return False
    hour, minute = (int(part) for part in time_str.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return 0 <= (now - target).total_seconds() < 120
