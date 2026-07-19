from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.v1 import api_router

settings = get_settings()

app = FastAPI(
    title="MikroControl",
    description="Sistema de gestión de routers MikroTik",
    version="2.0.7",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "MikroControl"}


@app.on_event("startup")
def on_startup():
    from app.core.database import SessionLocal
    from app.models.user import User
    from app.core.security import get_password_hash

    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        import os
        import secrets as _secrets
        admin_pw = os.environ.get("MK_ADMIN_PASSWORD") or _secrets.token_urlsafe(12)
        admin = User(
            username="admin",
            email="admin@mikrocontrol.local",
            full_name="Administrador",
            hashed_password=get_password_hash(admin_pw),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print("=" * 60)
        print("  Usuario admin creado")
        print(f"  Usuario:     admin")
        print(f"  Contraseña:  {admin_pw}")
        print("  GUARDÁ esta contraseña y cambiala tras el primer ingreso.")
        print("  (Podés fijarla con la variable de entorno MK_ADMIN_PASSWORD)")
        print("=" * 60)
    db.close()

    _seed_roles()
    _migrate_router_view_permission()
    _encrypt_router_passwords()
    _encrypt_settings_secrets()

    from app.services.health_check import start_health_checker
    start_health_checker()

    from app.services.syslog_receiver import start_syslog_receiver
    start_syslog_receiver()

    from app.services.notification_delivery import start_notification_delivery
    start_notification_delivery()

    from app.api.v1.system_backup import start_backup_scheduler
    start_backup_scheduler()

    from app.services.history_fetcher import start_history_fetcher
    start_history_fetcher()

    from app.services.router_backup_scheduler import start_router_backup_scheduler
    start_router_backup_scheduler()

    from app.services.traffic_sampler import start_traffic_sampler
    start_traffic_sampler()


@app.on_event("shutdown")
def on_shutdown():
    from app.services.routeros_service import close_shared_connections
    close_shared_connections()


def _encrypt_router_passwords():
    """Migra contraseñas de routers guardadas en texto plano a cifrado Fernet."""
    from app.core.database import SessionLocal
    from app.models.router import Router
    from app.core.crypto import is_encrypted, encrypt_secret

    db = SessionLocal()
    try:
        migrated = 0
        for r in db.query(Router).all():
            pwd = r.api_password_encrypted
            if pwd and not is_encrypted(pwd):
                r.api_password_encrypted = encrypt_secret(pwd)
                migrated += 1
        if migrated:
            db.commit()
            print(f"Migración: {migrated} contraseña(s) de router cifradas")
    except Exception as e:
        db.rollback()
        print(f"Error cifrando contraseñas de routers: {e}")
    finally:
        db.close()


def _encrypt_settings_secrets():
    """Migra secretos (SMTP/Telegram) guardados en texto plano a cifrado."""
    from app.core.database import SessionLocal
    from app.models.settings import SystemSetting
    from app.core.crypto import is_encrypted, encrypt_secret
    from app.api.v1.settings import SENSITIVE_KEYS

    db = SessionLocal()
    try:
        migrated = 0
        rows = db.query(SystemSetting).filter(SystemSetting.key.in_(SENSITIVE_KEYS)).all()
        for row in rows:
            if row.value and not is_encrypted(row.value):
                row.value = encrypt_secret(row.value)
                migrated += 1
        if migrated:
            db.commit()
            print(f"Migración: {migrated} secreto(s) de configuración cifrados")
    except Exception as e:
        db.rollback()
        print(f"Error cifrando secretos de configuración: {e}")
    finally:
        db.close()


def _migrate_router_view_permission():
    """Reemplaza el permiso maestro obsoleto 'routers:view' por el conjunto
    equivalente de permisos por sección + datos técnicos. Idempotente."""
    from app.core.database import SessionLocal
    from app.models.role import Role
    from app.core.permissions import ROUTER_VIEW_ALL

    db = SessionLocal()
    try:
        changed = 0
        for role in db.query(Role).all():
            perms = role.get_permissions()
            if "routers:view" not in perms:
                continue
            new_perms = [p for p in perms if p != "routers:view"]
            for p in ROUTER_VIEW_ALL:
                if p not in new_perms:
                    new_perms.append(p)
            role.set_permissions(new_perms)
            changed += 1
        if changed:
            db.commit()
            print(f"Migración: 'routers:view' reemplazado por permisos por sección en {changed} rol(es)")
    except Exception as e:
        db.rollback()
        print(f"Error migrando routers:view: {e}")
    finally:
        db.close()


def _seed_roles():
    from app.core.database import SessionLocal
    from app.models.role import Role
    from app.core.permissions import DEFAULT_ROLES

    db = SessionLocal()
    try:
        for name, data in DEFAULT_ROLES.items():
            existing = db.query(Role).filter(Role.name == name).first()
            if existing:
                # Solo el admin se re-sincroniza siempre (para recibir permisos
                # nuevos). Los demás roles se respetan tal como el usuario los
                # editó y NO se sobrescriben en cada arranque.
                if name == "admin":
                    existing.set_permissions(data["permissions"])
                    existing.description = data["description"]
                    existing.is_system = data["is_system"]
                continue
            role = Role(
                name=name,
                description=data["description"],
                is_system=data["is_system"],
            )
            role.set_permissions(data["permissions"])
            db.add(role)
        db.commit()
        print("Roles del sistema sembrados correctamente")
    except Exception as e:
        db.rollback()
        print(f"Error sembrando roles: {e}")
    finally:
        db.close()
