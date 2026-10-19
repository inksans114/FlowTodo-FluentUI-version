# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

root = Path(SPECPATH).resolve().parents[1]
resources = ['qml', 'focus-studio', 'supervision-models', 'supervision-web', 'i18n',
             'vendor/RinUI', 'logopromax.ico', 'audio.mp3', 'CLASS_WIDGETS_2_LICENSE.txt']
datas = [(str(root / name), name if (root / name).is_dir() else '.') for name in resources]
datas += [(str(root / 'tools/allow_phone_camera.ps1'), 'tools')]
binaries = []
for package in ('mediapipe', 'rapidocr_onnxruntime', 'RinUI'):
    datas += collect_data_files(package)
for package in ('mediapipe', 'onnxruntime'):
    binaries += collect_dynamic_libs(package)
datas += copy_metadata('mediapipe')
hidden = ['win32crypt', 'win32com.client', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore',
          'PySide6.QtWebChannel', 'PySide6.QtNetwork', 'PySide6.QtMultimedia', 'PIL.ImageGrab',
          'mediapipe', 'rapidocr_onnxruntime'] + collect_submodules('mediapipe.tasks.python.vision')
a = Analysis([str(root / 'app.py')], pathex=[str(root), str(root / 'vendor')],
             binaries=binaries, datas=datas, hiddenimports=hidden,
             hookspath=[str(root / 'vendor/RinUI/hooks')], hooksconfig={}, runtime_hooks=[],
             excludes=['playsound', 'mediapipe.tasks.python.test', 'PIL.ImageTk', 'PIL.ImageQt',
                       'PyQt5', 'PyQt6', 'PySide2'], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FlowTodo', debug=False,
          strip=False, upx=False, console=False, icon=str(root / 'logopromax.ico'), contents_directory='.')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FlowTodo')
