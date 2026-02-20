# PyInstaller spec for Matteino Launcher (admin)
# Run from project root: pyinstaller matteino_admin.spec
# Executable name and icon: admin.config.json (if present) overrides config/defaults/admin.default.json.

import json
import os
import re

_spec_dir = os.path.dirname(os.path.abspath(SPEC))
with open(os.path.join(_spec_dir, 'config/defaults/admin.default.json'), 'r', encoding='utf-8') as f:
    _cfg = json.load(f)
_admin_cfg_path = None
for _path in (os.path.join(_spec_dir, 'admin.config.json'), os.path.join(_spec_dir, 'config/admin.config.json')):
    if os.path.isfile(_path):
        with open(_path, 'r', encoding='utf-8') as f:
            _cfg.update(json.load(f))
        _admin_cfg_path = _path
        break

# Executable name: launcher_name sanitized + "-Admin"
_launcher_name = _cfg.get('launcher_name', 'Matteino Launcher')
EXE_NAME_ADMIN = re.sub(r'[^\w\-]', '-', _launcher_name).strip('-') + '-Admin'

# Icon: icon_path from config; prefer .ico for Windows
_icon_rel = _cfg.get('icon_path', 'launcherAdmin/resources/images/icon.png')
_icon_abs = os.path.join(_spec_dir, _icon_rel)
if not os.path.isfile(_icon_abs) and _icon_rel.endswith('.png'):
    _icon_dir = os.path.dirname(_icon_abs)
    for _f in os.listdir(_icon_dir) if os.path.isdir(_icon_dir) else []:
        if _f.endswith('.ico'):
            _icon_abs = os.path.join(_icon_dir, _f)
            break
EXE_ICON_ADMIN = _icon_abs if os.path.isfile(_icon_abs) else None

config_defaults = 'config/defaults'
admin_images = 'launcherAdmin/resources/images'
admin_translations = 'launcherAdmin/translations'
resources_about = 'resources/about.html'

# Data files: defaults + packager config (shipped with exe) + custom resources from config
datas_admin = [
    (os.path.join(_spec_dir, f'{config_defaults}/admin.default.json'), config_defaults),
    (os.path.join(_spec_dir, resources_about), 'resources'),
    (os.path.join(_spec_dir, admin_images), admin_images),
]
if _admin_cfg_path:
    datas_admin.append((_admin_cfg_path, 'config'))
for _key in ('logo_path', 'icon_path'):
    _rel = _cfg.get(_key)
    if _rel and not os.path.isabs(_rel):
        _full = os.path.join(_spec_dir, _rel)
        if os.path.isfile(_full):
            _dest = os.path.dirname(_rel)
            if (os.path.join(_spec_dir, _rel), _dest) not in [(d[0], d[1]) for d in datas_admin]:
                datas_admin.append((_full, _dest))
_admin_translations_abs = os.path.join(_spec_dir, admin_translations)
if os.path.isdir(_admin_translations_abs):
    for f in os.listdir(_admin_translations_abs):
        if f.endswith('.qm'):
            datas_admin.append((os.path.join(_admin_translations_abs, f), admin_translations))

block_cipher = None

a = Analysis(
    ['launcherAdmin/main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas_admin,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'minecraft_launcher_lib',
        'requests',
        'psutil',
        'src.common',
        'src.common.config',
        'src.common.paths',
        'src.common.version',
        'src.common.about',
        'src.common.about_dialog',
        'src.common.translations',
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
    name=EXE_NAME_ADMIN,
    icon=EXE_ICON_ADMIN,
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
