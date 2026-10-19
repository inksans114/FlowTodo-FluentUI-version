# Build on Apple Silicon with tools/build_macos.py. This is an onedir .app.
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

root = Path(SPECPATH).resolve().parents[1]
sys.path[:0] = [str(root / 'vendor'), str(root)]
from tools.macos_recipe import resource_entries, bundle_info, HIDDEN_IMPORTS
from version import APP_VERSION

datas = resource_entries(root)
datas += collect_data_files('RinUI', excludes=['config/**', '**/__pycache__/**'])
mp_data, mp_binaries, mp_imports = collect_all('mediapipe',
    filter_submodules=lambda name: '.test' not in name and '.examples' not in name)
datas += mp_data
a = Analysis([str(root / 'app.py')], pathex=[str(root / 'vendor'), str(root)],
    binaries=mp_binaries, datas=datas,
    hiddenimports=list(HIDDEN_IMPORTS) + mp_imports,
    excludes=['win32api', 'win32con', 'win32gui', 'win32com', 'rapidocr_onnxruntime',
              'onnxruntime', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FlowTodo',
    debug=False, strip=False, upx=False, console=False, argv_emulation=False,
    target_arch='arm64', codesign_identity=os.environ.get('FLOWTODO_CODESIGN_IDENTITY') or None,
    entitlements_file=str(root / 'packaging/macos/entitlements.plist'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FlowTodo')
app = BUNDLE(coll, name='FlowTodo.app', icon=str(root / 'logopromax.ico'),
    bundle_identifier='io.github.inksans114.flowtodo', info_plist=bundle_info(APP_VERSION))
