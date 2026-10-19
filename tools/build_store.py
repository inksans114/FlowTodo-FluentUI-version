"""Build a clean Win32 payload and validated Microsoft Store MSIX (Windows x64)."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import APP_VERSION


def identity(path=None):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig')) if path else {
        'name': 'FlowTodo.LocalPreview', 'publisher': 'CN=FlowTodoLocalPreview',
        'publisherDisplayName': 'FlowTodo Preview', 'displayName': 'FlowTodo',
        'version': APP_VERSION + '.0.0'}
    for key in ('name', 'publisher', 'publisherDisplayName', 'displayName', 'version'):
        if not isinstance(value.get(key), str) or not value[key].strip() or 'COPY_FROM' in value[key]:
            raise ValueError('Missing Partner Center identity: ' + key)
    if not re.fullmatch(r'[A-Za-z0-9.-]{3,50}', value['name']):
        raise ValueError('Invalid Package/Identity/Name')
    if not value['publisher'].startswith('CN='):
        raise ValueError('Publisher must be copied exactly from Partner Center (CN=...)')
    if not re.fullmatch(r'\d+\.\d+\.\d+\.0', value['version']):
        raise ValueError('Store version must contain four numbers, ending in .0')
    numbers = [int(part) for part in value['version'].split('.')]
    if not 1 <= numbers[0] <= 65535 or any(n > 65535 for n in numbers):
        raise ValueError('Version component out of range')
    return value


def manifest(value):
    namespaces = {'': 'http://schemas.microsoft.com/appx/manifest/foundation/windows10',
                  'uap': 'http://schemas.microsoft.com/appx/manifest/uap/windows10',
                  'rescap': 'http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities'}
    for prefix, uri in namespaces.items(): ET.register_namespace(prefix, uri)
    def tag(name):
        prefix, local = name.split(':') if ':' in name else ('', name)
        return '{' + namespaces[prefix] + '}' + local
    def add(parent, name, **attributes): return ET.SubElement(parent, tag(name), attributes)
    package = ET.Element(tag('Package'), {'IgnorableNamespaces': 'uap rescap'})
    add(package, 'Identity', Name=value['name'], Publisher=value['publisher'], Version=value['version'], ProcessorArchitecture='x64')
    properties = add(package, 'Properties')
    for name, text in [('DisplayName', value['displayName']), ('PublisherDisplayName', value['publisherDisplayName']), ('Logo', 'Assets/StoreLogo.png')]:
        add(properties, name).text = text
    add(add(package, 'Resources'), 'Resource', Language='zh-CN')
    add(add(package, 'Dependencies'), 'TargetDeviceFamily', Name='Windows.Desktop', MinVersion='10.0.19041.0', MaxVersionTested='10.0.26100.0')
    application = add(add(package, 'Applications'), 'Application', Id='FlowTodo', Executable='App/FlowTodo.exe', EntryPoint='Windows.FullTrustApplication')
    visual = add(application, 'uap:VisualElements', DisplayName=value['displayName'], Description='FlowTodo tasks, focus and AI planning', BackgroundColor='transparent', Square150x150Logo='Assets/Square150x150Logo.png', Square44x44Logo='Assets/Square44x44Logo.png')
    add(visual, 'uap:DefaultTile', Wide310x150Logo='Assets/Wide310x150Logo.png', Square310x310Logo='Assets/Square310x310Logo.png', Square71x71Logo='Assets/Square71x71Logo.png')
    add(visual, 'uap:SplashScreen', Image='Assets/SplashScreen.png', BackgroundColor='#FFFFFF')
    extension = add(add(application, 'Extensions'), 'uap:Extension', Category='windows.protocol')
    add(add(extension, 'uap:Protocol', Name='flowtodo'), 'uap:DisplayName').text = 'FlowTodo'
    capabilities = add(package, 'Capabilities')
    add(capabilities, 'Capability', Name='internetClient')
    add(capabilities, 'DeviceCapability', Name='microphone')
    add(capabilities, 'DeviceCapability', Name='webcam')
    add(capabilities, 'rescap:Capability', Name='runFullTrust')
    ET.indent(package)
    return ET.tostring(package, encoding='utf-8', xml_declaration=True)


def assets(folder):
    from PIL import Image
    folder.mkdir(parents=True, exist_ok=True)
    logo = Image.open(ROOT / 'logopromax.ico').convert('RGBA')
    for name, size in {'StoreLogo': (50, 50), 'Square44x44Logo': (44, 44), 'Square71x71Logo': (71, 71),
                       'Square150x150Logo': (150, 150), 'Square310x310Logo': (310, 310),
                       'Wide310x150Logo': (310, 150), 'SplashScreen': (620, 300)}.items():
        canvas = Image.new('RGBA', size)
        icon = logo.copy()
        edge = round(min(size) * .8)
        icon.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        canvas.alpha_composite(icon, ((size[0]-icon.width)//2, (size[1]-icon.height)//2))
        canvas.save(folder / (name + '.png'))


def makeappx(explicit=None):
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file(): raise FileNotFoundError(path)
        return path
    candidates = list((ROOT / 'work/store-sdk/tools').glob('**/x64/makeappx.exe'))
    candidates += list(Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')).glob('Windows Kits/10/bin/*/x64/makeappx.exe'))
    if not candidates: raise RuntimeError('MakeAppx missing. Install Microsoft.Windows.SDK.BuildTools or Windows SDK.')
    return sorted(candidates)[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', type=Path, help='Real Partner Center identity JSON; omitted = clearly marked local preview')
    parser.add_argument('--payload', type=Path, help='Reuse a current, verified FlowTodo folder instead of rebuilding')
    parser.add_argument('--makeappx', type=Path)
    parser.add_argument('--payload-only', action='store_true')
    args = parser.parse_args()
    value = identity(args.identity)
    output = ROOT / 'dist-store' / datetime.now().strftime('build-%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'vendor'))
    if args.payload:
        payload = args.payload.resolve()
    else:
        subprocess.run([sys.executable, str(ROOT / 'tools/build_check.py'), '--builder', 'pyinstaller'], check=True, env=env)
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(output / 'payload'),
                        '--workpath', str(output / 'work'), str(ROOT / 'packaging/windows/FlowTodo.spec')], check=True, env=env)
        payload = output / 'payload/FlowTodo'
    subprocess.run([sys.executable, str(ROOT / 'tools/build_check.py'), '--builder', 'pyinstaller', '--package-root', str(payload)], check=True, env=env)
    (output / 'payload-path.txt').write_text(str(payload), encoding='utf-8')
    if args.payload_only:
        print('PAYLOAD=' + str(payload), flush=True)
        return
    stage = output / 'layout'
    stage.mkdir()
    shutil.copytree(payload, stage / 'App', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.log'))
    # Never ship developer or real-user RinUI settings collected from the source tree.
    for config in (stage / 'App/vendor/RinUI/config', stage / 'App/RinUI/config'):
        if config.exists(): shutil.rmtree(config)
    (stage / 'AppxManifest.xml').write_bytes(manifest(value))
    assets(stage / 'Assets')
    suffix = '' if args.identity else '-PREVIEW-NOT-FOR-UPLOAD'
    target = output / f'FlowTodo-{value["version"]}-x64{suffix}.msix'
    subprocess.run([str(makeappx(args.makeappx)), 'pack', '/d', str(stage), '/p', str(target), '/h', 'SHA256', '/o'], check=True)
    digest = hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()
    report = {'file': str(target), 'sha256': digest, 'bytes': target.stat().st_size, 'identity': value,
              'storeIdentityConfigured': bool(args.identity), 'makeAppxValidation': 'passed',
              'storeCertification': 'not run', 'installedPackageSmokeTest': 'not run',
              'note': 'Unsigned Store submission; Microsoft signs after certification. Preview identity cannot be uploaded.'}
    (output / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'SHA256.txt').write_text(digest + '  ' + target.name + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
