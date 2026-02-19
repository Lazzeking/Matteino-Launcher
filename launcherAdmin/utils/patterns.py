import os
import urllib.parse
from typing import List


def normalize_patterns(patterns: List[str], base_folder: str) -> List[dict]:
    """
    Normalize user-defined patterns and parse optional target paths.
    Returns a list of dicts with 'source' and optional 'target'.
    """
    result = []
    for pattern in patterns:
        target = None
        if "=>" in pattern:
            parts = pattern.split("=>")
            pattern = parts[0].strip()
            target = parts[1].strip()

        full_path = os.path.join(base_folder, pattern)
        if pattern.endswith('/*'):
            pattern = pattern[:-1] + '**'
        elif os.path.isdir(full_path) and not any(c in pattern for c in '*?'):
            pattern = os.path.join(pattern, '**')

        result.append({
            "source": pattern,
            "target": target
        })

    return result


def collect_all_patterns(pack_data: dict, base_folder: str) -> list[dict]:
    """
    Returns a normalized list of pattern dictionaries.
    Each dict contains:
        - source: the pattern (glob or URL)
        - target: optional custom target path
        - group: optional group name (for optional features)
    """
    collected = []

    # === Normal overrides ===
    for raw in pack_data.get("overrides", []):
        if "=>" in raw:
            source, target = map(str.strip, raw.split("=>", 1))
        else:
            source = raw.strip()
            target = None
        if source:
            collected.append({
                "source": source,
                "target": target,
                "group": None
            })

    # === Optional features ===
    for feature in pack_data.get("optionalFeatures", []):
        group_name = feature.get("name", "optional")

        for raw in feature.get("include", []):
            if "=>" in raw:
                source, target = map(str.strip, raw.split("=>", 1))
            else:
                source = raw.strip()
                target = None
            if source:
                collected.append({
                    "source": source,
                    "target": target,
                    "group": group_name
                })

    return collected


def is_url(path: str) -> bool:
    parsed = urllib.parse.urlparse(path)
    return parsed.scheme in ('http', 'https')
