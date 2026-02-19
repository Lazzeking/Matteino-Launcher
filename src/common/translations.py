"""
Discover available translation files (.qm) for the launcher and provide
display names. Used by the GUI language selector.
"""
import os
import glob

from . import paths

# Locale code -> display name (in that language or English)
_LOCALE_NAMES = {
    "en": "English",
    "it": "Italiano",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
}


def get_available_languages(app: str) -> list[dict]:
    """
    Return list of available languages for the given app ("admin" or "user").
    Each item is {"id": "", "file": "", "name": "English"} for English, or
    {"id": "it", "file": "launcherAdmin/translations/it.qm", "name": "Italiano"}.
    Paths in "file" are relative to project root (for config).
    """
    base = paths.base_dir()
    if app == "admin":
        trans_dir = os.path.join(base, "launcherAdmin", "translations")
        rel_prefix = "launcherAdmin/translations/"
    else:
        trans_dir = os.path.join(base, "launcherUser", "translations")
        rel_prefix = "launcherUser/translations/"

    result = [{"id": "", "file": "", "name": "English"}]

    if not os.path.isdir(trans_dir):
        return result

    for qm_path in sorted(glob.glob(os.path.join(trans_dir, "*.qm"))):
        basename = os.path.basename(qm_path)
        code = basename[:-3] if basename.endswith(".qm") else basename
        name = _LOCALE_NAMES.get(code, code)
        result.append({
            "id": code,
            "file": rel_prefix + basename,
            "name": name,
        })
    return result


def get_current_translation_file(config: dict) -> str:
    """
    Return the current translation file path from config (for matching in combo),
    or "" for English.
    """
    trans = config.get("translations", {})
    if not trans.get("enabled"):
        return ""
    return trans.get("file", "").strip()
