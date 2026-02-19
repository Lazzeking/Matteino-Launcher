# Matteino Launcher

Open-source modded Minecraft launcher. Two applications share this repository: the **user launcher** (players: install packs, manage accounts, launch the game) and the **admin launcher** (pack authors: manage workspaces, mod lists, and optional features).

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`: PyQt6, minecraft-launcher-lib, requests, psutil

## Running

From the project root (after `pip install -r requirements.txt`):

- **User launcher:** `python launcherUser/main.py`
- **Admin launcher:** `python launcherAdmin/main.py`

Config and data paths are resolved from the project root when run this way; see `config/defaults/` for default settings.

## Project layout

- `launcherUser/` — User launcher UI and logic (main window, accounts, packs, play).
- `launcherAdmin/` — Admin launcher (workspace selection, pack editing, mod list, optional features).
- `src/common/` — Shared code (config, paths, version, about dialog).
- `config/` — Default config files; local overrides and secrets are gitignored.
- `resources/` — Editable assets (e.g. About text in `about.html`).

Version is defined in `src/common/version.py` and used by both apps.

## Config and data

- Default config: `config/defaults/user.default.json` and `admin.default.json`.
- Local overrides and secrets (e.g. `*.local.json`, `config/local/`, `.env`) are not committed; see `.gitignore`.

## License

GNU General Public License v3.0. See [LICENSE](LICENSE) and [resources/about.html](resources/about.html) for details and third-party credits.
