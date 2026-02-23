# Matteino Launcher

<p align="center">
  <img src="launcherUser/resources/images/matteinocraft_mc_logo.png" alt="Matteino Launcher" width="128" />
</p>

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

Config and data paths are resolved from the project root when run this way; see `launcher_config/defaults/` for default settings.

## Project layout

- `launcherUser/` — User launcher UI and logic (main window, accounts, packs, play).
- `launcherAdmin/` — Admin launcher (workspace selection, pack editing, mod list, optional features).
- `src/common/` — Shared code (config, paths, version, about dialog).
- `launcher_config/` — Launcher config: `defaults/` (default JSON), optional overrides `admin.config.json`, `user.config.json`. Do not use `config/` for launcher (reserved for game/pack data if needed).
- `resources/` — Editable assets (e.g. About text in `about.html`).

Version is defined in `src/common/version.py` and used by both apps.

## Config and data

- Default config: `launcher_config/defaults/user.default.json` and `admin.default.json`.
- Overrides: `launcher_config/user.config.json` and `launcher_config/admin.config.json` (optional; do not commit secrets; see `.gitignore`).
- **User launcher – optional server status:** In `launcher_config/user.config.json` you can set `server_status.enabled: true` and `server_status.servers` to a list of `{ "name": "Display Name", "host": "hostname", "port": 25565 }`. The launcher will show a small preview of each server (online/offline and player count), refreshed on a configurable interval (`refresh_interval_seconds`).

## Building distributable releases

Build standalone executables for **Linux, Windows, and macOS** (no Python required for end users). Config and custom resources you set before building are **bundled into the exe**, so the shipped build is pre-configured (APIs, custom URLs, logos, icons).

### Local build (per OS)

- **Linux:** Build on a Linux machine; output in `dist/` (no extension).
- **Windows:** Build on a Windows machine; output in `dist/` (`.exe`).
- **macOS:** Build on a Mac; output in `dist/` (no extension).

1. Install dependencies and PyInstaller:  
   `pip install -r requirements.txt pyinstaller`
2. From the project root, run:  
   `pyinstaller --noconfirm matteino_user.spec`  
   `pyinstaller --noconfirm matteino_admin.spec`  
   Or: `./scripts/build_releases.sh`

### What gets bundled

- **Defaults:** `launcher_config/defaults/*.default.json`, `resources/about.html`, launcher images, admin translations (`.qm`).
- **Your config:** If `launcher_config/user.config.json` or `launcher_config/admin.config.json` exists, it is **included in the exe** and used at runtime (so APIs, custom URLs, etc. are built in). A config file next to the executable still overrides the bundled one.
- **Custom resources:** Paths from your config (`logo_path`, `icon_path`, `loading_image_path` for user) are bundled when they are relative and the files exist, so custom logos and icons ship with the exe.

Executable **name** and **icon** come from your config (override if present, else defaults). Use a `.ico` for the Windows exe icon.

### CI builds (default executables only)

The workflow [`.github/workflows/build-release.yml`](.github/workflows/build-release.yml) builds the **default** user and admin launchers on Linux, Windows, and macOS (on push to `main`, on release, or manual run). Artifacts contain **only the executables** (no custom config or assets):

- **dist-linux** — Linux binaries
- **dist-windows** — Windows `.exe` files
- **dist-macos** — macOS executables

### Shipping your own build (configs, images, scripts)

On your machine, use the **distribute script** to combine the downloaded exes with your custom files into a folder and zip to ship:

1. Download the artifact for the platform you need from Actions and **unzip into `dist/`** (so `dist/` contains the two executables).
2. Put your custom files in **`distribution/`** — or run **`python scripts/fill_distribution.py`** to copy your current dev config and referenced assets (logos, icons, translations, etc.) into `distribution/` automatically.
3. Run: **`./scripts/distribute.sh [platform]`** (e.g. `./scripts/distribute.sh windows`). This creates `release-<platform>/` and `release-<platform>.zip` with the exes plus everything from `distribution/`.

See [`distribution/README.md`](distribution/README.md) for what to put in `distribution/`.

## Future enhancements (admin launcher – Mods)

- **Modify button:** The "Edit" / "Modify" action on each mod entry is currently a placeholder. A possible enhancement is to let the user **change the mod version** (e.g. pick another version compatible with the current Minecraft version and loader). This would require:
  - Loading compatible versions for the mod (Modrinth/CurseForge APIs).
  - Handling **dependencies** (new version may require different or extra mods) and **dependents** (other mods in the pack may depend on this mod and break if the version changes).
  - Clear UI to show what would be added/removed/updated and any compatibility warnings.

## License

GNU General Public License v3.0. See [LICENSE](LICENSE) and [resources/about.html](resources/about.html) for details and third-party credits.
