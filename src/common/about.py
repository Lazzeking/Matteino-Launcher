"""
Load the shared About / credits / licenses HTML.
Content is read from resources/about.html (editable); placeholders are filled at runtime.
"""
import os
import html as html_module

from src.common import paths
from src.common.version import __version__

# Default repo URL; set to "" to hide the source link in the template
REPO_URL = "https://github.com/matteinocraft/LauncherPython-v2"

_ABOUT_HTML_PATH = os.path.join(paths.base_dir(), "resources", "about.html")

_DEFAULT_HTML = """<h2 style="margin-top:0;">{{LAUNCHER_NAME}}</h2>
<p><b>Version {{VERSION}}</b></p>
<p>Open-source modded Minecraft launcher. {{REPO_ANCHOR}}</p>
<h3>Author &amp; maintainer</h3>
<p><strong>Lazzeking</strong> — main developer and maintainer. <a href="mailto:lazzeking@gmail.com">lazzeking@gmail.com</a> · <a href="https://github.com/Lazzeking">https://github.com/Lazzeking</a></p>
<h3>Our license</h3>
<p>Licensed under the <a href="https://www.gnu.org/licenses/gpl-3.0.html">GNU General Public License v3.0</a>. Copyright (C) 2025 Matteino Launcher / Matteinocraft authors.</p>
<h3>Third-party libraries</h3>
<p>PyQt6, minecraft-launcher-lib, requests, psutil — see repository or resources/about.html for full credits and licenses.</p>
<h3>APIs and external services</h3>
<p>Modrinth API, CurseForge API, Minecraft/Microsoft auth, Crafthead (avatars), Starlightskins (renders). Use subject to their respective terms.</p>"""


def get_about_html(
    launcher_name: str = "Matteino Launcher",
    version: str | None = None,
    repo_url: str | None = None,
) -> str:
    """
    Load resources/about.html (if present), replace placeholders, return HTML.
    Falls back to built-in default if the file is missing.
    """
    version = version or __version__
    repo_url = repo_url if repo_url is not None else REPO_URL
    repo_anchor = f'<a href="{html_module.escape(repo_url)}">Source code</a>' if repo_url else ""

    raw = _DEFAULT_HTML
    if os.path.isfile(_ABOUT_HTML_PATH):
        try:
            with open(_ABOUT_HTML_PATH, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            pass

    return (
        raw.replace("{{LAUNCHER_NAME}}", html_module.escape(launcher_name))
        .replace("{{VERSION}}", html_module.escape(version))
        .replace("{{REPO_ANCHOR}}", repo_anchor)
    )
