# workers/server_status_worker.py
"""
Worker that pings Minecraft Java servers and emits status (online, players, latency).
Used when config server_status.enabled is true and server_status.servers is non-empty.
"""

from PyQt6.QtCore import QObject, pyqtSignal

try:
    from mcstatus import JavaServer
    MCSTATUS_AVAILABLE = True
except ImportError:
    MCSTATUS_AVAILABLE = False


def _parse_description(desc):
    """Extract plain text from server description (can be dict with 'text' or string)."""
    if desc is None:
        return ""
    if isinstance(desc, str):
        return desc.strip()
    if isinstance(desc, dict):
        if "text" in desc:
            return _parse_description(desc["text"])
        if "extra" in desc:
            return "".join(
                (e.get("text", "") if isinstance(e, dict) else str(e))
                for e in desc["extra"]
            ).strip()
    return str(desc)


def _get_motd_raw(desc):
    """Get MOTD string that may contain § color/format codes, for tooltip rendering."""
    if desc is None:
        return ""
    # mcstatus may expose to_minecraft() for legacy § string
    if hasattr(desc, "to_minecraft"):
        return (desc.to_minecraft() or "").strip()
    if isinstance(desc, str):
        return desc.strip()
    if isinstance(desc, dict):
        # Build approximate § string from dict (text + extra with color/bold etc.)
        return _motd_dict_to_legacy(desc)
    return str(desc)


def _motd_dict_to_legacy(obj, style=""):
    """Recursively build §-style string from JSON-style MOTD (text, extra, color, bold, ...)."""
    out = []
    color = obj.get("color", "")
    if color:
        code = {"black": "0", "dark_blue": "1", "dark_green": "2", "dark_aqua": "3", "dark_red": "4",
                "dark_purple": "5", "gold": "6", "gray": "7", "dark_gray": "8", "blue": "9",
                "green": "a", "aqua": "b", "red": "c", "light_purple": "d", "yellow": "e", "white": "f"}.get(color, "")
        if code:
            style = f"§{code}"
    if obj.get("bold"):
        style += "§l"
    if obj.get("italic"):
        style += "§o"
    if obj.get("underlined"):
        style += "§n"
    if obj.get("strikethrough"):
        style += "§m"
    if obj.get("obfuscated"):
        style += "§k"
    if "text" in obj:
        out.append(style + str(obj["text"]))
    for e in obj.get("extra", []):
        if isinstance(e, dict):
            out.append(_motd_dict_to_legacy(e, style))
        else:
            out.append(style + str(e))
    return "".join(out)


def _extract_favicon_b64(status) -> str | None:
    """Get server favicon as base64 string (no data URL prefix), or None if missing."""
    icon = getattr(status, "icon", None)
    if not icon:
        return None
    s = str(icon).strip()
    if s.startswith("data:image/png;base64,"):
        return s.removeprefix("data:image/png;base64,")
    return s


def ping_one(server_spec, timeout=8):
    """
    Ping a single server. server_spec: {"name": "...", "host": "...", "port": 25565}.
    Returns dict: name, online, players_online, players_max, latency_ms, description, error, favicon_b64.
    """
    name = server_spec.get("name", server_spec.get("host", "Server"))
    host = server_spec.get("host", "")
    port = int(server_spec.get("port", 25565))
    empty = {"name": name, "online": False, "error": "No host", "players_online": None, "players_max": None, "latency_ms": None, "description": "", "description_raw": "", "favicon_b64": None}
    if not host:
        return empty
    if not MCSTATUS_AVAILABLE:
        return {"name": name, "online": False, "error": "mcstatus not installed", "players_online": None, "players_max": None, "latency_ms": None, "description": "", "description_raw": "", "favicon_b64": None}
    try:
        # Use direct host:port so we don't depend on DNS SRV records (many servers don't have them)
        # Timeout is passed to the server instance, not to status()
        server = JavaServer(host, port, timeout=timeout)
        status = server.status()
        players_online = status.players.online if status.players else 0
        players_max = status.players.max if status.players else 0
        latency_ms = round(status.latency) if status.latency is not None else None
        raw_desc = status.description
        description = _parse_description(raw_desc) if raw_desc else ""
        description_raw = _get_motd_raw(raw_desc) if raw_desc else ""
        favicon_b64 = _extract_favicon_b64(status)
        return {
            "name": name,
            "online": True,
            "players_online": players_online,
            "players_max": players_max,
            "latency_ms": latency_ms,
            "description": description,
            "description_raw": description_raw,
            "error": None,
            "favicon_b64": favicon_b64,
        }
    except Exception as e:
        return {
            "name": name,
            "online": False,
            "error": str(e),
            "players_online": None,
            "players_max": None,
            "latency_ms": None,
            "description": "",
            "description_raw": "",
            "favicon_b64": None,
        }


class ServerStatusWorker(QObject):
    """Pings a list of servers and emits a single list of status dicts."""
    finished = pyqtSignal(list)  # list of status dicts from ping_one
    error = pyqtSignal(str)

    def __init__(self, servers):
        super().__init__()
        self.servers = servers or []

    def run(self):
        if not self.servers:
            self.finished.emit([])
            return
        results = []
        for spec in self.servers:
            results.append(ping_one(spec))
        self.finished.emit(results)
