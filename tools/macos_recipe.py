"""Pure build metadata shared by Mac preflight and PyInstaller's spec."""
import ast
import plistlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIRS = ('qml', 'focus-studio', 'i18n', 'supervision-models', 'supervision-web')
RESOURCE_FILES = ('logopromax.ico', 'audio.mp3')
HIDDEN_IMPORTS = ('PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtWidgets',
                  'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel',
                  'PySide6.QtNetwork', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
                  'AppKit', 'objc', 'cryptography', 'qrcode', 'mediapipe.tasks.python.vision')


def bundle_info(version):
    return {'CFBundleDisplayName': 'FlowTodo', 'CFBundleShortVersionString': version,
            'CFBundleVersion': version, 'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '13.0',
            'NSCameraUsageDescription': '仅在你开启监督模式后，使用摄像头在本机识别学习姿势；不保存视频。',
            'NSMicrophoneUsageDescription': '仅在你确认云端语音转写后录音，发送到你选择的语音服务。',
            'NSLocalNetworkUsageDescription': '连接同一局域网的手机摄像头，画面仅在电脑本机处理。'}


def resource_entries(root=ROOT):
    """Only explicit app resources; never include user settings or working files."""
    entries = []
    for directory in RESOURCE_DIRS:
        for path in sorted((root / directory).rglob('*')):
            if path.is_file() and not any(part in ('__pycache__', '.DS_Store') for part in path.parts):
                entries.append((str(path), str(path.relative_to(root).parent)))
    entries.extend((str(root / name), '.') for name in RESOURCE_FILES)
    return entries


def check_source(root=ROOT):
    from tools.build_check import APP_FILES
    # Windows-only firewall helper isn't part of the Mac app.
    required = [name for name in APP_FILES if name != 'tools/allow_phone_camera.ps1']
    required += ['requirements-macos.txt', 'packaging/macos/FlowTodo.spec',
                 'packaging/macos/entitlements.plist', 'app_paths.py']
    missing = [name for name in required if not (root / name).is_file() or not (root / name).stat().st_size]
    if missing:
        raise RuntimeError('Missing Mac build inputs: ' + ', '.join(missing))
    for path in list(root.glob('*.py')) + list((root / 'vendor/RinUI').rglob('*.py')):
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    ast.parse((root / 'packaging/macos/FlowTodo.spec').read_text(encoding='utf-8'), filename='FlowTodo.spec')
    with (root / 'packaging/macos/entitlements.plist').open('rb') as handle:
        plistlib.load(handle)
    print('[OK] Mac source, bundle recipe, permissions and application assets.')
