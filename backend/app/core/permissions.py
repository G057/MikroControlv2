"""Catálogo central de permisos del sistema MikroControl.

Cada permiso es una clave 'modulo:accion'. El rol 'admin' es de sistema
y tiene acceso total; el resto de roles se definen por su lista de permisos.

La configuración del router se controla de forma granular:
  routers:cfg_<feature>_<op>
donde <feature> ∈ {addresses, dhcp, dns, routes, firewall, nat, wireguard}
y <op> ∈ {create, edit, delete}.
"""

# (clave, etiqueta, descripción, grupo)
PERMISSION_CATALOG = [
    # Dashboard
    ("dashboard:view", "Ver Dashboard", "Acceder al panel principal NOC", "Dashboard"),
    ("monitor:view", "Ver Monitor", "Acceder al panel de monitoreo en tiempo real", "Dashboard"),
    ("monitor:mute", "Silenciar Alertas", "Silenciar popup de alertas críticas/warning en monitoreo", "Dashboard"),
    # Routers
    ("routers:details", "Ver Datos del Cliente", "Ver datos sensibles del cliente (teléfono, email, dirección, notas)", "Routers"),
    ("routers:edit", "Gestionar Routers", "Crear, editar y eliminar routers en el sistema", "Routers"),
    ("routers:terminal", "Usar Terminal", "Ejecutar comandos RouterOS libres en el terminal", "Routers"),
    ("routers:bulk_command", "Comandos en Lote", "Ejecutar un comando en varios routers a la vez", "Routers"),
    ("routers:backup", "Gestionar Backups", "Crear y restaurar backups de routers", "Routers"),
    ("routers:ping", "Ping desde Router", "Ejecutar ping desde el router hacia una IP", "Routers"),
    ("routers:configure_wan", "Configurar WAN", "Configurar interfaz WAN (PPPoE/IP fija/DHCP)", "Routers"),
    # Vista por sección (granular): seleccionar qué puede ver cada rol
    ("routers:view_sensitive", "Ver Datos Técnicos", "Ver IP, hostname, identidad, MAC, serial y modelo del router", "Vista Router"),
    ("routers:view_interfaces", "Ver Interfaces", "Ver pestaña Interfaces del router", "Vista Router"),
    ("routers:view_traffic", "Ver Tráfico", "Ver gráfica histórica de tráfico por interfaz", "Vista Router"),
    ("routers:view_arp", "Ver ARP", "Ver tabla ARP del router", "Vista Router"),
    ("routers:view_dhcp", "Ver DHCP", "Ver leases DHCP (vista y configuración)", "Vista Router"),
    ("routers:view_pppoe", "Ver PPPoE", "Ver sesiones PPPoE", "Vista Router"),
    ("routers:view_firewall", "Ver Firewall", "Ver reglas de Firewall (filter y config)", "Vista Router"),
    ("routers:view_wireguard", "Ver WireGuard", "Ver interfaces y peers WireGuard", "Vista Router"),
    ("routers:view_addresses", "Ver Direcciones IP", "Ver direcciones IP en configuración", "Vista Router"),
    ("routers:view_dns", "Ver DNS", "Ver registros DNS estáticos", "Vista Router"),
    ("routers:view_routes", "Ver Rutas", "Ver rutas del router", "Vista Router"),
    ("routers:view_nat", "Ver NAT", "Ver reglas NAT en configuración", "Vista Router"),
]

# Configuración del router: por feature y por operación
_CFG_FEATURES = {
    "addresses": "Direcciones IP",
    "dhcp": "DHCP",
    "dns": "DNS Estático",
    "routes": "Rutas",
    "firewall": "Firewall Filter",
    "nat": "Firewall NAT",
    "wireguard": "WireGuard",
}
_CFG_OPS = {
    "create": "Crear",
    "edit": "Editar/Habilitar",
    "delete": "Eliminar",
}

for _feat, _feat_label in _CFG_FEATURES.items():
    for _op, _op_label in _CFG_OPS.items():
        PERMISSION_CATALOG.append((
            f"routers:cfg_{_feat}_{_op}",
            f"{_op_label} {_feat_label}",
            f"{_op_label} registros en {_feat_label} del router",
            "Config. Router",
        ))

PERMISSION_CATALOG += [
    # Grupos
    ("groups:view", "Ver Grupos", "Listar grupos de routers", "Grupos"),
    ("groups:edit", "Gestionar Grupos", "Crear, editar y eliminar grupos", "Grupos"),
    # Eventos
    ("events:view", "Ver Eventos", "Acceder a logs y eventos del sistema", "Eventos"),
    # Auditoría
    ("audit:view", "Ver Auditoría", "Ver log de auditoría y historial del router", "Auditoría"),
    # Usuarios
    ("users:view", "Ver Usuarios", "Listar operadores del sistema", "Usuarios"),
    ("users:edit", "Gestionar Usuarios", "Crear, editar y eliminar operadores", "Usuarios"),
    # Roles
    ("roles:manage", "Gestionar Roles", "Crear, editar y eliminar roles y sus permisos", "Usuarios"),
    # Configuración
    ("settings:view", "Ver Configuración", "Acceder a la configuración del sistema", "Configuración"),
    ("settings:edit", "Editar Configuración", "Modificar SMTP, Telegram, monitoreo, reloj, backup", "Configuración"),
]

ALL_PERMISSIONS = [p[0] for p in PERMISSION_CATALOG]

# Secciones de sólo lectura del router (para armar el conjunto "ver todo").
ROUTER_VIEW_SECTIONS = [
    "interfaces", "traffic", "arp", "dhcp", "pppoe", "firewall",
    "wireguard", "addresses", "dns", "routes", "nat",
]
# Permisos de vista por sección (sin datos técnicos sensibles).
ROUTER_VIEW_PERMS = [f"routers:view_{s}" for s in ROUTER_VIEW_SECTIONS]
# Conjunto equivalente al viejo "routers:view" (ver todas las secciones + datos técnicos).
ROUTER_VIEW_ALL = ROUTER_VIEW_PERMS + ["routers:view_sensitive"]

PERMISSION_GROUPS = {}
for _key, _label, _desc, _group in PERMISSION_CATALOG:
    PERMISSION_GROUPS.setdefault(_group, []).append((_key, _label, _desc))


# Roles legacy sembrados al iniciar (para no romper usuarios existentes).
# El admin es de sistema (no se puede borrar) y tiene todos los permisos.
_CFG_ALL = [f"routers:cfg_{f}_{op}" for f in _CFG_FEATURES for op in ("create", "edit", "delete")]

DEFAULT_ROLES = {
    "admin": {
        "description": "Administrador con acceso total al sistema",
        "is_system": True,
        "permissions": list(ALL_PERMISSIONS),
    },
    "supervisor": {
        "description": "Supervisa operaciones y auditores",
        "is_system": False,
        "permissions": [
            "dashboard:view", "routers:details", "routers:terminal",
            "routers:ping",
            "groups:view", "groups:edit", "events:view", "audit:view",
            "users:view", "settings:view",
        ] + ROUTER_VIEW_ALL,
    },
    "tecnico_n2": {
        "description": "Técnico nivel 2 con gestión completa de routers",
        "is_system": False,
        "permissions": [
            "dashboard:view", "routers:details", "routers:terminal",
            "routers:backup", "routers:ping",
            "groups:view", "groups:edit", "events:view",
        ] + ROUTER_VIEW_ALL + _CFG_ALL,
    },
    "tecnico_n1": {
        "description": "Técnico nivel 1 con acceso básico y terminal",
        "is_system": False,
        "permissions": [
            "dashboard:view", "routers:terminal", "routers:backup", "routers:ping",
            "groups:view", "events:view",
        ] + ROUTER_VIEW_ALL,
    },
    "tecnico_n3": {
        "description": "Técnico nivel 3: puede crear IP/DHCP pero no editar ni eliminar",
        "is_system": False,
        "permissions": [
            "dashboard:view", "routers:details", "routers:terminal",
            "routers:ping",
            "routers:cfg_addresses_create", "routers:cfg_dhcp_create", "events:view",
        ] + ROUTER_VIEW_ALL,
    },
    "auditor": {
        "description": "Solo lectura de auditoría y eventos",
        "is_system": False,
        "permissions": [
            "dashboard:view", "events:view", "audit:view",
        ] + ROUTER_VIEW_ALL,
    },
}
