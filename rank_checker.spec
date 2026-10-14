# Run: python -m PyInstaller --clean --noconfirm rank_checker.spec
from pathlib import Path

root = Path(SPECPATH)
browsers = root / 'browsers'
if not browsers.is_dir() or not any(browsers.glob('chromium-*')):
    raise SystemExit('Install Chromium into ./browsers first; see README packaging instructions.')

a = Analysis(
    [str(root / 'app.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'assets'), 'assets'), (str(browsers), 'browsers')],
    hiddenimports=['playwright.sync_api'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='搜索排名检查器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(root / 'assets' / 'app.ico'),
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name='搜索排名检查器',
)
