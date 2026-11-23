# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets')]
binaries = []
hiddenimports = ['docx', 'openpyxl', 'pypdf', 'PIL', 'PIL.Image', 'winocr', 'winrt.windows.media.ocr', 'winrt.windows.graphics.imaging', 'winrt.windows.storage.streams', 'winrt.windows.globalization', 'pymupdf', 'filekeeper.invoice', 'filekeeper.ocr']
hiddenimports += collect_submodules('winrt')
tmp_ret = collect_all('tkinterdnd2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['onnxruntime', 'pymupdf.layout', 'pymupdf_layout', 'pymupdf4llm'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='文件管家',
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
    version='assets/version_info.txt',
    icon=['assets/filekeeper.ico'],
    manifest='assets/app.manifest',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='文件管家',
)
