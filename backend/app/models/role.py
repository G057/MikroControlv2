from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime, timezone
from app.core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(200), default="")
    is_system = Column(Boolean, default=False)
    permissions = Column(Text, default="[]")  # JSON array de claves de permiso
    event_categories = Column(Text, default="[]")  # JSON array de categorías de eventos visibles
    event_filters = Column(Text, default="[]")  # Columna legacy retenida para compatibilidad de esquema.
    router_scope = Column(String(10), default="all")  # "all" | "selected"
    router_ids = Column(Text, default="[]")  # JSON array de ids de routers visibles (scope=selected)
    router_group_ids = Column(Text, default="[]")  # JSON array de ids de grupos visibles (scope=selected)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def get_permissions(self) -> list:
        import json
        try:
            data = json.loads(self.permissions or "[]")
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_permissions(self, perms: list):
        import json
        self.permissions = json.dumps(list(perms))

    def get_event_categories(self) -> list:
        import json
        try:
            data = json.loads(self.event_categories or "[]")
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_event_categories(self, cats: list):
        import json
        self.event_categories = json.dumps(list(cats))

    def get_router_scope(self) -> str:
        return self.router_scope if self.router_scope in ("all", "selected") else "selected"

    def set_router_scope(self, scope: str):
        if scope not in ("all", "selected"):
            raise ValueError("router_scope debe ser 'all' o 'selected'")
        self.router_scope = scope

    def get_router_ids(self) -> list:
        import json
        try:
            data = json.loads(self.router_ids or "[]")
            return [int(x) for x in data if str(x).isdigit()] if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_router_ids(self, ids: list):
        import json
        self.router_ids = json.dumps([int(x) for x in ids if str(x).isdigit()])

    def get_router_group_ids(self) -> list:
        import json
        try:
            data = json.loads(self.router_group_ids or "[]")
            return [int(x) for x in data if str(x).isdigit()] if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_router_group_ids(self, ids: list):
        import json
        self.router_group_ids = json.dumps([int(x) for x in ids if str(x).isdigit()])
