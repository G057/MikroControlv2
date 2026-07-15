from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.database import engine, Base
import app.models.monitoring  # Register monitoring tables before create_all.
from app.api.v1 import api_router

settings = get_settings()

# Create all tables
Base.metadata.create_all(bind=engine)


def _migrate():
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    try:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "token_version" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
                print("Migración: columna 'token_version' agregada a users")
    except Exception as e:
        print(f"Error en migración (users): {e}")
    try:
        cols = {c["name"] for c in inspector.get_columns("roles")}
        with engine.begin() as conn:
            if "event_categories" not in cols:
                conn.execute(text("ALTER TABLE roles ADD COLUMN event_categories TEXT NOT NULL DEFAULT '[]'"))
                print("Migración: columna 'event_categories' agregada a roles")
            if "event_filters" not in cols:
                conn.execute(text("ALTER TABLE roles ADD COLUMN event_filters TEXT NOT NULL DEFAULT '[]'"))
                print("Migración: columna 'event_filters' agregada a roles")
            if "router_scope" not in cols:
                conn.execute(text("ALTER TABLE roles ADD COLUMN router_scope TEXT NOT NULL DEFAULT 'all'"))
                print("Migración: columna 'router_scope' agregada a roles")
            if "router_ids" not in cols:
                conn.execute(text("ALTER TABLE roles ADD COLUMN router_ids TEXT NOT NULL DEFAULT '[]'"))
                print("Migración: columna 'router_ids' agregada a roles")
            if "router_group_ids" not in cols:
                conn.execute(text("ALTER TABLE roles ADD COLUMN router_group_ids TEXT NOT NULL DEFAULT '[]'"))
                print("Migración: columna 'router_group_ids' agregada a roles")
    except Exception as e:
        print(f"Error en migración: {e}")
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP INDEX IF EXISTS ix_alerts_unique_active"))
    except Exception as e:
        print(f"Error creando índice único en alerts: {e}")
    try:
        event_columns = {c["name"] for c in inspector.get_columns("event_logs")}
        additions = {
            "source": "VARCHAR(30) NOT NULL DEFAULT 'legacy'",
            "event_type": "VARCHAR(80) NOT NULL DEFAULT 'unclassified'",
            "canonical_hash": "VARCHAR(64)",
            "deduplication_key": "VARCHAR(255)",
            "correlation_id": "VARCHAR(100)",
            "raw_message": "TEXT",
            "received_timestamp": "TIMESTAMP",
            "event_timestamp": "TIMESTAMP",
            "metadata_json": "JSON",
        }
        with engine.begin() as conn:
            for name, definition in additions.items():
                if name not in event_columns:
                    conn.execute(text(f"ALTER TABLE event_logs ADD COLUMN {name} {definition}"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_event_logs_canonical_hash ON event_logs(canonical_hash)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_logs_deduplication_key ON event_logs(deduplication_key)"))
    except Exception as e:
        print(f"Error migrando event_logs: {e}")
    try:
        alert_columns = {c["name"] for c in inspector.get_columns("alerts")}
        additions = {
            "opening_event_id": "INTEGER",
            "resolution_event_id": "INTEGER",
            "deduplication_key": "VARCHAR(255)",
            "occurrence_count": "INTEGER NOT NULL DEFAULT 1",
            "first_seen": "TIMESTAMP",
            "last_seen": "TIMESTAMP",
        }
        with engine.begin() as conn:
            for name, definition in additions.items():
                if name not in alert_columns:
                    conn.execute(text(f"ALTER TABLE alerts ADD COLUMN {name} {definition}"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_alerts_deduplication_key ON alerts(deduplication_key)"))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_alerts_unique_active_key "
                "ON alerts(router_id, deduplication_key) "
                "WHERE is_resolved = 0 AND deduplication_key IS NOT NULL"
            ))
    except Exception as e:
        print(f"Error migrando alerts: {e}")


# Migraciones incrementales para tablas ya existentes
_migrate()

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
