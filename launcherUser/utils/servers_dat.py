# launcherUser/utils/servers_dat.py
"""
Parse and edit Minecraft Java Edition servers.dat (NBT format).
Path: <gameDirectory>/servers.dat (uncompressed, big-endian).
Used to sync launcher config server_status.servers into the in-game server list.
"""

import os

# Minecraft uses uncompressed NBT; nbtlib auto-detects gzip, we pass gzipped=False for clarity
try:
    import nbtlib
except ImportError:
    nbtlib = None

# Standard filename in game directory. Minecraft uses servers.dat; we also try server.dat when loading.
SERVERS_DAT = "servers.dat"
SERVERS_DAT_ALT = "server.dat"


def _ip_from_config(host, port=25565):
    """Build Minecraft 'ip' string: host or host:port if port != 25565."""
    host = (host or "").strip()
    if not host:
        return ""
    port = int(port)
    if port == 25565:
        return host
    return f"{host}:{port}"


def load_servers(game_directory):
    """
    Load server list from game_directory/servers.dat.
    Returns list of dicts: [{"name": str, "ip": str, "acceptTextures": 0|1, "icon": str|None}, ...].
    Returns [] if file missing, invalid, or nbtlib not installed.
    """
    if not nbtlib:
        return []
    path = os.path.join(game_directory, SERVERS_DAT)
    if not os.path.isfile(path):
        path = os.path.join(game_directory, SERVERS_DAT_ALT)
    if not os.path.isfile(path):
        return []
    try:
        # Minecraft servers.dat is uncompressed, big-endian
        data = nbtlib.load(path, gzipped=False)
    except Exception:
        return []
    out = []
    servers_tag = data.get("servers")
    if servers_tag is None:
        return []
    try:
        for entry in servers_tag:
            if not hasattr(entry, "get"):
                continue
            name = entry.get("name")
            ip = entry.get("ip")
            if ip is None:
                continue
            # nbtlib tags inherit from Python types; extract string value
            name_str = str(name) if name is not None else "Server"
            ip_str = str(ip)
            accept = entry.get("acceptTextures")
            accept_int = int(accept) if accept is not None else 0
            icon = entry.get("icon")
            icon_str = str(icon) if icon is not None else None
            out.append({
                "name": name_str,
                "ip": ip_str,
                "acceptTextures": accept_int,
                "icon": icon_str,
            })
    except Exception:
        return []
    return out


def save_servers(game_directory, servers_list):
    """
    Write server list to game_directory/servers.dat (uncompressed NBT).
    servers_list: list of dicts with keys "name", "ip", optionally "acceptTextures", "icon".
    """
    if not nbtlib:
        return False
    path = os.path.join(game_directory, SERVERS_DAT)
    try:
        Compound = nbtlib.Compound
        List = nbtlib.List
        String = nbtlib.String
        Byte = nbtlib.Byte
        nbt_servers = []
        for s in servers_list:
            name = str(s.get("name", "Server"))
            ip = str(s.get("ip", ""))
            if not ip:
                continue
            entry = Compound({
                "name": String(name),
                "ip": String(ip),
            })
            if "acceptTextures" in s:
                entry["acceptTextures"] = Byte(int(s["acceptTextures"]))
            if s.get("icon"):
                entry["icon"] = String(str(s["icon"]))
            nbt_servers.append(entry)
        root = Compound({"servers": List(nbt_servers)})
        nbt_file = nbtlib.File(root, gzipped=False)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        nbt_file.save(path, gzipped=False)
        return True
    except Exception:
        return False


def merge_config_servers(game_directory, config_servers):
    """
    Merge launcher config servers into Minecraft servers.dat.
    config_servers: list of {"name": str, "host": str, "port": int (optional)} from server_status.servers.
    - Loads existing servers.dat if present.
    - For each config server, adds or updates by ip (host:port). Existing entry: update name; new: append.
    - Saves back to game_directory/servers.dat.
    Returns True if write succeeded (or no config servers), False on error.
    """
    if not config_servers:
        return True
    if not nbtlib:
        return False
    path = os.path.join(game_directory, SERVERS_DAT)
    existing = load_servers(game_directory)
    # Index existing by ip for merge
    by_ip = {s["ip"]: s for s in existing}
    for cfg in config_servers:
        host = cfg.get("host", "").strip()
        if not host:
            continue
        port = int(cfg.get("port", 25565))
        name = (cfg.get("name") or host or "Server").strip() or "Server"
        ip = _ip_from_config(host, port)
        if not ip:
            continue
        if ip in by_ip:
            by_ip[ip]["name"] = name
        else:
            by_ip[ip] = {"name": name, "ip": ip, "acceptTextures": 0, "icon": None}
    merged = list(by_ip.values())
    return save_servers(game_directory, merged)
