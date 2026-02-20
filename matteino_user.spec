# PyInstaller spec for Matteino Launcher (user)
# Run from project root: pyinstaller matteino_user.spec
# Executable name and icon: launcher_config/user.config.json (if present) overrides launcher_config/defaults/user.default.json.

import json
import os
import re

_spec_dir = os.path.dirname(os.path.abspath(SPEC))
_defaults_dir = os.path.join(_spec_dir, 'launcher_config', 'defaults')
with open(os.path.join(_defaults_dir, 'user.default.json'), 'r', encoding='utf-8') as f:
    _cfg = json.load(f)
_user_cfg_path = None
for _path in (os.path.join(_spec_dir, 'launcher_config', 'user.config.json'), os.path.join(_spec_dir, 'user.config.json')):
    if os.path.isfile(_path):
        with open(_path, 'r', encoding='utf-8') as f:
            _cfg.update(json.load(f))
        _user_cfg_path = _path
        break

# Executable name: launcher_name sanitized + "-User" (e.g. "Matteino Launcher" -> "Matteino-Launcher-User")
_launcher_name = _cfg.get('launcher_name', 'Matteino Launcher')
EXE_NAME_USER = re.sub(r'[^\w\-]', '-', _launcher_name).strip('-') + '-User'

# Icon: icon_path from config, relative to project root; prefer .ico for Windows
_icon_rel = _cfg.get('icon_path', 'launcherUser/resources/images/icon.png')
_icon_abs = os.path.join(_spec_dir, _icon_rel)
if not os.path.isfile(_icon_abs) and _icon_rel.endswith('.png'):
    _icon_dir = os.path.dirname(_icon_abs)
    for _f in os.listdir(_icon_dir) if os.path.isdir(_icon_dir) else []:
        if _f.endswith('.ico'):
            _icon_abs = os.path.join(_icon_dir, _f)
            break
EXE_ICON_USER = _icon_abs if os.path.isfile(_icon_abs) else None

# Data files: defaults + packager config (shipped with exe) + custom resources + auth templates
launcher_config = 'launcher_config'
user_images = 'launcherUser/resources/images'
resources_about = 'resources/about.html'
auth_templates = 'launcherUser/auth/templates'
datas_user = [
    (os.path.join(_spec_dir, launcher_config, 'defaults', 'user.default.json'), os.path.join(launcher_config, 'defaults')),
    (os.path.join(_spec_dir, resources_about), 'resources'),
    (os.path.join(_spec_dir, user_images), user_images),
    (os.path.join(_spec_dir, auth_templates), auth_templates),
]
if _user_cfg_path:
    datas_user.append((_user_cfg_path, launcher_config))
# Bundle custom logo/icon/loading image from config if they exist (relative paths only)
for _key in ('logo_path', 'icon_path', 'loading_image_path'):
    _rel = _cfg.get(_key)
    if _rel and not os.path.isabs(_rel):
        _full = os.path.join(_spec_dir, _rel)
        if os.path.isfile(_full):
            _dest = os.path.dirname(_rel)
            if (os.path.join(_spec_dir, _rel), _dest) not in [(d[0], d[1]) for d in datas_user]:
                datas_user.append((_full, _dest))

block_cipher = None

a = Analysis(
    ['launcherUser/main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas_user,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'minecraft_launcher_lib',
        'minecraft_launcher_lib.microsoft_account',
        'requests',
        'psutil',
        'src.common',
        'src.common.config',
        'src.common.paths',
        'src.common.version',
        'src.common.about',
        'src.common.about_dialog',
        'mcstatus',
        'mcstatus.java',
        'nbtlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=EXE_NAME_USER,
    icon=EXE_ICON_USER,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
