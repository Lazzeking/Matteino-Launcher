"""
Load launcher config from JSON: defaults first, then optional user override file,
then environment variables for secrets. Simple flat-ish structure so non-technical
users can edit the JSON.
"""
import json
import os
import sys
from pathlib import Path

from . import paths


def _load_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _migrate_user_config_from_legacy_paths(app: str, new_path: str) -> None:
    """If new_path does not exist, try legacy paths (config/<app>.config.json or <app>.config.json in writable_dir) and copy to new_path."""
    w = paths.writable_dir()
    legacy_candidates = [
        os.path.join(w, "config", f"{app}.config.json"),
        os.path.join(w, f"{app}.config.json"),
    ]
    for legacy in legacy_candidates:
        if os.path.isfile(legacy):
            try:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                with open(legacy, "r", encoding="utf-8") as f:
                    data = f.read()
                with open(new_path, "w", encoding="utf-8") as f:
                    f.write(data)
            except OSError:
                pass
            break


def _migrate_default_config_from_legacy_paths(app: str, new_path: str) -> None:
    """If new_path does not exist, copy from legacy config/defaults/<app>.default.json (project root) to new_path."""
    if os.path.isfile(new_path):
        return
    base = paths.base_dir()
    legacy = os.path.join(base, "config", "defaults", f"{app}.default.json")
    if os.path.isfile(legacy):
        try:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            with open(legacy, "r", encoding="utf-8") as f:
                data = f.read()
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(data)
        except OSError:
            pass


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
    1. launcher_config/defaults/<app>.default.json (bundled when frozen, under writable_dir when not)
    2. When frozen: launcher_config/<app>.config.json in the bundle (packager's config shipped with the exe)
    3. Optional <app>.config.json in writable dir (override next to the executable when frozen)
    4. Environment variables for secrets (see env_map below)

    Returns a single dict. Paths in the config can be relative to writable_dir();
    the loader does not resolve them here so callers can use paths.writable_dir().
    """
    default_path = paths.default_config_path(app)
    # When running from source, migrate defaults to launcher_config/defaults/ if needed
    if not getattr(sys, "frozen", False) and not os.path.isfile(default_path):
        _migrate_default_config_from_legacy_paths(app, default_path)
    base = _load_json(default_path)
    if not base:
        base = {}

    # Bundled config (packager's config built into the exe when frozen)
    if getattr(sys, "frozen", False):
        bundled_cfg = os.path.join(paths.base_dir(), paths.LAUNCHER_CONFIG_DIR, f"{app}.config.json")
        bundled = _load_json(bundled_cfg)
        if bundled:
            base = _deep_merge(base, bundled)

    user_path = paths.user_config_path(app)
    # When running from source, migrate from old locations so config/ is no longer mixed with game config
    if not getattr(sys, "frozen", False) and not os.path.isfile(user_path):
        _migrate_user_config_from_legacy_paths(app, user_path)
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


def save_user_config(app: str, override: dict) -> None:
    """
    Merge override into the user config file and write it back.
    Use for persisting UI choices (e.g. translations). Does not touch defaults.
    """
    user_path = paths.user_config_path(app)
    current = _load_json(user_path) if os.path.isfile(user_path) else {}
    merged = _deep_merge(current, override)
    os.makedirs(os.path.dirname(user_path), exist_ok=True)
    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)


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
