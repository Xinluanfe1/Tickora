# -*- mode: python ; coding: utf-8 -*-
"""Tickora 的 PyInstaller onedir 构建配置。

用法（由 scripts/build.ps1 调用，或手动执行）：
    python -m PyInstaller --noconfirm --clean --distpath dist --workpath build scripts\\TodoList.spec

相对路径基于本 spec 文件所在目录解析；不包含任何用户数据。
"""

from PyInstaller.utils.hooks import collect_all

_toasts = collect_all("windows_toasts")

a = Analysis(
    ["..\\main.py"],
    pathex=[],
    binaries=_toasts[1],
    datas=[("..\\resources\\brand", "resources\\brand")] + _toasts[0],
    hiddenimports=[
        "winrt.windows.ui.notifications",
        "winrt.windows.data.xml.dom",
        "winrt.windows.foundation",
        "winrt.windows.foundation.collections",
    ] + _toasts[2],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TodoList",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="..\\resources\\brand\\tickora.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TodoList",
)
