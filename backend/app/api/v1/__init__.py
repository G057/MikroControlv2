from fastapi import APIRouter
from app.api.v1 import auth, users, routers_crud, groups, inventory, templates, backups, alerts, dashboard, routeros, audit, events, settings, dashboard_pref, roles, traffic, logo, monitor, system_backup

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(users.router, prefix="/users", tags=["Usuarios"])
api_router.include_router(routers_crud.router, prefix="/routers", tags=["Routers"])
api_router.include_router(groups.router, prefix="/groups", tags=["Grupos"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventario"])
api_router.include_router(templates.router, prefix="/templates", tags=["Plantillas"])
api_router.include_router(backups.router, prefix="/backups", tags=["Backups"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alertas"])
api_router.include_router(events.router, prefix="/events", tags=["Eventos"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(routeros.router, prefix="/routeros", tags=["RouterOS"])
api_router.include_router(traffic.router, prefix="/traffic", tags=["Tráfico"])
api_router.include_router(audit.router, prefix="/audit", tags=["Auditoría"])
api_router.include_router(settings.router, prefix="/settings", tags=["Sistema"])
api_router.include_router(dashboard_pref.router, prefix="/dashboard-pref", tags=["Preferencias"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])
api_router.include_router(logo.router, prefix="/logo", tags=["Logo"])
api_router.include_router(monitor.router, prefix="/monitor", tags=["Monitor"])
api_router.include_router(system_backup.router, prefix="/system-backup", tags=["Backup Sistema"])
