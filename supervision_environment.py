"""Read-only readiness checks for the interpreter actually running the app."""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path

from supervision_vision import MODEL_DIR, MODEL_FILES

IMPORT_ERRORS = {}


def bootstrap():
    # Run before Qt's __feature__ import hook is installed. Failure of one
    # optional package must not prevent loading the other, or ordinary tasks.
    for name in ("mediapipe", "rapidocr_onnxruntime"):
        try:
            importlib.import_module(name)
            IMPORT_ERRORS.pop(name, None)
        except Exception as error:
            IMPORT_ERRORS[name] = f"{type(error).__name__}: {error}"[:400]


def package_issue(name):
    if name in IMPORT_ERRORS:
        return f"{name} 未能加载（{IMPORT_ERRORS[name]}）"
    # Compiled modules can be loaded without a spec; don't mistake them for
    # missing dependencies when running a standalone build.
    if name in sys.modules:
        return ""
    try:
        if importlib.util.find_spec(name) is not None:
            return ""
    except (ImportError, ValueError, AttributeError):
        pass
    return f"当前启动环境未安装 {name}"


def availability():
    missing_models = [name for name in MODEL_FILES if not (MODEL_DIR / name).is_file()]
    camera_reason = package_issue("mediapipe")
    if not camera_reason and missing_models:
        camera_reason = "缺少摄像头模型：" + "、".join(missing_models)
    screen_reason = "屏幕巡查目前需要 Windows" if sys.platform != "win32" else package_issue("rapidocr_onnxruntime")
    if not screen_reason:
        try:
            from PIL import ImageGrab
            if "window" not in inspect.signature(ImageGrab.grab).parameters:
                screen_reason = "截图组件版本过旧，需要 Pillow 11.2 或以上"
        except (ImportError, ValueError, AttributeError) as error:
            screen_reason = f"截图组件不可用（{type(error).__name__}）"
    if not screen_reason:
        module = sys.modules.get("rapidocr_onnxruntime")
        if module is not None and getattr(module, "__file__", None):
            model_root = Path(module.__file__).parent / "models"
            if len(list(model_root.glob("*.onnx"))) < 3:
                screen_reason = "缺少本地文字识别模型，请重新安装识别组件"
    frozen = bool(getattr(sys, "frozen", False) or "__compiled__" in globals())
    interpreter = sys.executable
    script = Path(__file__).resolve().parent / "tools" / "setup_supervision.py"
    # This is a displayed PowerShell command only, never run from the UI.
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    return {
        "camera": not camera_reason, "screen": not screen_reason,
        "models": not missing_models, "cameraReason": camera_reason,
        "screenReason": screen_reason, "pythonVersion": sys.version.split()[0],
        "interpreter": interpreter, "packaged": frozen,
        "repairCommand": "" if frozen else "& " + quote(interpreter) + " " + quote(script),
        "repairHint": "请使用包含识别组件的完整安装包。" if frozen else
                      "用当前 Python 运行下方修复命令，完成后重新启动软件。不会打包，也不会开启摄像头。",
    }
