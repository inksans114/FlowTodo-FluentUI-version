"""Mac-only build. --check parses inputs without installing or compiling anything."""
from __future__ import annotations

import argparse
import json
import os
import platform
import plistlib
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.macos_recipe import check_source, RESOURCE_DIRS
from version import APP_VERSION


def verify_bundle(app):
    resources = app / 'Contents/Resources'
    with (app / 'Contents/Info.plist').open('rb') as handle:
        info = plistlib.load(handle)
    for key in ('NSCameraUsageDescription', 'NSMicrophoneUsageDescription', 'NSLocalNetworkUsageDescription'):
        if not info.get(key):
            raise RuntimeError('Missing permission description: ' + key)
    executable = app / 'Contents/MacOS' / info['CFBundleExecutable']
    arches = subprocess.check_output(['lipo', '-archs', str(executable)], text=True).strip().split()
    if arches != ['arm64']:
        raise RuntimeError('Unexpected executable architecture: ' + str(arches))
    for directory in RESOURCE_DIRS:
        for source in (ROOT / directory).rglob('*'):
            if source.is_file() and not any(part in ('__pycache__', '.DS_Store') for part in source.parts) and not (resources / source.relative_to(ROOT)).is_file():
                raise RuntimeError('Bundle resource missing: ' + str(source.relative_to(ROOT)))
    if not (resources / 'RinUI/qmldir').is_file():
        raise RuntimeError('Local patched RinUI QML module was not collected.')
    if not any(path.is_file() for path in app.rglob('QtWebEngineProcess')):
        raise RuntimeError('Qt WebEngine helper was not collected.')
    if not any(path.is_file() for path in app.rglob('libqcocoa.dylib')):
        raise RuntimeError('Qt Cocoa platform plugin was not collected.')
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    subprocess.run(['plutil', '-lint', str(app / 'Contents/Info.plist')], check=True)
    with tempfile.TemporaryDirectory(prefix='flowtodo-mac-smoke-') as temporary:
        env = dict(os.environ, FLOWTODO_DATA_DIR=str(Path(temporary) / 'data'),
                   FLOWTODO_RINUI_CONFIG_DIR=str(Path(temporary) / 'RinUI/config'),
                   QT_QPA_PLATFORM='offscreen')
        result = subprocess.run([str(executable), '--smoke-test'], env=env,
                                capture_output=True, text=True, timeout=60)
        print(result.stdout)
        if result.returncode:
            raise RuntimeError('Packaged app startup failed:\n' + result.stderr[-5000:])
    print('[OK] arm64 app, permissions, resources, Qt helpers, signature and isolated startup.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    check_source()
    from tools.prepare_supervision_models import verify
    verify()
    if args.check:
        print('[INFO] No compilation started. Actual build requires Apple Silicon macOS and Python 3.12.')
        return
    if sys.platform != 'darwin' or platform.machine() != 'arm64' or sys.version_info[:2] != (3, 12):
        raise RuntimeError('Use native Apple Silicon macOS with Python 3.12; Windows cannot build this app.')
    output = ROOT / 'dist' / ('macos-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / 'vendor'), str(ROOT))))
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                    '--distpath', str(output), '--workpath', str(output / 'work'),
                    str(ROOT / 'packaging/macos/FlowTodo.spec')], cwd=ROOT, env=env, check=True)
    app = output / 'FlowTodo.app'
    verify_bundle(app)
    release = output / f'FlowTodo-macOS-arm64-{APP_VERSION}-test.zip'
    # ditto retains symlinks and executable permissions inside .app frameworks.
    subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(release)], check=True)
    print(json.dumps({'app': str(app), 'zip': str(release), 'notarized': False}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
