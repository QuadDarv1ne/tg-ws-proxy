# -*- mode: python ; coding: utf-8 -*-
# TG WS Proxy - Windows Build Specification
# Author: Dupley Maxim Igorevich
# © 2026 Dupley Maxim Igorevich. All rights reserved.

import sys
import os

block_cipher = None

# customtkinter ships JSON themes + assets that must be bundled
import customtkinter
ctk_path = os.path.dirname(customtkinter.__file__)

# Rich library for console dashboard
import rich
rich_path = os.path.dirname(rich.__file__)

# Flask for web dashboard
import flask
flask_path = os.path.dirname(flask.__file__)

# Get project root
project_root = os.path.join(os.path.dirname(SPEC), os.pardir)
proxy_dir = os.path.join(project_root, 'proxy')
static_dir = os.path.join(proxy_dir, 'static')

a = Analysis(
    [os.path.join(os.path.dirname(SPEC), os.pardir, 'windows.py')],
    pathex=[],
    binaries=[],
    datas=[
        (ctk_path, 'customtkinter/'),
        (rich_path, 'rich/'),
        (flask_path, 'flask/'),
        (proxy_dir, 'proxy/'),
        (static_dir, 'proxy/static/') if os.path.exists(static_dir) else None,
    ],
    hiddenimports=[
        'pystray._win32',
        'PIL._tkinter_finder',
        'customtkinter',
        'cryptography.hazmat.primitives.ciphers',
        'cryptography.hazmat.primitives.ciphers.algorithms',
        'cryptography.hazmat.primitives.ciphers.modes',
        'cryptography.hazmat.backends.openssl',
        'rich',
        'rich.console',
        'rich.live',
        'rich.table',
        'rich.panel',
        'markdown_it',
        'flask',
        'flask_cors',
        'jinja2',
        'werkzeug',
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

icon_path = os.path.join(os.path.dirname(SPEC), os.pardir, 'icon.ico')
if os.path.exists(icon_path):
    a.datas += [('icon.ico', icon_path, 'DATA')]

# Filter out None from datas
a.datas = [d for d in a.datas if d is not None]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
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
    icon=icon_path if os.path.exists(icon_path) else None,
)
