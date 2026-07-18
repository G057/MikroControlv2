"""Lógica compartida para gestión de usuarios: validación de contraseñas,
prevención de escalada de privilegios y borrado con limpieza de FKs.

Usado tanto por app/api/v1/users.py como por los endpoints de operadores en
app/api/v1/settings.py para mantener un único comportamiento.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

MIN_PASSWORD_LENGTH = 12


def validate_password_strength(password: str):
    """Valida la fortaleza mínima de una contraseña. Lanza HTTP 400 si es débil."""
    if password is None or len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres",
        )
    if password.strip() == "":
        raise HTTPException(status_code=400, detail="La contraseña no puede estar vacía")
    if not any(char.islower() for char in password):
        raise HTTPException(status_code=400, detail="La contraseña debe incluir una letra minúscula")
    if not any(char.isupper() for char in password):
        raise HTTPException(status_code=400, detail="La contraseña debe incluir una letra mayúscula")
    if not any(char.isdigit() for char in password):
        raise HTTPException(status_code=400, detail="La contraseña debe incluir un número")


def assert_can_assign_role(actor, target_role_name: str, db: Session):
    """Impide la escalada de privilegios al crear/editar usuarios.

    - El admin puede asignar cualquier rol.
    - Nadie que no sea admin puede asignar el rol 'admin'.
    - Un no-admin sólo puede asignar roles cuyo conjunto de permisos sea un
      subconjunto de los permisos que él mismo posee.
    """
    from app.core.security import get_user_permissions
    from app.models.role import Role

    if not target_role_name:
        raise HTTPException(status_code=400, detail="Rol requerido")

    role = db.query(Role).filter(Role.name == target_role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail=f"Rol inexistente: {target_role_name}")

    if actor.role == "admin":
        return
    if target_role_name == "admin":
        raise HTTPException(status_code=403, detail="No podés asignar el rol 'admin'")

    actor_perms = set(get_user_permissions(actor))
    target_perms = set(role.get_permissions())
    escalated = target_perms - actor_perms
    if escalated:
        raise HTTPException(
            status_code=403,
            detail="No podés asignar un rol con más permisos de los que tenés",
        )


def assert_not_self(actor, target_user, action: str = "modificar"):
    """Evita que un usuario se modifique/borre a sí mismo en operaciones sensibles."""
    if actor.id == target_user.id:
        raise HTTPException(status_code=400, detail=f"No podés {action} tu propia cuenta")


def delete_user_record(db: Session, user):
    """Borra un usuario liberando referencias para no violar claves foráneas."""
    from app.models.audit import AuditLog
    from app.models.dashboard_pref import DashboardPreference

    db.query(DashboardPreference).filter(DashboardPreference.user_id == user.id).delete()
    db.query(AuditLog).filter(AuditLog.user_id == user.id).update({AuditLog.user_id: None})
    db.delete(user)
