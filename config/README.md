# Launcher configuration

Configuration is in **JSON** so it's easy to read and edit. You can change launcher name, logos, and URLs without touching code.

## Where config lives

- **Defaults**: `config/defaults/admin.default.json` and `config/defaults/user.default.json` (shipped with the project; do not put secrets here).
- **Your overrides**: Put `admin.config.json` or `user.config.json` next to the launcher (or in the same folder as the executable when built). Only set the keys you want to override; the rest come from defaults.

## Admin config (`admin.default.json` / `admin.config.json`)

| Key | Meaning |
|-----|--------|
| `launcher_name` | Name of the launcher (e.g. "Matteino Launcher"). |
| `window_title` | Text in the admin window title bar. |
| `logo_path` | Path to logo image (relative to project root when running from source). |
| `icon_path` | Path to window icon image. |
| `workspaces_file` | Path to the JSON file that stores the list of workspace folders. |
| `curseforge_api_key` | CurseForge API key for adding mods from CurseForge. Do not commit; set in `admin.config.json` or `LAUNCHER_CURSEFORGE_API_KEY`. |
| `translations.enabled` | Whether to load a translation file. |
| `translations.locale` | Locale code (e.g. "it", "en"). |
| `translations.file` | Path to the .qm translation file. |

## User config (`user.default.json` / `user.config.json`)

| Key | Meaning |
|-----|--------|
| `launcher_name` | Name of the launcher shown to players. |
| `window_title` | Window title of the user launcher. |
| `logo_path` | Path to logo image. |
| `icon_path` | Path to window icon. |
| `loading_image_path` | Path to loading/spinner image. |
| `package_base_url` | **Important.** Base URL where the launcher fetches the modpack list. Example: `https://myserver.com/mypack/launcher` so it loads `.../launcher/packages.json`. |
| `microsoft.client_id` | Azure app Client ID for Microsoft login. **Use your own app; do not commit real values.** , https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade |
| `microsoft.client_secret` | Azure app Client secret. Prefer setting via env: `LAUNCHER_MICROSOFT_CLIENT_SECRET`. |
| `microsoft.redirect_url` | OAuth redirect URL (usually `http://localhost:2411`). |
| `microsoft.redirect_port` | Port for the local OAuth callback server. |
| `minecraft.min_ram_mb` | Minimum RAM for Minecraft (MB). |
| `minecraft.max_ram_mb` | Maximum RAM for Minecraft (MB). |
| `minecraft.java_path` | Leave empty to auto-detect Java, or set a path. |
| `minecraft.jvm_args` | Optional extra JVM arguments. |

## Secrets (do not commit)

- **User (Microsoft login):** Set `microsoft.client_id` and `microsoft.client_secret` in `user.config.json`, or use environment variables `LAUNCHER_MICROSOFT_CLIENT_ID` and `LAUNCHER_MICROSOFT_CLIENT_SECRET`.
- **Admin (CurseForge):** Set `curseforge_api_key` in `admin.config.json`, or use `LAUNCHER_CURSEFORGE_API_KEY`. Required only when adding mods from CurseForge.
- Override files `user.config.json` and `admin.config.json` are in `.gitignore`.
