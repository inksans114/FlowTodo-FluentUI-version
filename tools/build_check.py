"""Read-only build checks; create a fresh output directory only when requested."""

from __future__ import annotations

import argparse
import ast
import importlib
import platform
import re
import struct
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor"))

APP_FILES = (
    "qml/components/AccountAvatar.qml", "qml/components/AvatarCropDialog.qml", "qml/components/StudioTokens.qml",
    "qml/pages/UserAccount.qml", "qml/components/AccountMenu.qml", "qml/components/AccountQuota.qml",
    "qml/components/InlineHelp.qml", "qml/components/QuietMenu.qml", "qml/components/JourneySpinBox.qml",
    "qml/pages/TaskRelationsPage.qml", "qml/pages/TaskEditorPage.qml", "qml/pages/RelationPrepPage.qml",
    "qml/components/TaskGraphCanvas.qml", "qml/components/TaskRelationsButton.qml", "qml/components/RelationCompletionDialog.qml",
    "qml/components/FlowPreparationDialog.qml", "qml/components/FlowInvalidDialog.qml",
    "qml/FocusStudioWindow.qml", "qml/pages/AiPlanWorkspace.qml", "qml/i18n/qmldir", "qml/i18n/I18n.qml",
    "qml/Main.qml", "qml/pages/FocusJourney.qml", "qml/pages/FocusWorkspace.qml", "qml/pages/ArchivedTasks.qml",
    "qml/pages/QuickCapture.qml", "qml/pages/AiGuidedCapture.qml", "qml/pages/AiSavedPlans.qml", "qml/components/VoiceCapture.qml",
    "qml/pages/SupervisionWorkspace.qml", "qml/SupervisionWindow.qml", "qml/components/SupervisionPanel.qml",
    "supervision-models/pose_landmarker_lite.task", "supervision-models/efficientdet_lite0.tflite",
    "supervision-models/hand_landmarker.task", "supervision-models/face_landmarker.task", "supervision-web/phone.html",
    "tools/allow_phone_camera.ps1",
    "supervision-models/manifest.json", "supervision-models/NOTICE.md",
    "vendor/RinUI/__init__.py", "vendor/RinUI/qmldir",
    "i18n/en_US.json", "i18n/zh_TW.json", "logopromax.ico", "audio.mp3",
    "focus-studio/index.html", "focus-studio/studio.js", "focus-studio/studio.css",
    "focus-studio/scene3d.js", "focus-studio/depth-renderer.js",
    "focus-studio/ambience.js", "focus-studio/assets/tree.svg",
    "focus-studio/assets/room.svg", "focus-studio/assets/rain.wav", "focus-studio/assets/reward.wav",
    "focus-studio/assets/NOTICE.md",
)
WEB_RESOURCES = (
    "icudtl.dat", "qtwebengine_resources.pak", "qtwebengine_resources_100p.pak",
    "qtwebengine_resources_200p.pak", "v8_context_snapshot.bin",
)


def require_files(root: Path, names: tuple[str, ...]) -> None:
    missing = [name for name in names if not (root / name).is_file() or not (root / name).stat().st_size]
    if missing:
        raise RuntimeError(f"Missing or empty files in {root}: " + ", ".join(missing))


def check_package_config() -> None:
    import yaml

    path = ROOT / "tools/supervision.nuitka-package.config.yml"
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as error:
        raise RuntimeError(f"Invalid Nuitka YAML: {error}") from error
    if not isinstance(config, list) or not config:
        raise RuntimeError("Nuitka package configuration must be a nonempty list.")
    for entry in config:
        if not isinstance(entry, dict) or not isinstance(entry.get("module-name"), str):
            raise RuntimeError("Nuitka package entry must have a module-name.")
        for section in ("data-files", "dlls"):
            if section in entry and (not isinstance(entry[section], list)
                                     or any(not isinstance(item, dict) for item in entry[section])):
                raise RuntimeError(f"Nuitka {entry['module-name']}: {section} must be a list of objects.")
    print("[OK] Nuitka package configuration YAML and section structure.")


def check_source(builder="nuitka") -> None:
    # Registry restrictions can leave platform.machine() empty on Windows.
    # The Python build target remains available without registry access.
    import sysconfig
    machine = platform.machine().lower() or sysconfig.get_platform().lower().removeprefix("win-")
    if sys.platform != "win32" or struct.calcsize("P") != 8 or machine not in ("amd64", "x86_64"):
        raise RuntimeError("This script builds Windows x64 packages; use 64-bit x64 Python.")
    if sys.version_info < (3, 10):
        raise RuntimeError("Use Python 3.10 or newer. Python 3.12 x64 is recommended.")
    require_files(ROOT, APP_FILES)
    if builder == "nuitka":
        check_package_config()
    # Keep the batch file as the single list of explicitly compiled app modules.
    # Parse source without importing it: preflight must not start application code.
    build_script = (ROOT / "build_nuitka.bat").read_text(encoding="utf-8-sig")
    modules = re.findall(r"--include-module=([A-Za-z_][A-Za-z_0-9.]*)", build_script)
    if not modules:
        raise RuntimeError("The build script has no explicit application modules.")
    # win32crypt is a pywin32 extension, not a project .py source file.
    external_modules = {"win32crypt"}
    source_files = ("app.py",) + tuple(name.replace(".", "/") + ".py" for name in modules if name not in external_modules)
    require_files(ROOT, source_files)
    for name in source_files:
        try:
            ast.parse((ROOT / name).read_text(encoding="utf-8-sig"), filename=name)
        except (SyntaxError, UnicodeError) as error:
            raise RuntimeError(f"Invalid application source {name}: {error}") from error
    print(f"[OK] Entry point and {len(modules)} explicit application modules passed source checks.")
    for module in (
        "mediapipe", "rapidocr_onnxruntime", "onnxruntime", "numpy", "PIL.ImageGrab",
        "cryptography", "qrcode",
        "PyInstaller" if builder == "pyinstaller" else "nuitka", "RinUI", "darkdetect", "win32api", "win32crypt", "win32com.client", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.QtWidgets", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore",
        "PySide6.QtWebChannel", "PySide6.QtNetwork", "PySide6.QtMultimedia",
    ):
        try:
            importlib.import_module(module)
        except (ImportError, OSError) as error:
            raise RuntimeError(f"Cannot import {module}: {error}") from error
    if builder == "pyinstaller":
        import PyInstaller
        if int(PyInstaller.__version__.split(".")[0]) != 6:
            raise RuntimeError("This build script requires PyInstaller 6.x.")
    from PySide6 import __version__ as qt_version
    from PySide6.QtCore import QLibraryInfo
    from version import APP_VERSION
    from tools.prepare_supervision_models import verify
    verify()
    import rapidocr_onnxruntime
    ocr_models = Path(rapidocr_onnxruntime.__file__).parent / "models"
    if len(list(ocr_models.glob("*.onnx"))) < 3:
        raise RuntimeError("The local screen OCR models are missing.")

    qt_numbers = tuple(int(part) for part in qt_version.split(".")[:3])
    if not (qt_numbers >= (6, 11, 1) and qt_numbers < (7, 0, 0)):
        raise RuntimeError(f"PySide6 {qt_version} does not match requirements.txt.")
    data = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.DataPath))
    executables = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath))
    translations = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    require_files(executables, ("QtWebEngineProcess.exe",))
    require_files(data / "resources", WEB_RESOURCES)
    require_files(translations / "qtwebengine_locales", ("en-US.pak",))
    if not list((plugins / "multimedia").glob("*.dll")):
        raise RuntimeError("Qt multimedia plugins are missing; rain audio cannot be packaged.")
    print(f"[OK] FlowTodo {APP_VERSION}; Python {platform.python_version()}; PySide6 {qt_version}")
    print("[OK] QML, local scenes, rain audio, WebEngine process/resources and multimedia plugins.")
    print("[OK] Local supervision camera and OCR models/runtime.")


def check_package(package: Path) -> None:
    # Python modules are compiled into the executable, not copied as data files.
    package_files = tuple(name for name in APP_FILES if not name.endswith(".py"))
    require_files(package, ("FlowTodo.exe",) + package_files)
    for pattern, label in (("**/mediapipe/tasks/c/*.dll", "MediaPipe native runtime"),
                           ("**/rapidocr_onnxruntime/models/*.onnx", "Screen OCR models"),
                           ("**/onnxruntime/capi/*.dll", "ONNX native runtime")):
        if not any(package.glob(pattern)):
            raise RuntimeError(f"The built package is missing {label}.")
    # Nuitka's PySide6 plugin currently places Chromium resources beside the exe.
    # Also accept the resources/ layout for compatible future plugin versions.
    if not any(all((base / name).is_file() for name in WEB_RESOURCES)
               for base in (package, package / "resources", package / "PySide6/resources",
                            package / "PySide6/Qt/resources")):
        raise RuntimeError("The built package is missing WebEngine .pak/ICU/snapshot resources.")
    for pattern, label in (
        ("**/QtWebEngineProcess.exe", "WebEngine subprocess"),
        ("**/qtwebengine_locales/en-US.pak", "WebEngine locales"),
        ("**/multimedia/*.dll", "Qt multimedia plugins"),
        ("**/platforms/qwindows.dll", "Qt Windows platform plugin"),
    ):
        if not any(package.glob(pattern)):
            raise RuntimeError(f"The built package is missing {label}.")
    print(f"[OK] Release package resources verified: {package}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--builder", choices=("nuitka", "pyinstaller"), default="nuitka")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-output", action="store_true")
    mode.add_argument("--package-root", type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.prepare_output:
            output = ROOT / ("dist-pyinstaller" if arguments.builder == "pyinstaller" else "dist")
            output.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            print(tempfile.mkdtemp(prefix=f"build-{stamp}-", dir=output))
        elif arguments.package_root:
            check_package(arguments.package_root.resolve())
        else:
            check_source(arguments.builder)
    except (RuntimeError, OSError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
