# Matteino Launcher

Open-source modded Minecraft launcher. Two applications share this repository: the **user launcher** (players: install packs, manage accounts, launch the game) and the **admin launcher** (pack authors: manage workspaces, mod lists, and optional features).

## Features

### User launcher (players)

- **Microsoft login** — Sign in with a Microsoft account; add, remove, and switch between multiple accounts. Player avatar shown in the launcher.
- **Modpack list** — Choose from modpacks provided by a configurable server URL (`package_base_url` in config). Install or update the selected pack.
- **Optional features** — For packs that define optional features (e.g. extra mods or configs), choose which ones to enable or disable before playing.
- **Settings** — Set minimum and maximum RAM for Minecraft and optionally a custom Java path.
- **Play** — Launch Minecraft with the selected pack and account.

### Admin launcher (pack authors)

- **Workspaces** — Manage multiple workspace folders; each workspace can contain several packs.
- **Pack info** — Edit pack name, version, Minecraft version, and mod loader (Forge, Fabric, etc.).
- **Mods** — Add mods by pasting Modrinth or CurseForge URLs (or ForgeCDN links). Remove or reorder entries. Mod icons are loaded and cached.
- **Overrides** — Edit override paths and files included in the pack.
- **Optional features** — Define optional features (name, description, default on/off, recommendation). Each feature can include local files (globs) or a remote file URL. Players see these in the user launcher and can enable or disable them.
- **Export** — Build the pack as an `.mrpack` file. Test the pack by building and launching the game from the admin.
- **Translations** — Optional UI translation (e.g. Italian) via config and a `.qm` file.

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
