"""
Load launcher config from JSON: defaults first, then optional user override file,
then environment variables for secrets. Simple flat-ish structure so non-technical
users can edit the JSON.
"""
import json
import os
from pathlib import Path

from . import paths


def _load_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base (override wins). Nested dicts merged recursively."""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _apply_env(config: dict, env_map: list[tuple[str, str]]) -> None:
    """
    Override config with environment variables. env_map is list of (env_var, "key.path.in.config").
    Only set if env var is non-empty.
    """
    for env_var, key_path in env_map:
        value = os.environ.get(env_var, "").strip()
        if not value:
            continue
        keys = key_path.split(".")
        d = config
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value


def load_config(app: str) -> dict:
    """
    Load config for 'admin' or 'user'. Uses:
    1. config/defaults/<app>.default.json (bundled or from project)
    2. Optional <app>.config.json in writable dir (user override)
    3. Environment variables for secrets (see env_map below)

    Returns a single dict. Paths in the config can be relative to writable_dir();
    the loader does not resolve them here so callers can use paths.writable_dir().
    """
    default_path = paths.default_config_path(app)
    base = _load_json(default_path)
    if not base:
        base = {}

    user_path = paths.user_config_path(app)
    override = _load_json(user_path)
    if override:
        base = _deep_merge(base, override)

    # Env overrides for secrets (no need to put them in a file)
    if app == "user":
        _apply_env(base, [
            ("LAUNCHER_MICROSOFT_CLIENT_ID", "microsoft.client_id"),
            ("LAUNCHER_MICROSOFT_CLIENT_SECRET", "microsoft.client_secret"),
        ])
    elif app == "admin":
        _apply_env(base, [
            ("LAUNCHER_CURSEFORGE_API_KEY", "curseforge_api_key"),
        ])

    return base


def get_user_paths(app: str) -> dict:
    """
    Return standard paths the app should use (all under writable_dir).
    Keys: resources_dir, accounts_file, settings_file, packages_file, workspaces_file (admin only), packs_dir (user only).
    """
    w = paths.writable_dir()
    base = w
    # When running from source, admin/user have their own resources next to the script
    if app == "admin":
        return {
            "resources_dir": os.path.join(base, "launcherAdmin", "resources"),
            "workspaces_file": os.path.join(base, "launcherAdmin", "resources", "workspaces.json"),
            "images_dir": os.path.join(base, "launcherAdmin", "resources", "images"),
        }
    return {
        "resources_dir": os.path.join(base, "launcherUser", "resources"),
        "accounts_file": os.path.join(base, "launcherUser", "resources", "accounts.json"),
        "settings_file": os.path.join(base, "launcherUser", "resources", "settings.json"),
        "packages_file": os.path.join(base, "launcherUser", "resources", "packages.json"),
        "images_dir": os.path.join(base, "launcherUser", "resources", "images"),
        "packs_dir": os.path.join(base, "launcherUser", "packs"),
    }
