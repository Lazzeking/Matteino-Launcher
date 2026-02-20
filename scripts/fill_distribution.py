#!/usr/bin/env python3
"""
Copy your current development setup into distribution/ so you can ship it
with the executables (e.g. after running the distribute script).

- Copies user.config.json and admin.config.json from config/ or project root.
- Copies any relative paths referenced in those configs (logo_path, icon_path,
  loading_image_path, translations.file) into distribution/, preserving paths.
- Optionally copies resources/about.html.

Run from project root: python scripts/fill_distribution.py
"""

import json
import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DISTRIBUTION = PROJECT_ROOT / "distribution"

# Config keys that point to files we should copy (relative paths only)
USER_FILE_KEYS = ("logo_path", "icon_path", "loading_image_path")
ADMIN_FILE_KEYS = ("logo_path", "icon_path")
ADMIN_TRANSLATIONS_KEY = ("translations", "file")  # nested: translations.file


def find_config(app: str) -> Path | None:
    """Return path to app config if it exists (config/ or root)."""
    for base in (PROJECT_ROOT / "config", PROJECT_ROOT):
        p = base / f"{app}.config.json"
        if p.is_file():
            return p
    return None


def copy_configs() -> list[str]:
    copied = []
    for app in ("user", "admin"):
        src = find_config(app)
        if not src:
            continue
        dst = DISTRIBUTION / f"{app}.config.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(dst.relative_to(PROJECT_ROOT)))
    return copied


def copy_file_from_config(config_path: Path, keys: tuple, nested_key: tuple | None = None) -> list[str]:
    """If config has a relative path at key(s), copy that file into distribution/ preserving path."""
    copied = []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return copied

    if nested_key:
        obj = data
        for k in nested_key:
            obj = obj.get(k) if isinstance(obj, dict) else None
            if obj is None:
                return copied
        path_val = obj
    else:
        path_val = None
        for k in keys:
            if data.get(k):
                path_val = data[k]
                break

    if not path_val or os.path.isabs(path_val):
        return copied

    src = PROJECT_ROOT / path_val
    if not src.is_file():
        return copied
    dst = DISTRIBUTION / path_val
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied.append(str(dst.relative_to(PROJECT_ROOT)))
    return copied


def copy_about() -> list[str]:
    copied = []
    src = PROJECT_ROOT / "resources" / "about.html"
    if src.is_file():
        dst = DISTRIBUTION / "resources" / "about.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(dst.relative_to(PROJECT_ROOT)))
    return copied


def main() -> None:
    DISTRIBUTION.mkdir(parents=True, exist_ok=True)

    all_copied: list[str] = []

    # Config files
    all_copied.extend(copy_configs())

    # User config asset paths
    user_cfg = find_config("user")
    if user_cfg:
        all_copied.extend(copy_file_from_config(user_cfg, USER_FILE_KEYS))

    # Admin config asset paths + translations file
    admin_cfg = find_config("admin")
    if admin_cfg:
        all_copied.extend(copy_file_from_config(admin_cfg, ADMIN_FILE_KEYS))
        all_copied.extend(copy_file_from_config(admin_cfg, (), ADMIN_TRANSLATIONS_KEY))

    # Optional: about.html
    all_copied.extend(copy_about())

    if all_copied:
        print("Filled distribution/ with:")
        for p in sorted(set(all_copied)):
            print("  ", p)
        print("\nNote: Config may contain secrets (API keys, etc.). Do not commit distribution/ if so.")
    else:
        print("No config or assets found to copy. Add user.config.json and/or admin.config.json in config/ or project root.")


if __name__ == "__main__":
    main()
