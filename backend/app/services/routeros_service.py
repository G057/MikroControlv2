import socket
import struct
import ssl as ssl_module
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _get_connection(router):
    from app.core.crypto import decrypt_secret
    return RouterOSConnection(
        host=router.ip_address,
        port=router.access_port,
        username=router.api_username,
        password=decrypt_secret(router.api_password_encrypted or ""),
        use_ssl=router.use_ssl,
    )


class RouterOSConnection:
    """Conexión TCP socket a MikroTik RouterOS v7 API."""

    def __init__(self, host, port=8728, username="admin", password="", use_ssl=False, timeout=10.0, verify_tls=None):
        from app.core.config import get_settings
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.timeout = timeout
        self.verify_tls = get_settings().ROUTEROS_TLS_VERIFY if verify_tls is None else verify_tls
        self.sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def _cleanup_socket(self, raw_sock=None):
        for s in (self.sock, raw_sock):
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        self.sock = None

    def connect(self) -> bool:
        raw_sock = None
        try:
            raw_sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            if self.use_ssl:
                if self.verify_tls:
                    ctx = ssl_module.create_default_context()
                else:
                    logger.warning("La verificación TLS está deshabilitada para RouterOS API-SSL")
                    ctx = ssl_module.SSLContext(ssl_module.PROTOCOL_TLS_CLIENT)
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl_module.CERT_NONE
                self.sock = ctx.wrap_socket(raw_sock, server_hostname=self.host)
            else:
                self.sock = raw_sock
            self._login()
            return True
        except socket.timeout:
            self._cleanup_socket(raw_sock)
            raise Exception("Timeout: el router no responde (verificar IP/puerto/SSL)")
        except ConnectionRefusedError:
            self._cleanup_socket(raw_sock)
            raise Exception("Conexión rechazada — el servicio API está deshabilitado o el puerto es incorrecto")
        except ssl_module.SSLCertVerificationError:
            self._cleanup_socket(raw_sock)
            raise Exception("Certificado SSL no confiable o no coincide con el host del router")
        except ssl_module.SSLError:
            self._cleanup_socket(raw_sock)
            raise Exception("Error SSL — Verificá que API-SSL esté habilitado en el router")
        except OSError:
            self._cleanup_socket(raw_sock)
            raise Exception("Error de conexión — verificá que el router esté accesible")
        except Exception:
            self._cleanup_socket(raw_sock)
            raise

    def _login(self):
        self._write_sentence("/login", f"=name={self.username}", f"=password={self.password}")
        reply = self._read_sentence()
        if not reply:
            raise Exception("Respuesta vacía del router")
        first = reply[0].decode(errors="replace")
        if first == "!trap":
            msg = self._extract_trap_message(reply)
            raise Exception(f"Credenciales incorrectas: {msg}")
        if first not in ("!done",):
            raise Exception(f"Respuesta inesperada: {first}")

    def _extract_trap_message(self, reply) -> str:
        for word in reply:
            decoded = word.decode(errors="replace")
            if decoded.startswith("=message="):
                return decoded[9:]
        return "credenciales incorrectas"

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _write_sentence(self, *words):
        data = b""
        for word in words:
            encoded = word.encode()
            data += self._encode_length(len(encoded)) + encoded
        data += b"\x00"
        self.sock.sendall(data)

    def _encode_length(self, length):
        if length < 0x80:
            return struct.pack("!B", length)
        elif length < 0x4000:
            return struct.pack("!H", length | 0x8000)
        elif length < 0x200000:
            return struct.pack("!I", length | 0xC00000)
        return struct.pack("!I", length | 0xE0000000)

    def _read_sentence(self):
        words = []
        while True:
            length = self._read_word_length()
            if length == 0:
                break
            word = b""
            remaining = length
            while remaining > 0:
                chunk = self.sock.recv(min(remaining, 4096))
                if not chunk:
                    raise Exception("Conexión cerrada por el router")
                word += chunk
                remaining -= len(chunk)
            words.append(word)
        return words

    def _read_word_length(self):
        first = self._recv_exact(1)
        byte = first[0]
        if byte == 0:
            return 0
        if byte < 0x80:
            return byte
        if byte < 0xC0:
            second = self._recv_exact(1)[0]
            return ((byte & 0x3F) << 8) | second
        if byte < 0xE0:
            data = self._recv_exact(2)
            return ((byte & 0x1F) << 16) | (data[0] << 8) | data[1]
        data = self._recv_exact(3)
        return ((byte & 0x0F) << 24) | (data[0] << 16) | (data[1] << 8) | data[2]

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise Exception("Conexión cerrada")
            data += chunk
        return data

    @staticmethod
    def _to_api_format(cmd: str) -> list:
        tokens = []
        current = ""
        in_quotes = False
        for ch in cmd:
            if ch == '"':
                in_quotes = not in_quotes
                current += ch
            elif ch == ' ' and not in_quotes:
                if current:
                    tokens.append(current)
                    current = ""
            else:
                current += ch
        if current:
            tokens.append(current)

        if len(tokens) <= 1:
            return tokens

        first = tokens[0]
        if first.count('/') >= 2:
            return tokens

        ACTIONS = {'add', 'set', 'remove', 'enable', 'disable', 'print'}
        action_idx = -1
        for i, t in enumerate(tokens):
            if t in ACTIONS:
                action_idx = i
                break

        if action_idx < 0:
            return ["/".join(tokens)]

        path = "/".join(tokens[:action_idx + 1])
        params = tokens[action_idx + 1:]
        return [path] + params

    def command(self, cmd):
        self._write_sentence(*self._to_api_format(cmd))
        result = []
        current = {}
        trap_msg = None
        while True:
            reply = self._read_sentence()
            if not reply:
                break
            for word in reply:
                decoded = word.decode(errors="replace")
                if decoded == "!trap":
                    trap_msg = self._extract_trap_message(reply)
                if decoded == "!re":
                    if current:
                        result.append(current)
                    current = {}
                    continue
                if decoded in ("!done", "!empty"):
                    if current:
                        result.append(current)
                        current = {}
                    if trap_msg:
                        raise Exception(f"Error del router: {trap_msg}")
                    return result
                if decoded.startswith("="):
                    key, _, value = decoded[1:].partition("=")
                    current[key] = value
        if trap_msg:
            raise Exception(f"Error del router: {trap_msg}")
        if current:
            result.append(current)
        return result

    def command_raw(self, cmd):
        self._write_sentence(*self._to_api_format(cmd))
        all_words = []
        while True:
            reply = self._read_sentence()
            all_words.extend(reply)
            if any(word.decode(errors="replace") in ("!done", "!empty") for word in reply):
                break
        return all_words


def check_router_status(router) -> dict:
    try:
        conn = _get_connection(router)
        conn.connect()
        resources = conn.command("/system/resource/print")
        identity = conn.command("/system/identity/print")
        interfaces = conn.command("/interface/print")
        conn.close()

        if resources:
            r = resources[0]
            router.is_online = True
            router.last_seen = datetime.now(timezone.utc)

            try:
                router.cpu_usage = float(r.get("cpu-load", 0))
            except (ValueError, TypeError):
                router.cpu_usage = 0

            try:
                total_mem = r.get("total-memory", "0")
                free_mem = r.get("free-memory", "0")
                total_mb = _parse_memory_mb(total_mem)
                free_mb = _parse_memory_mb(free_mem)
                if total_mb > 0:
                    router.ram_usage = round(((total_mb - free_mb) / total_mb) * 100, 1)
                    router.ram_total = total_mb
                else:
                    router.ram_usage = 0
            except Exception:
                router.ram_usage = 0

            router.uptime = r.get("uptime", "")
            router.routeros_version = r.get("version", "")
            router.identity = identity[0].get("name", "") if identity else ""

            return {"online": True, "resources": r, "identity": identity, "interfaces": interfaces}

        router.is_online = False
        router.last_seen = datetime.now(timezone.utc)
        return {"online": False}
    except Exception as e:
        logger.warning(f"Check failed for {router.name}: {e}")
        router.is_online = False
        router.last_seen = datetime.now(timezone.utc)
        return {"online": False, "error": str(e)}


def _parse_memory_mb(value):
    value = str(value).strip()
    if value.endswith("GiB"):
        return float(value.replace("GiB", "").strip()) * 1024
    elif value.endswith("MiB"):
        return float(value.replace("MiB", "").strip())
    elif value.endswith("KiB"):
        return float(value.replace("KiB", "").strip()) / 1024
    try:
        v = float(value)
        if v > 1000000:
            return v / (1024 * 1024)
        return v
    except ValueError:
        return 0


def _cmd(router, cmd):
    conn = _get_connection(router)
    conn.connect()
    result = conn.command(cmd)
    conn.close()
    return result


def get_system_resources(router):
    try:
        result = _cmd(router, "/system/resource/print")
        return result[0] if isinstance(result, list) and result else result
    except Exception as e:
        return {"error": str(e)}


def get_interfaces(router):
    try:
        return _cmd(router, "/interface/print")
    except Exception as e:
        return {"error": str(e)}


def get_dhcp_leases(router):
    try:
        return _cmd(router, "/ip/dhcp-server/lease/print")
    except Exception as e:
        return {"error": str(e)}


def get_arp_entries(router):
    try:
        return _cmd(router, "/ip/arp/print")
    except Exception as e:
        return {"error": str(e)}


def get_pppoe_active(router):
    try:
        return _cmd(router, "/ppp/active/print")
    except Exception as e:
        return {"error": str(e)}


def get_firewall_rules(router):
    try:
        conn = _get_connection(router)
        conn.connect()
        filter_rules = conn.command("/ip/firewall/filter/print")
        nat_rules = conn.command("/ip/firewall/nat/print")
        mangle_rules = conn.command("/ip/firewall/mangle/print")
        conn.close()
        return {"filter": filter_rules, "nat": nat_rules, "mangle": mangle_rules}
    except Exception as e:
        return {"error": str(e)}


def get_wireguard_peers(router):
    try:
        conn = _get_connection(router)
        conn.connect()
        interfaces = conn.command("/interface/wireguard/print")
        peers = conn.command("/interface/wireguard/peers/print")
        conn.close()
        return {"interfaces": interfaces, "peers": peers}
    except Exception as e:
        return {"error": str(e)}


def execute_routeros_command(router, command):
    try:
        conn = _get_connection(router)
        conn.connect()
        result = conn.command(command)
        conn.close()
        output = str(result) if result else "OK (sin datos de retorno)"
        return {"success": True, "output": output}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


SKIP_PROPS = {
    ".id", ".nextid",
    "rx-byte", "tx-byte", "rx-packet", "tx-packet", "rx-drop", "tx-drop",
    "tx-queue-drop", "rx-error", "tx-error",
    "fp-rx-byte", "fp-tx-byte", "fp-rx-packet", "fp-tx-packet",
    "link-downs", "last-link-up-time", "last-link-down-time",
    "last-seen", "expires-after", "age",
    "active-address", "active-mac-address", "active-client-id", "active-server",
    "actual-interface", "actual-mtu", "actual-mac-address",
    "status", "running", "inactive",
    "write-sect-since-reboot", "write-sect-total", "bad-blocks",
    "uptime", "version", "build-time", "factory-software",
    "free-memory", "total-memory", "free-hdd-space", "total-hdd-space",
    "cpu", "cpu-count", "cpu-frequency", "cpu-load",
    "architecture-name", "board-name", "platform",
    "last-logged-in", "last-caller-id", "last-disconnect-reason",
    "run-count", "last-ran",
    "src-mac-address", "multicast-router",
    "hw-offload",
    "cache-used",
    "debug-info",
    "port-number", "role", "edge-port", "edge-port-discovery",
    "point-to-point-port", "external-fdb-status", "sending-rstp",
    "learning", "forwarding", "root-path-cost",
    "designated-bridge", "designated-cost", "designated-port-number",
    "hw-offload-group",
    "bytes", "packets",
    "public-address", "dns-name", "back-to-home-vpn", "update-time",
    "dynamic-servers",
    "arp-timeout", "radio-mac", "master", "bound",
    "default-name", "type",
    "dynamic", "invalid", "builtin",
    "last-logged-out",
    "log-prefix",
    "service-name", "ac-name",
    "caller-id", "ipv6-routes",
    "address-list", "on-up", "on-down",
    "skin",
}

RSC_SECTIONS = [
    {
        "api": "/system/identity/print",
        "path": "/system identity",
        "mode": "set",
    },
    {
        "api": "/system/clock/print",
        "path": "/system clock",
        "mode": "set",
    },
    {
        "api": "/system/note/print",
        "path": "/system note",
        "mode": "set",
    },
    {
        "api": "/interface/print",
        "path": "/interface",
        "mode": "add",
        "skip_types": {"ether", "lag", "bridge", "wifi", "vlan", "bonding", "lte", "pppoe-out"},
        "filter_field": "type",
    },
    {
        "api": "/interface/print",
        "path": "/interface bridge",
        "mode": "add",
        "only_type": "bridge",
    },
    {
        "api": "/interface/wifi/print",
        "path": "/interface wifi",
        "mode": "set",
        "use_default_name": True,
    },
    {
        "api": "/interface/bridge/port/print",
        "path": "/interface bridge port",
        "mode": "add",
    },
    {
        "api": "/interface/list/print",
        "path": "/interface list",
        "mode": "add",
        "skip_names": {"all"},
    },
    {
        "api": "/interface/list/member/print",
        "path": "/interface list member",
        "mode": "add",
    },
    {
        "api": "/interface/pppoe-client/print",
        "path": "/interface pppoe-client",
        "mode": "add",
    },
    {
        "api": "/interface/l2tp-server/print",
        "path": "/interface l2tp-server server",
        "mode": "set",
    },
    {
        "api": "/interface/wireguard/print",
        "path": "/interface wireguard",
        "mode": "add",
    },
    {
        "api": "/interface/wireguard/peers/print",
        "path": "/interface wireguard peers",
        "mode": "add",
    },
    {
        "api": "/ip/pool/print",
        "path": "/ip pool",
        "mode": "add",
    },
    {
        "api": "/ip/address/print",
        "path": "/ip address",
        "mode": "add",
    },
    {
        "api": "/ip/cloud/print",
        "path": "/ip cloud",
        "mode": "set",
    },
    {
        "api": "/ip/dhcp-client/print",
        "path": "/ip dhcp-client",
        "mode": "add",
    },
    {
        "api": "/ip/dhcp-server/print",
        "path": "/ip dhcp-server",
        "mode": "add",
    },
    {
        "api": "/ip/dhcp-server/network/print",
        "path": "/ip dhcp-server network",
        "mode": "add",
    },
    {
        "api": "/ip/dns/print",
        "path": "/ip dns",
        "mode": "set",
    },
    {
        "api": "/ip/dns/static/print",
        "path": "/ip dns static",
        "mode": "add",
    },
    {
        "api": "/ip/route/print",
        "path": "/ip route",
        "mode": "add",
        "skip_dynamic": True,
    },
    {
        "api": "/ip/firewall/filter/print",
        "path": "/ip firewall filter",
        "mode": "add",
    },
    {
        "api": "/ip/firewall/nat/print",
        "path": "/ip firewall nat",
        "mode": "add",
    },
    {
        "api": "/ip/service/print",
        "path": "/ip service",
        "mode": "set",
    },
    {
        "api": "/ip/neighbor/discovery-settings/print",
        "path": "/ip neighbor discovery-settings",
        "mode": "set",
    },
    {
        "api": "/ppp/secret/print",
        "path": "/ppp secret",
        "mode": "add",
    },
    {
        "api": "/ppp/profile/print",
        "path": "/ppp profile",
        "mode": "add",
        "skip_field_values": {"default": "true"},
    },
    {
        "api": "/user/group/print",
        "path": "/user group",
        "mode": "add",
    },
    {
        "api": "/user/print",
        "path": "/user",
        "mode": "add",
    },
    {
        "api": "/system/scheduler/print",
        "path": "/system scheduler",
        "mode": "add",
    },
    {
        "api": "/tool/mac-server/print",
        "path": "/tool mac-server",
        "mode": "set",
    },
    {
        "api": "/tool/mac-server/mac-winbox/print",
        "path": "/tool mac-server mac-winbox",
        "mode": "set",
    },
    {
        "api": "/queue/simple/print",
        "path": "/queue simple",
        "mode": "add",
    },
]


def _format_rsc_value(val):
    val = str(val)
    if val == "" or val == "true" or val == "false":
        return val
    if any(c in val for c in " \t\n\"'"):
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return val


def _row_to_rsc(mode, row, use_default_name=False):
    props = []
    for k, v in row.items():
        if k in SKIP_PROPS:
            continue
        if k == ".id":
            continue
        if k == "name" and use_default_name:
            continue
        val = _format_rsc_value(v)
        if k == "comment":
            props.append(f"comment={val}")
        else:
            props.append(f"{k}={val}")

    if mode == "set" and use_default_name:
        default_name = row.get("default-name", "")
        if default_name:
            return f"set [ find default-name={default_name} ] " + " ".join(props)

    if mode == "set":
        return "set " + " ".join(props)

    return "add " + " ".join(props)


def _write_rsc_line(f, line, indent=""):
    MAX_WIDTH = 80
    if len(indent + line) <= MAX_WIDTH:
        f.write(indent + line + "\n")
        return
    parts = line.split(" ")
    current = indent
    first = True
    for part in parts:
        if not first and len(current) + len(part) + 1 > MAX_WIDTH:
            f.write(current + " \\\n")
            current = indent + "    " + part
        else:
            if first:
                current += part
                first = False
            else:
                current += " " + part
    f.write(current + "\n")


def create_router_backup(router, backup_type="binary"):
    try:
        conn = _get_connection(router)
        conn.connect()

        identity = ""
        try:
            id_result = conn.command("/system/identity/print")
            if id_result:
                identity = id_result[0].get("name", "")
        except Exception:
            pass

        version = router.routeros_version or ""
        board = ""
        serial = ""
        try:
            res = conn.command("/system/resource/print")
            if res:
                version = res[0].get("version", version)
                board = res[0].get("board-name", "")
        except Exception:
            pass

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        all_rsc_lines = []
        for section in RSC_SECTIONS:
            api_path = section["api"]
            rsc_path = section["path"]
            mode = section["mode"]

            try:
                rows = conn.command(api_path)
            except Exception:
                continue

            if not rows:
                continue

            filtered = []
            for row in rows:
                if row.get("dynamic") == "true" and section.get("skip_dynamic", False):
                    continue
                if row.get("dynamic") == "true":
                    continue
                if "skip_types" in section and row.get(section.get("filter_field", "")) in section["skip_types"]:
                    continue
                if "only_type" in section and row.get("type") != section["only_type"]:
                    continue
                if "skip_names" in section and row.get("name") in section["skip_names"]:
                    continue
                if row.get("builtin") == "true":
                    continue
                skip_fv = section.get("skip_field_values", {})
                if any(row.get(fk) == fv for fk, fv in skip_fv.items()):
                    continue
                filtered.append(row)

            if not filtered:
                continue

            all_rsc_lines.append(("", rsc_path))
            for row in filtered:
                line = _row_to_rsc(mode, row, section.get("use_default_name", False))
                all_rsc_lines.append(("line", line))

        conn.close()

        ext = "rsc" if backup_type != "binary" else "backup"
        filename = f"{router.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

        from app.core.backup_utils import BACKUP_DIR
        backup_dir = BACKUP_DIR
        os.makedirs(backup_dir, exist_ok=True)
        filepath = os.path.join(backup_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {timestamp} by RouterOS {version}\n")
            if board:
                f.write(f"# software id = \n#\n")
                f.write(f"# model = {board}\n")
            f.write(f"# serial number = {serial}\n" if serial else "")
            f.write("\n")

            for kind, content in all_rsc_lines:
                if kind == "":
                    f.write(f"\n{content}\n")
                else:
                    _write_rsc_line(f, content)

        from app.core.database import SessionLocal
        from app.models.backup import Backup

        db = SessionLocal()
        backup = Backup(
            router_id=router.id,
            backup_type=backup_type,
            filename=filename,
            file_path=filepath,
            routeros_version=version,
        )
        db.add(backup)
        db.commit()
        db.close()

        return {"success": True, "filename": filename}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_wan_interfaces(router) -> list:
    conn = _get_connection(router)
    conn.connect()
    try:
        interfaces = conn.command("/interface/print")
        conn.close()
        return [{"name": i.get("name"), "type": i.get("type"), "running": i.get("running") == "true"}
                for i in interfaces if i.get("type") in ("ether", "wlan", "wifi", "bridge")]
    except Exception as e:
        try: conn.close()
        except: pass
        raise


def configure_persistent_logging(router, syslog_host: str, syslog_port: int, ntp_primary: str,
                                 ntp_secondary: str, time_zone: str) -> dict:
    """Configures MikroControl's remote Syslog, durable logs, NTP and timezone."""
    desired_topics = ("system,error,critical", "ppp,info", "interface,info", "account,warning")
    syslog_action = "mikrocontrol-syslog"
    conn = _get_connection(router)
    conn.connect()
    try:
        actions = conn.command("/system/logging/action/print")
        if not any(action.get("name") == "disk" for action in actions):
            return {"success": False, "error": "El router no tiene la acción de logging 'disk'"}

        action = next((item for item in actions if item.get("name") == syslog_action), None)
        remote_base = f"=target=remote =remote={syslog_host} =remote-port={syslog_port}"

        def configure_remote_action(log_format):
            config = f"{remote_base} =remote-log-format={log_format}"
            if action and action.get(".id"):
                conn.command(f"/system/logging/action/set =.id={action['.id']} {config}")
                return False
            conn.command(f"/system/logging/action/add =name={syslog_action} {config}")
            return True

        try:
            action_created = configure_remote_action("bsd-syslog")
            remote_log_format = "bsd-syslog"
        except Exception as exc:
            if "remote-log-format" not in str(exc).lower():
                raise
            # Older RouterOS releases only accept the default remote format.
            actions = conn.command("/system/logging/action/print")
            action = next((item for item in actions if item.get("name") == syslog_action), None)
            action_created = configure_remote_action("default")
            remote_log_format = "default"

        rules = conn.command("/system/logging/print")
        existing_disk = {tuple(sorted(filter(None, rule.get("topics", "").split(",")))) for rule in rules if rule.get("action") == "disk"}
        existing_remote = {tuple(sorted(filter(None, rule.get("topics", "").split(",")))) for rule in rules if rule.get("action") == syslog_action}
        disk_created, syslog_created = [], []
        for topics in desired_topics:
            normalized = tuple(sorted(topics.split(",")))
            if normalized not in existing_disk:
                conn.command(f'/system/logging/add =topics={topics} =action=disk =comment="MikroControl persistent logs"')
                disk_created.append(topics)
            if normalized not in existing_remote:
                conn.command(f'/system/logging/add =topics={topics} =action={syslog_action} =comment="MikroControl Syslog"')
                syslog_created.append(topics)
        conn.command(f"/system/clock/set =time-zone-autodetect=no =time-zone-name={time_zone}")
        try:
            conn.command(f"/system/ntp/client/set =enabled=yes =servers={ntp_primary},{ntp_secondary}")
            ntp_mode = "v7"
        except Exception:
            # RouterOS v6 does not support the v7 `servers` property.
            conn.command(f"/system/ntp/client/set =enabled=yes =primary-ntp={ntp_primary} =secondary-ntp={ntp_secondary}")
            ntp_mode = "legacy"
        return {"success": True, "disk_created": disk_created, "syslog_created": syslog_created,
                "action_created": action_created, "configured": list(desired_topics), "ntp_mode": ntp_mode,
                "remote_log_format": remote_log_format}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


def get_wan_config(router) -> dict:
    conn = _get_connection(router)
    conn.connect()
    try:
        interfaces = conn.command("/interface/print")
        addresses = conn.command("/ip/address/print")
        dhcp_clients = conn.command("/ip/dhcp-client/print")
        pppoe_clients = conn.command("/interface/pppoe-client/print")
        dns = conn.command("/ip/dns/print")
        routes = conn.command("/ip/route/print")
        conn.close()

        wan_ifaces = [{"name": i.get("name"), "type": i.get("type"), "running": i.get("running") == "true"}
                      for i in interfaces if i.get("type") in ("ether", "wlan", "wifi", "bridge")]

        return {
            "interfaces": wan_ifaces,
            "addresses": [{"interface": a.get("interface"), "address": a.get("address"), "network": a.get("network")} for a in addresses],
            "dhcp_clients": [{"interface": d.get("interface"), "status": d.get("status"), "dhcp_server": d.get("dhcp-server"), "address": d.get("address")} for d in dhcp_clients],
            "pppoe_clients": [{"name": p.get("name"), "interface": p.get("interface"), "status": p.get("status"), "user": p.get("user")} for p in pppoe_clients],
            "dns_servers": dns[0].get("servers", "") if dns else "",
            "gateway": next((r.get("gateway", "") for r in routes if r.get("dst-address") == "0.0.0.0/0"), ""),
        }
    except Exception as e:
        try: conn.close()
        except: pass
        raise


def configure_wan(router, wan_interface: str, wan_type: str, **kwargs) -> dict:
    conn = _get_connection(router)
    conn.connect()
    try:
        if wan_type == "dhcp":
            for d in conn.command("/ip/dhcp-client/print"):
                if d.get("interface") == wan_interface and ".id" in d:
                    conn.command(f"/ip/dhcp-client/remove =.id={d['.id']}")
            for a in conn.command("/ip/address/print"):
                if a.get("interface") == wan_interface and ".id" in a:
                    conn.command(f"/ip/address/remove =.id={a['.id']}")
            conn.command(f"/ip/dhcp-client/add =interface={wan_interface} =disabled=no")

        elif wan_type == "pppoe":
            user = kwargs.get("pppoe_user", "")
            password = kwargs.get("pppoe_password", "")
            for p in conn.command("/interface/pppoe-client/print"):
                if (p.get("interface") == wan_interface or p.get("name") == "pppoe-wan") and ".id" in p:
                    conn.command(f"/interface/pppoe-client/remove =.id={p['.id']}")
            for d in conn.command("/ip/dhcp-client/print"):
                if d.get("interface") == "pppoe-wan" and ".id" in d:
                    conn.command(f"/ip/dhcp-client/remove =.id={d['.id']}")
            conn.command(f"/interface/pppoe-client/add =name=pppoe-wan =interface={wan_interface} =user={user} =password={password} =disabled=no")
            conn.command("/ip/dhcp-client/add =interface=pppoe-wan =disabled=no")

        elif wan_type == "static":
            ip_address = kwargs.get("ip_address", "")
            gateway = kwargs.get("gateway", "")
            dns_servers = kwargs.get("dns_servers", "")
            for d in conn.command("/ip/dhcp-client/print"):
                if d.get("interface") == wan_interface and ".id" in d:
                    conn.command(f"/ip/dhcp-client/remove =.id={d['.id']}")
            for a in conn.command("/ip/address/print"):
                if a.get("interface") == wan_interface and ".id" in a:
                    conn.command(f"/ip/address/remove =.id={a['.id']}")
            for r in conn.command("/ip/route/print"):
                if r.get("dst-address") == "0.0.0.0/0" and ".id" in r:
                    conn.command(f"/ip/route/remove =.id={r['.id']}")
            if ip_address:
                conn.command(f"/ip/address/add =address={ip_address} =interface={wan_interface}")
            if gateway:
                conn.command(f"/ip/route/add =dst-address=0.0.0.0/0 =gateway={gateway}")
            if dns_servers:
                conn.command(f"/ip/dns/set =servers={dns_servers}")

        else:
            raise ValueError(f"Tipo WAN inválido: {wan_type}")

        conn.close()
        return {"success": True, "message": f"Configuración WAN ({wan_type}) aplicada en {wan_interface}"}
    except Exception as e:
        try: conn.close()
        except: pass
        return {"success": False, "error": str(e)}
