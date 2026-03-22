# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec file for TG WS Proxy - macOS.

Build command:
    pyinstaller --clean --distpath dist --workpath build/macos packaging/macos.spec
"""

import os
import sys
from pathlib import Path

block_cipher = None

# Project paths - use os.getcwd() since __file__ is not available in spec context
PROJECT_ROOT = Path(os.getcwd())
PROXY_DIR = PROJECT_ROOT / "proxy"
STATIC_DIR = PROXY_DIR / "static"

# Add project root to path
sys.path.insert(0, str(PROJECT_ROOT))

a = Analysis(
    [str(PROJECT_ROOT / 'macos.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # Include proxy static files
        (str(STATIC_DIR), 'proxy/static') if STATIC_DIR.exists() else (str(PROXY_DIR), 'proxy'),
        # Include config default
        (str(PROJECT_ROOT / 'config.default.json'), '.'),
    ],
    hiddenimports=[
        'proxy.tg_ws_proxy',
        'proxy.constants',
        'proxy.stats',
        'proxy.pluggable_transports',
        'cryptography',
        'cryptography.fernet',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'customtkinter',
        'psutil',
        'pyperclip',
        'flask',
        'flask_cors',
        'qrcode',
        'rich',
        'aiodns',
        'appdirs',
        'rumps',
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

app = BUNDLE(
    EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='TgWsProxy',
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
    ),
    name='TgWsProxy.app',
    icon=None,
    bundle_identifier='com.tgwsproxy.app',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'LSUIElement': 'True',  # Hide dock icon (menu bar app)
    },
)
