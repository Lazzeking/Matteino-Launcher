#!/usr/bin/env python3
"""
Copy your current development setup into distribution/ so you can ship it
with the executables (e.g. after running the distribute script).

- Copies user.config.json and admin.config.json from config/ or project root.
- Copies all graphics: full launcherUser/resources/images/ and launcherAdmin/resources/images/
  (logo, icon, loading, down_chevron, matteinocraft_mc_logo, etc.).
- Copies any extra relative paths from config (e.g. translations.file) into distribution/.
- Copies resources/about.html.

Config image paths (logo_path, icon_path, etc.) are resolved relative to the exe at runtime.

Run from project root: python scripts/fill_distribution.py
"""

import json
import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DISTRIBUTION = PROJECT_ROOT / "distribution"

# Full image directories to copy (all graphics used by each app)
IMAGE_DIRS = [
    "launcherUser/resources/images",
    "launcherAdmin/resources/images",
]
ADMIN_TRANSLATIONS_KEY = ("translations", "file")


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


def copy_image_dirs() -> list[str]:
    """Copy full image directories so all graphics (logo, icon, chevron, etc.) are included."""
    copied = []
    for rel_dir in IMAGE_DIRS:
        src_dir = PROJECT_ROOT / rel_dir
        if not src_dir.is_dir():
            continue
        dst_dir = DISTRIBUTION / rel_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        for f in src_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, dst_dir / f.name)
                copied.append(str((dst_dir / f.name).relative_to(PROJECT_ROOT)))
    return copied


def copy_file_from_config(config_path: Path, nested_key: tuple) -> list[str]:
    """Copy a single file path from nested config key (e.g. translations.file) into distribution/."""
    copied = []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return copied
    obj = data
    for k in nested_key:
        obj = obj.get(k) if isinstance(obj, dict) else None
        if obj is None:
            return copied
    path_val = obj if isinstance(obj, str) else None
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

    # All graphics: full image dirs for user and admin
    all_copied.extend(copy_image_dirs())

    # Admin translations file (e.g. it.qm) if set in config
    admin_cfg = find_config("admin")
    if admin_cfg:
        all_copied.extend(copy_file_from_config(admin_cfg, ADMIN_TRANSLATIONS_KEY))

    # about.html
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
