"""
Path resolution for the launcher. Works both when running from source and when
frozen (e.g. PyInstaller). Read-only assets come from the bundle; writable data
(config overrides, accounts, settings, packs) always goes to the writable dir.
"""
import os
import sys


def _is_frozen() -> bool:
    """True if running from a frozen executable (PyInstaller, Nuitka, etc.)."""
    return getattr(sys, "frozen", False)


def _frozen_asset_base() -> str:
    """Base path for read-only bundled files (inside the exe bundle). PyInstaller uses _MEIPASS."""
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.executable))


def _dev_base() -> str:
    """Base path when running from source: project root (where config/, launcherAdmin/, launcherUser/ live)."""
    # Assume we're in src/common/ or similar; go up to project root.
    this_file = os.path.abspath(__file__)
    # src/common/paths.py -> project root = 2 levels up
    common_dir = os.path.dirname(this_file)
    src_dir = os.path.dirname(common_dir)
    return os.path.dirname(src_dir)


def base_dir() -> str:
    """
    Base directory for read-only assets (default config, bundled images, translations).
    - When frozen: inside the executable bundle (e.g. sys._MEIPASS).
    - When running from source: project root.
    """
    if _is_frozen():
        return _frozen_asset_base()
    return _dev_base()


def writable_dir() -> str:
    """
    Directory for writable data: user config override, accounts, settings, packs, cache.
    Must be outside the bundle so updates and installs persist.
    - When frozen: directory containing the executable (or a dedicated user-data dir).
    - When running from source: project root (e.g. launcherUser/resources or a single data dir).
    """
    if _is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return _dev_base()


def resource_dir(app: str) -> str:
    """
    Path to app-specific resources (images, etc.). Prefer writable_dir first for overrides,
    then fall back to bundled/default. app is 'admin' or 'user'.
    """
    w = writable_dir()
    if _is_frozen():
        # Bundled resources: same layout as source (launcherUser/resources/images, launcherAdmin/resources/images)
        app_dir = "launcherAdmin" if app == "admin" else "launcherUser"
        return os.path.join(base_dir(), app_dir, "resources", "images")
    if app == "admin":
        return os.path.join(w, "launcherAdmin", "resources", "images")
    return os.path.join(w, "launcherUser", "resources", "images")


def default_config_path(app: str) -> str:
    """Path to the default config file for admin or user (bundled or in config/defaults)."""
    if _is_frozen():
        return os.path.join(base_dir(), "config", "defaults", f"{app}.default.json")
    return os.path.join(base_dir(), "config", "defaults", f"{app}.default.json")


def user_config_path(app: str) -> str:
    """Path to optional user override config. When frozen: next to exe. When dev: project root or config/ (first that exists)."""
    primary = os.path.join(writable_dir(), f"{app}.config.json")
    if _is_frozen():
        return primary
    fallback = os.path.join(writable_dir(), "config", f"{app}.config.json")
    if os.path.isfile(fallback) and not os.path.isfile(primary):
        return fallback
    return primary


def resolve_asset_path(relative_path: str) -> str:
    """Resolve a path from config (e.g. 'launcherUser/resources/images/logo.png') to an absolute path.
    When frozen: resolve relative to the exe dir (writable_dir) first, then fall back to the bundle (base_dir)."""
    if not relative_path:
        return ""
    if os.path.isabs(relative_path):
        return relative_path
    if _is_frozen():
        next_to_exe = os.path.join(writable_dir(), relative_path)
        if os.path.isfile(next_to_exe):
            return next_to_exe
        return os.path.join(base_dir(), relative_path)
    return os.path.join(writable_dir(), relative_path)
