"""Create the Windows ZIP consumed by FlowTodo's automatic updater."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from version import APP_VERSION


def create_release_archive(executable_path: str | Path) -> Path:
    executable = Path(executable_path).resolve()
    if not executable.is_file() or executable.name.lower() != "flowtodo.exe":
        raise FileNotFoundError(f"FlowTodo.exe not found: {executable}")
    package_dir = executable.parent
    output_base = package_dir.parent / f"FlowTodo-Windows-x64-{APP_VERSION}"
    archive = Path(f"{output_base}.zip")
    archive.unlink(missing_ok=True)
    shutil.make_archive(
        str(output_base),
        "zip",
        root_dir=str(package_dir.parent),
        base_dir=package_dir.name,
    )
    return archive


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: package_release.py <path-to-FlowTodo.exe>")
    result = create_release_archive(sys.argv[1])
    print(result)
