from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
from app.core.database import get_db
from app.core.security import get_current_user, require_permission, require_any_permission, get_user_permissions
from app.models.user import User
from app.models.router import Router
from pydantic import BaseModel
from typing import Optional, List
from app.utils.audit import log_audit
from app.core.router_access import require_visible_router

router = APIRouter()


class PingRequest(BaseModel):
    router_id: int
    target: str
    count: int = 4


class PingResponse(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None

# Mapa base de comandos RouterOS -> feature de configuración
_CMD_FEATURE = {
    "/ip/address": "addresses",
    "/ip/dhcp-server/lease": "dhcp",
    "/ip/dns/static": "dns",
    "/ip/route": "routes",
    "/ip/firewall/filter": "firewall",
    "/ip/firewall/nat": "nat",
    "/interface/wireguard": "wireguard",
}

# Mapea sección de configuración -> permiso de vista granular
_SECTION_VIEW = {
    "addresses": "routers:view_addresses",
    "firewall": "routers:view_firewall",
    "nat": "routers:view_nat",
    "dhcp": "routers:view_dhcp",
    "dns": "routers:view_dns",
    "routes": "routers:view_routes",
    "wireguard": "routers:view_wireguard",
}


def _required_perm_for_command(command: str):
    """Devuelve el permiso necesario para ejecutar el comando, o None si es de solo lectura.

    - Comandos de sección de configuración (add/set/enable/disable/remove) -> routers:cfg_<feature>_<op>
    - Comandos de solo lectura (print/get) -> None (cualquier usuario autenticado que vea el router)
    - Cualquier otro comando libre -> routers:terminal
    """
    if not command:
        return "routers:terminal"
    first = command.strip().split()[0].lower() if command.strip() else ""
    segments = first.split("/")
    if len(segments) < 2:
        return "routers:terminal"
    action = segments[-1]
    base = "/".join(segments[:-1])
    if base in _CMD_FEATURE:
        if action in ("add",):
            return f"routers:cfg_{_CMD_FEATURE[base]}_create"
        if action in ("set", "enable", "disable"):
            return f"routers:cfg_{_CMD_FEATURE[base]}_edit"
        if action in ("remove", "delete"):
            return f"routers:cfg_{_CMD_FEATURE[base]}_delete"
        # print/get y otros -> lectura
        return None
    return "routers:terminal"


def _action_for_command(command: str) -> str:
    cmd = (command or "").strip().lower()
    if '/remove' in cmd or cmd.endswith('/remove'):
        return "delete"
    if '/add' in cmd or cmd.endswith('/add'):
        return "create"
    if '/set' in cmd or cmd.endswith('/set') or '/enable' in cmd or '/disable' in cmd:
        return "update"
    return "command"


class CommandRequest(BaseModel):
    router_id: int
    command: str


class CommandResponse(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None


class BulkCommandRequest(BaseModel):
    router_ids: List[int]
    command: str


class BulkCommandItem(BaseModel):
    router_id: int
    router_name: str
    success: bool
    output: str
    error: Optional[str] = None


class BulkCommandResponse(BaseModel):
    results: List[BulkCommandItem]


class WanConfigureRequest(BaseModel):
    router_id: int
    wan_interface: str
    wan_type: str  # "pppoe", "static", "dhcp"
    pppoe_user: Optional[str] = None
    pppoe_password: Optional[str] = None
    ip_address: Optional[str] = None  # "192.168.1.2/24"
    gateway: Optional[str] = None
    dns_servers: Optional[str] = None  # "8.8.8.8,1.1.1.1"


class TestConnectionRequest(BaseModel):
    hostname: str
    port: int = 8728
    username: str = "admin"
    password: str = ""
    use_ssl: bool = False


@router.post("/test-connection")
def test_connection(
    data: TestConnectionRequest,
    current_user: User = Depends(get_current_user),
):
    from app.services.routeros_service import RouterOSConnection

    conn = RouterOSConnection(
        host=data.hostname,
        port=data.port,
        username=data.username,
        password=data.password,
        use_ssl=data.use_ssl,
        timeout=8,
    )
    try:
        conn.connect()
        identity = conn.command("/system/identity/print")
        resources = conn.command("/system/resource/print")
        conn.close()
        return {
            "success": True,
            "identity": identity[0].get("name", "") if identity else "",
            "version": resources[0].get("version", "") if resources else "",
        }
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


@router.post("/ping", response_model=PingResponse)
def ping_from_router(
    data: PingRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:ping")),
):
    r = require_visible_router(data.router_id, current_user, db)
    from app.services.routeros_service import _get_connection
    try:
        conn = _get_connection(r)
        conn.connect()
        conn._write_sentence("/ping", f"=address={data.target}", f"=count={data.count}")
        result = []
        while True:
            reply = conn._read_sentence()
            if not reply:
                break
            first = reply[0].decode(errors="replace")
            if first == "!done":
                break
            if first == "!trap":
                msg = conn._extract_trap_message(reply)
                conn.close()
                log_audit(db, current_user.username, "command", "router",
                          r.id, r.name, {"command": f"/ping {data.target} count={data.count}", "success": False},
                          current_user.id, req.client.host if req.client else None)
                db.commit()
                return PingResponse(success=False, output="", error=msg)
            if first == "!re":
                row = {}
                for word in reply[1:]:
                    decoded = word.decode(errors="replace")
                    if decoded.startswith("="):
                        parts = decoded[1:].split("=", 1)
                        if len(parts) == 2:
                            row[parts[0]] = parts[1]
                result.append(row)
        conn.close()
        output_lines = []
        for row in result:
            if row.get('status') == 'timeout':
                output_lines.append("  * timeout")
            else:
                seq = row.get('seq', '?')
                time_ms = row.get('time', '?')
                ttl = row.get('ttl', '?')
                host = row.get('host', '')
                output_lines.append(f"  seq={seq}  time={time_ms}ms  ttl={ttl}  host={host}")
        if not output_lines:
            output_lines.append(str(result))
        output = "\n".join(output_lines)
        sent = sum(1 for r in result if r.get('status') != 'timeout')
        total = len(result)
        output += f"\n\n--- {data.target} ping statistics ---\n{sent} packets transmitted, {sent} received, {total - sent} loss"
        log_audit(db, current_user.username, "command", "router",
                  r.id, r.name, {"command": f"/ping {data.target} count={data.count}", "success": True},
                  current_user.id, req.client.host if req.client else None)
        db.commit()
        return PingResponse(success=True, output=output)
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        log_audit(db, current_user.username, "command", "router",
                  r.id, r.name, {"command": f"/ping {data.target} count={data.count}", "success": False},
                  current_user.id, req.client.host if req.client else None)
        db.commit()
        return PingResponse(success=False, output="", error=str(e))


@router.post("/command", response_model=CommandResponse)
def execute_command(
    data: CommandRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = require_visible_router(data.router_id, current_user, db)

    required = _required_perm_for_command(data.command)
    if required:
        perms = get_user_permissions(current_user)
        if required not in perms and "routers:terminal" not in perms:
            raise HTTPException(status_code=403, detail=f"Sin permiso para ejecutar este comando ({required})")

    from app.services.routeros_service import execute_routeros_command
    result = execute_routeros_command(r, data.command)
    action = _action_for_command(data.command)
    log_audit(db, current_user.username, action, "router",
              r.id, r.name, {"command": data.command, "success": result.get("success", False)},
              current_user.id, req.client.host if req.client else None)
    db.commit()
    return CommandResponse(**result)


def _run_command_snapshot(snap: dict) -> dict:
    """Ejecuta el comando contra un router usando un snapshot de conexión
    (sin objetos ORM: corre en un hilo del pool)."""
    from app.services.routeros_service import RouterOSConnection
    conn = RouterOSConnection(
        host=snap["host"], port=snap["port"], username=snap["username"],
        password=snap["password"], use_ssl=snap["use_ssl"],
    )
    try:
        conn.connect()
        result = conn.command(snap["command"])
        conn.close()
        output = str(result) if result else "OK (sin datos de retorno)"
        return {"router_id": snap["id"], "router_name": snap["name"],
                "success": True, "output": output, "error": None}
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"router_id": snap["id"], "router_name": snap["name"],
                "success": False, "output": "", "error": str(e)}


@router.post("/bulk-command", response_model=BulkCommandResponse)
def execute_bulk_command(
    data: BulkCommandRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:bulk_command")),
):
    if not data.router_ids:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos un router")
    if len(data.router_ids) > 100:
        raise HTTPException(status_code=400, detail="Máximo 100 routers por ejecución")
    if not data.command.strip():
        raise HTTPException(status_code=400, detail="El comando no puede estar vacío")

    required = _required_perm_for_command(data.command)
    if required:
        perms = get_user_permissions(current_user)
        if required not in perms and "routers:terminal" not in perms:
            raise HTTPException(status_code=403, detail=f"Sin permiso para ejecutar este comando ({required})")

    from app.core.crypto import decrypt_secret
    snapshots = []
    results = []
    seen = set()
    for rid in data.router_ids:
        if rid in seen:
            continue
        seen.add(rid)
        try:
            r = require_visible_router(rid, current_user, db)
        except HTTPException:
            results.append({"router_id": rid, "router_name": f"#{rid}",
                            "success": False, "output": "",
                            "error": "Router no encontrado o fuera de tu alcance"})
            continue
        snapshots.append({
            "id": r.id, "name": r.name, "host": r.ip_address,
            "port": r.access_port, "username": r.api_username,
            "password": decrypt_secret(r.api_password_encrypted or ""),
            "use_ssl": r.use_ssl, "command": data.command,
        })

    if snapshots:
        max_workers = min(10, len(snapshots))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bulk-cmd") as ex:
            results.extend(ex.map(_run_command_snapshot, snapshots))

    action = _action_for_command(data.command)
    ip = req.client.host if req.client else None
    for res in results:
        if res["router_name"].startswith("#"):
            continue
        log_audit(db, current_user.username, action, "router",
                  res["router_id"], res["router_name"],
                  {"command": data.command, "success": res["success"], "bulk": True},
                  current_user.id, ip)
    db.commit()
    return BulkCommandResponse(results=[BulkCommandItem(**r) for r in results])


@router.get("/interfaces/{router_id}")
def get_interfaces(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:view_interfaces")),
):
    r = require_visible_router(router_id, current_user, db)
    from app.services.routeros_service import get_interfaces
    return get_interfaces(r)


@router.get("/resources/{router_id}")
def get_resources(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:view_interfaces")),
):
    r = require_visible_router(router_id, current_user, db)
    from app.services.routeros_service import get_system_resources
    return get_system_resources(r)


@router.get("/dhcp/{router_id}")
def get_dhcp_leases(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:view_dhcp")),
):
    r = require_visible_router(router_id, current_user, db)
    from app.services.routeros_service import get_dhcp_leases
    return get_dhcp_leases(r)


@router.get("/arp/{router_id}")
def get_arp_table(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:view_arp")),
):
    r = require_visible_router(router_id, current_user, db)
    from app.services.routeros_service import get_arp_entries
    return get_arp_entries(r)


@router.get("/pppoe/{router_id}")
def get_pppoe_users(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:view_pppoe")),
):
    r = require_visible_router(router_id, current_user, db)
    from app.services.routeros_service import get_pppoe_active
    return get_pppoe_active(r)


@router.get("/firewall/{router_id}")
def get_firewall_rules(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:view_firewall")),
):
    r = require_visible_router(router_id, current_user, db)
    from app.services.routeros_service import get_firewall_rules
    return get_firewall_rules(r)


@router.get("/wireguard/{router_id}")
def get_wireguard(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:view_wireguard")),
):
    r = require_visible_router(router_id, current_user, db)
    from app.services.routeros_service import get_wireguard_peers
    return get_wireguard_peers(r)


@router.get("/config/{router_id}/{section}")
def get_config_section(
    router_id: int,
    section: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = require_visible_router(router_id, current_user, db)

    SECTION_MAP = {
        "addresses": "/ip/address/print",
        "firewall": "/ip/firewall/filter/print",
        "nat": "/ip/firewall/nat/print",
        "dhcp": "/ip/dhcp-server/lease/print",
        "dns": "/ip/dns/static/print",
        "routes": "/ip/route/print",
        "wireguard": "/interface/wireguard/print",
    }

    if section not in SECTION_MAP:
        raise HTTPException(status_code=400, detail=f"Sección inválida: {section}")

    required_view = _SECTION_VIEW.get(section, f"routers:view_{section}")
    perms = get_user_permissions(current_user)
    feature = section  # la sección coincide con el feature de configuración
    can_read = (
        required_view in perms
        or "routers:terminal" in perms
        or f"routers:cfg_{feature}_create" in perms
        or f"routers:cfg_{feature}_edit" in perms
        or f"routers:cfg_{feature}_delete" in perms
    )
    if not can_read:
        raise HTTPException(status_code=403, detail=f"Sin permiso para ver esta sección ({required_view})")

    from app.services.routeros_service import _cmd
    try:
        return _cmd(r, SECTION_MAP[section])
    except Exception as e:
        return []


@router.get("/wan/{router_id}")
def get_wan_config(
    router_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:configure_wan")),
):
    r = require_visible_router(router_id, current_user, db)
    from app.services.routeros_service import get_wan_config as _get_wan
    return _get_wan(r)


@router.post("/wan/configure")
def configure_wan(
    data: WanConfigureRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("routers:configure_wan")),
):
    r = require_visible_router(data.router_id, current_user, db)
    from app.services.routeros_service import configure_wan as _cfg_wan
    result = _cfg_wan(r, data.wan_interface, data.wan_type,
                      pppoe_user=data.pppoe_user, pppoe_password=data.pppoe_password,
                      ip_address=data.ip_address, gateway=data.gateway,
                      dns_servers=data.dns_servers)
    if result.get("success"):
        log_audit(db, current_user.username, "update", "router",
                  r.id, r.name, {"action": "configure_wan", "wan_type": data.wan_type},
                  current_user.id, req.client.host if req.client else None)
        db.commit()
    return result
