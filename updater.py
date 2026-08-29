"""Background GitHub Releases updater for packaged FlowTodo builds."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from PySide6.QtCore import QObject, Signal, Slot

from version import APP_VERSION


REPOSITORY = "inksans114/FlowTodo-FluentUI-version"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
RELEASES_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=20"
RELEASES_ATOM_URL = f"{RELEASES_URL}.atom"
USER_AGENT = f"FlowTodo-Updater/{APP_VERSION}"
DOWNLOAD_EXTENSIONS = (".zip", ".msi", ".exe")
MAX_DOWNLOAD_BYTES = 1_500 * 1024 * 1024


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    size: int = 0


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    title: str
    page_url: str
    assets: tuple[ReleaseAsset, ...]
    prerelease: bool = False


def version_key(value: str) -> tuple[int, ...]:
    """Convert tags such as ``v1.2.0`` or ``FlowTodo-1.2`` to comparable keys."""
    match = re.search(r"(?<!\d)(\d+(?:\.\d+){0,3})(?!\d)", str(value or ""))
    if not match:
        return ()
    parts = [int(part) for part in match.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    candidate_key = version_key(candidate)
    current_key = version_key(current)
    if not candidate_key or not current_key:
        return False
    length = max(len(candidate_key), len(current_key))
    return candidate_key + (0,) * (length - len(candidate_key)) > current_key + (0,) * (length - len(current_key))


def select_windows_asset(assets: tuple[ReleaseAsset, ...] | list[ReleaseAsset]) -> ReleaseAsset | None:
    """Choose a complete Windows package and ignore GitHub source archives."""
    machine = platform.machine().lower()
    scored: list[tuple[int, ReleaseAsset]] = []
    for asset in assets:
        name = asset.name.lower()
        suffix = Path(name).suffix
        if suffix not in DOWNLOAD_EXTENSIONS:
            continue
        if "source" in name or "/archive/refs/" in asset.url.lower():
            continue
        if suffix == ".exe" and not any(word in name for word in ("setup", "install", "installer")):
            continue
        if suffix == ".zip" and "flowtodo" not in name:
            continue
        score = {".zip": 40, ".msi": 35, ".exe": 30}[suffix]
        if "flowtodo" in name:
            score += 20
        if "windows" in name or re.search(r"(^|[-_.])win(?:32|64)?($|[-_.])", name):
            score += 16
        if machine in ("amd64", "x86_64") and any(word in name for word in ("x64", "amd64", "x86_64")):
            score += 8
        if "portable" in name:
            score += 4
        scored.append((score, asset))
    return max(scored, key=lambda item: item[0])[1] if scored else None


def safe_path_component(value: str, fallback: str = "update") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", str(value or "")).strip(" .")
    return cleaned or fallback


def validate_zip_package(path: Path) -> None:
    """Reject unsafe or incomplete archives before handing them to PowerShell."""
    try:
        with zipfile.ZipFile(path) as archive:
            files = [entry for entry in archive.infolist() if not entry.is_dir()]
            for entry in files:
                member = Path(entry.filename.replace("\\", "/"))
                if member.is_absolute() or ".." in member.parts:
                    raise RuntimeError("更新压缩包包含不安全的文件路径")
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError("更新压缩包不能包含符号链接")
            if not any(Path(entry.filename).name.lower() == "flowtodo.exe" for entry in files):
                raise RuntimeError("更新压缩包中缺少 FlowTodo.exe")
            bad_file = archive.testzip()
            if bad_file:
                raise RuntimeError(f"更新压缩包损坏：{bad_file}")
    except zipfile.BadZipFile as exc:
        raise RuntimeError("下载的更新包不是有效 ZIP 文件") from exc


def _request_bytes(url: str, timeout: int = 15) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json, application/atom+xml, text/html;q=0.9, */*;q=0.8",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _release_from_api(item: dict) -> ReleaseInfo:
    assets = tuple(
        ReleaseAsset(
            name=str(asset.get("name") or ""),
            url=str(asset.get("browser_download_url") or ""),
            size=int(asset.get("size") or 0),
        )
        for asset in item.get("assets", [])
        if asset.get("name") and asset.get("browser_download_url")
    )
    return ReleaseInfo(
        tag=str(item.get("tag_name") or ""),
        title=str(item.get("name") or item.get("tag_name") or "FlowTodo 更新"),
        page_url=str(item.get("html_url") or RELEASES_URL),
        assets=assets,
        prerelease=bool(item.get("prerelease")),
    )


def _assets_from_expanded_page(tag: str) -> tuple[ReleaseAsset, ...]:
    encoded_tag = urllib.parse.quote(tag, safe="")
    url = f"https://github.com/{REPOSITORY}/releases/expanded_assets/{encoded_tag}"
    html = _request_bytes(url).decode("utf-8", errors="replace")
    matches = re.findall(r'href="([^"]+/releases/download/[^"]+)"[^>]*>', html, flags=re.I | re.S)
    assets: list[ReleaseAsset] = []
    for href in matches:
        clean_href = href.replace("&amp;", "&")
        name = urllib.parse.unquote(clean_href.rstrip("/").rsplit("/", 1)[-1])
        assets.append(ReleaseAsset(name=name, url=urllib.parse.urljoin("https://github.com", clean_href)))
    return tuple(assets)


def _releases_from_atom() -> list[ReleaseInfo]:
    root = ElementTree.fromstring(_request_bytes(RELEASES_ATOM_URL))
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    releases: list[ReleaseInfo] = []
    for entry in root.findall("atom:entry", namespace):
        title = entry.findtext("atom:title", default="FlowTodo 更新", namespaces=namespace).strip()
        link_element = entry.find("atom:link[@rel='alternate']", namespace)
        page_url = link_element.get("href", "") if link_element is not None else ""
        tag = urllib.parse.unquote(page_url.rstrip("/").rsplit("/", 1)[-1])
        if not version_key(tag):
            continue
        releases.append(
            ReleaseInfo(
                tag=tag,
                title=title,
                page_url=page_url or f"{RELEASES_URL}/tag/{urllib.parse.quote(tag)}",
                assets=_assets_from_expanded_page(tag),
                prerelease="pre-release" in title.lower() or "prerelease" in title.lower(),
            )
        )
    return releases


def fetch_latest_release() -> ReleaseInfo | None:
    """Read releases from the API, falling back to GitHub's public Atom feed."""
    releases: list[ReleaseInfo] = []
    try:
        payload = json.loads(_request_bytes(RELEASES_API_URL).decode("utf-8"))
        if isinstance(payload, list):
            releases = [_release_from_api(item) for item in payload if isinstance(item, dict) and not item.get("draft")]
    except (OSError, ValueError, TypeError, urllib.error.URLError):
        releases = _releases_from_atom()
    valid = [release for release in releases if version_key(release.tag)]
    return max(valid, key=lambda release: version_key(release.tag), default=None)


def is_packaged_build() -> bool:
    return bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


class UpdateManager(QObject):
    """Check, download, and hand an update to a detached Windows updater."""

    statusChanged = Signal(str, str, str)
    downloadProgress = Signal(int)
    installReady = Signal(str, str, str)
    quitRequested = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._busy = False
        self.installReady.connect(self._install_downloaded_update)

    @Slot()
    def check_for_updates(self) -> None:
        if self._busy:
            return
        self._busy = True
        threading.Thread(target=self._check_worker, name="FlowTodoUpdateCheck", daemon=True).start()

    def _check_worker(self) -> None:
        download_started = False
        try:
            release = fetch_latest_release()
            if release is None or not is_newer_version(release.tag):
                return
            asset = select_windows_asset(release.assets)
            if asset is None:
                self.statusChanged.emit(
                    "warning",
                    f"发现 FlowTodo {release.tag}",
                    "新版本尚未提供 Windows 安装包，请稍后查看 GitHub Releases。",
                )
                return
            if not is_packaged_build():
                self.statusChanged.emit(
                    "info",
                    f"发现 FlowTodo {release.tag}",
                    "当前从源代码运行，自动替换已跳过；打包版会自动下载并安装。",
                )
                return
            self.statusChanged.emit("info", f"正在更新到 {release.tag}", f"正在下载 {asset.name}")
            download_started = True
            downloaded = self._download_asset(asset, release.tag)
            self.installReady.emit(str(downloaded), Path(asset.name).suffix.lower(), release.tag)
        except Exception as exc:
            if download_started:
                self.statusChanged.emit("warning", "更新下载失败", str(exc))
        finally:
            self._busy = False

    def _download_asset(self, asset: ReleaseAsset, tag: str) -> Path:
        update_dir = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "FlowTodo" / "updates" / safe_path_component(tag)
        update_dir.mkdir(parents=True, exist_ok=True)
        safe_name = safe_path_component(asset.name, "FlowTodo-update.zip")
        destination = update_dir / safe_name
        temporary = destination.with_suffix(destination.suffix + ".part")
        parsed_url = urllib.parse.urlparse(asset.url)
        expected_prefix = f"/{REPOSITORY}/releases/download/"
        if parsed_url.scheme != "https" or parsed_url.hostname != "github.com" or not parsed_url.path.startswith(expected_prefix):
            raise RuntimeError("Release 返回了不受信任的下载地址")
        request = urllib.request.Request(asset.url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response, temporary.open("wb") as handle:
                total = int(response.headers.get("Content-Length") or asset.size or 0)
                if total > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError("更新包体积异常，已停止下载")
                received = 0
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > MAX_DOWNLOAD_BYTES:
                        raise RuntimeError("更新包超过允许的最大体积")
                    handle.write(chunk)
                    if total:
                        self.downloadProgress.emit(min(100, int(received * 100 / total)))
            if received == 0:
                raise RuntimeError("更新包内容为空")
            if total and received != total:
                raise RuntimeError("更新包下载不完整")
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        if destination.suffix.lower() == ".zip":
            try:
                validate_zip_package(temporary)
            except RuntimeError:
                temporary.unlink(missing_ok=True)
                raise
        os.replace(temporary, destination)
        self.downloadProgress.emit(100)
        return destination

    @Slot(str, str, str)
    def _install_downloaded_update(self, package_path: str, package_type: str, tag: str) -> None:
        try:
            package = Path(package_path).resolve()
            if package_type == ".zip":
                self._launch_zip_updater(package)
            elif package_type == ".msi":
                subprocess.Popen(["msiexec.exe", "/i", str(package), "/passive"], close_fds=True)
            elif package_type == ".exe":
                subprocess.Popen([str(package)], close_fds=True)
            else:
                raise RuntimeError(f"不支持的更新包格式：{package_type}")
            self.statusChanged.emit("success", f"FlowTodo {tag} 已下载", "应用将退出并完成更新，然后自动重新打开。")
            self.quitRequested.emit()
        except Exception as exc:
            self.statusChanged.emit("error", "无法安装更新", str(exc))

    @staticmethod
    def _launch_zip_updater(package: Path) -> None:
        executable = Path(sys.executable).resolve()
        install_dir = executable.parent
        script_path = Path(tempfile.gettempdir()) / f"FlowTodo-update-{uuid.uuid4().hex}.ps1"
        script = r'''param(
    [int]$FlowTodoProcessId,
    [string]$Archive,
    [string]$Target,
    [string]$ExecutableName
)
$ErrorActionPreference = "Stop"
try {
    $deadline = (Get-Date).AddSeconds(120)
    while (Get-Process -Id $FlowTodoProcessId -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) { throw "等待 FlowTodo 退出超时" }
        Start-Sleep -Milliseconds 400
    }
    $staging = Join-Path ([System.IO.Path]::GetTempPath()) ("FlowTodo-stage-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    Expand-Archive -LiteralPath $Archive -DestinationPath $staging -Force
    $entries = @(Get-ChildItem -LiteralPath $staging -Force)
    $source = $staging
    if ($entries.Count -eq 1 -and $entries[0].PSIsContainer) { $source = $entries[0].FullName }
    $newExecutable = Join-Path $source $ExecutableName
    if (-not (Test-Path -LiteralPath $newExecutable)) { throw "更新包中缺少 $ExecutableName" }
    & robocopy.exe $source $Target /MIR /R:3 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -gt 7) { throw "复制更新文件失败，robocopy 返回 $LASTEXITCODE" }
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath (Join-Path $Target $ExecutableName) -WorkingDirectory $Target
} catch {
    $message = $_.Exception.Message.Replace('"', "'")
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("FlowTodo 更新失败：`n$message", "FlowTodo 更新", "OK", "Error") | Out-Null
} finally {
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
'''
        script_path.write_text(script, encoding="utf-8-sig")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", str(script_path),
                "-FlowTodoProcessId", str(os.getpid()),
                "-Archive", str(package),
                "-Target", str(install_dir),
                "-ExecutableName", executable.name,
            ],
            creationflags=creation_flags,
            close_fds=True,
        )
