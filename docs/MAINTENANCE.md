# Maintaining the launcher

## Keeping minecraft-launcher-lib up to date

[minecraft-launcher-lib](https://github.com/JakobDev/minecraft-launcher-lib) is the main dependency for Minecraft installation, mod loaders, and Microsoft auth. Keeping it updated ensures compatibility with new Minecraft versions and launcher APIs.

### How we get update alerts

- **Dependabot** (`.github/dependabot.yml`) opens a PR when a new version of any `requirements.txt` dependency is released (monthly check). Merge only after testing.
- You can also watch the library’s [releases](https://github.com/JakobDev/minecraft-launcher-lib/releases) or [PyPI](https://pypi.org/project/minecraft-launcher-lib/) and bump the version in `requirements.txt` manually.

### Where it’s used (so you know what to test)

| Area | Files | What it does |
|------|--------|----------------|
| **User – install** | `launcherUser/workers/install_worker.py` | `install_minecraft_version`, `mod_loader.get_mod_loader`, `loader.install()` |
| **User – launch** | `launcherUser/windows/main_window.py` | `get_minecraft_command` for running the game |
| **User – auth** | `launcherUser/windows/main_window.py`, `launcherUser/auth/server.py` | `microsoft_account.get_secure_login_data` and auth flow |
| **Admin – versions** | `launcherAdmin/workers/versions_loader_worker.py`, `workspace_window.py` | `utils.get_available_versions`, `mod_loader.get_mod_loader` for dropdowns |
| **Admin – mrpack** | `launcherAdmin/windows/workspace_window.py`, `launcherAdmin/workers/install_worker.py` | `mrpack.get_mrpack_information`, `mrpack.install_mrpack`, `mrpack.get_mrpack_launch_version`, `get_minecraft_command` |

### When upgrading minecraft-launcher-lib

1. **Check the changelog** — [Releases](https://github.com/JakobDev/minecraft-launcher-lib/releases) for breaking API changes (e.g. `mod_loader`, `mrpack`, or `microsoft_account` renames).
2. **Update version** — In `requirements.txt` set e.g. `minecraft-launcher-lib>=8.x.y` (or pin to the exact version you tested).
3. **Smoke test**:
   - **User launcher:** Install or update a pack, then launch the game; log in with Microsoft if you use it.
   - **Admin launcher:** Load a workspace, open Pack info (MC/loader versions load), run “Test pack” (mrpack build + install + launch).
4. **Build** — Run your usual PyInstaller build and do a quick run of the built executables.

If the library introduces breaking changes, update the imports and calls in the files listed above; the table should make it easy to find every usage.
