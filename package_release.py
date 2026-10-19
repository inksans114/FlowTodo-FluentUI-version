"""Create the Windows ZIP consumed by FlowTodo's automatic updater."""

from __future__ import annotations

import os
import sys
import tempfile
import zipfile
from pathlib import Path

from version import APP_VERSION


def create_release_archive(executable_path: str | Path) -> Path:
    executable = Path(executable_path).resolve()
    if not executable.is_file() or executable.name.lower() != "flowtodo.exe":
        raise FileNotFoundError(f"FlowTodo.exe not found: {executable}")
    package_dir = executable.parent
    output_base = package_dir.parent / f"FlowTodo-Windows-x64-{APP_VERSION}"
    archive = Path(f"{output_base}.zip")
    handle, temporary = tempfile.mkstemp(prefix="release-", suffix=".zip.tmp", dir=package_dir.parent)
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9, allowZip64=True) as output:
            for source in sorted(package_dir.rglob("*")):
                if source.is_file():
                    output.write(source, source.relative_to(package_dir.parent).as_posix())
        os.replace(temporary, archive)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return archive


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: package_release.py <path-to-FlowTodo.exe>")
    result = create_release_archive(sys.argv[1])
    print(result)
