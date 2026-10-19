"""Trim only development files and unsupported translations from a release."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def trim(package, apply=False):
    package = Path(package).resolve(strict=True)
    if not package.is_relative_to((ROOT / "dist").resolve()) or package.name != "app.dist":
        raise ValueError("Expected an app.dist directory inside this project's dist directory")
    if not (package / "FlowTodo.exe").is_file():
        raise ValueError("Missing FlowTodo.exe")
    files = [path for path in package.rglob("*") if path.is_file()]
    before = sum(path.stat().st_size for path in files)
    candidates = []
    for path in files:
        relative = path.relative_to(package)
        reason = None
        if path.name.endswith(".debug.pak") and path.with_name(path.name.replace(".debug.pak", ".pak")).is_file():
            reason = "Duplicate debug resource; release counterpart present"
        elif path.suffix.lower() in (".lib", ".exp", ".pdb", ".ilk"):
            reason = "Development library or debug symbols"
        elif relative.parts[:2] == ("PySide6", "translations"):
            if path.suffix == ".qm" and not re.search(r"_(en(?:_[A-Z]+)?|zh(?:_[A-Z]+)?)\.qm$", path.name):
                reason = "Qt translation outside supported English/Chinese languages"
            elif path.suffix == ".pak" and path.parent.name == "qtwebengine_locales" and path.stem not in ("en-US", "en-GB", "zh-CN", "zh-TW"):
                reason = "WebEngine translation outside supported English/Chinese languages"
        if reason:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(package) or path.is_symlink():
                raise ValueError(f"Unsafe cleanup path: {path}")
            candidates.append({"file": relative.as_posix(), "bytes": path.stat().st_size, "reason": reason})
    report = {"package": str(package), "applied": apply, "beforeBytes": before,
              "removedBytes": sum(item["bytes"] for item in candidates), "files": candidates}
    # Check all candidates before modifying any file; delete files only, never trees.
    if apply:
        for item in candidates:
            (package / item["file"]).unlink()
        (package.parent / "trim-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["afterBytes"] = before - report["removedBytes"]
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = trim(args.package, args.apply)
    print(json.dumps({key: value for key, value in result.items() if key != "files"}, ensure_ascii=False))
    print(f"Files selected: {len(result['files'])}")
