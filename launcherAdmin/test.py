"""One-off script to resolve a CurseForge file ID to mod info. Requires curseforge_api_key in admin.config.json or LAUNCHER_CURSEFORGE_API_KEY in the environment."""
import os
import sys

_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import requests
from src.common import config as common_config

cfg = common_config.load_config("admin")
API_KEY = (os.environ.get("LAUNCHER_CURSEFORGE_API_KEY") or cfg.get("curseforge_api_key") or "").strip()
if not API_KEY:
    print("Set curseforge_api_key in admin.config.json or LAUNCHER_CURSEFORGE_API_KEY in the environment.")
    sys.exit(1)

file_id = 5803518
base_url = "https://api.curseforge.com/v1"
headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Step 1: Get file info
file_resp = requests.post(f"{base_url}/mods/files",
                          headers=headers, json={"fileIds": [file_id]})
file_resp.raise_for_status()
file_info = file_resp.json()["data"][0]

mod_id = file_info["modId"]
download_url = file_info["downloadUrl"]

# Step 2: Get mod info (to fetch slug)
mod_resp = requests.get(f"{base_url}/mods/{mod_id}", headers=headers)
mod_resp.raise_for_status()
mod_info = mod_resp.json()["data"]

slug = mod_info["slug"]
mod_page_url = f"https://www.curseforge.com/minecraft/mc-mods/{slug}"

print("Mod ID:", mod_id)
print("Display Name:", file_info["displayName"])
print("Download URL:", download_url)
print("Mod Page URL:", mod_page_url)
