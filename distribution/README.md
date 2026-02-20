# Distribution files (for the distribute script)

Everything you put here is **packaged with the executables** when you run the **distribute script** on your machine. The script combines the exes (from `dist/`, e.g. downloaded from GitHub Actions) with this folder into a shippable zip/folder.

Use it for files you want next to the launcher when you ship:

- **Config overrides** — `user.config.json` and/or `admin.config.json` (a config next to the exe overrides the one bundled inside).
- **Setup/run scripts** — e.g. `run.sh` (Linux), `Run Launcher.bat` (Windows), `run.command` (macOS).
- **Images** — logos, icons, or other assets.
- **Docs** — README, license, install instructions.

**Workflow:** GitHub Actions builds default executables only (no custom files). You download the artifact for your platform, unzip into `dist/`, put your custom files in `distribution/`, then run `./scripts/distribute.sh [platform]` to get a folder and zip ready to ship.

**Auto-fill from your dev setup:** Run `python scripts/fill_distribution.py` to copy your current config files and any assets they reference (logos, icons, translations, etc.) into `distribution/`. Then run the distribute script as above. Config may contain secrets—do not commit `distribution/` if it does.
