"""Background GitHub Releases updater for packaged FlowTodo builds."""

from __future__ import annotations

import concurrent.futures
import time
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

from i18n_runtime import tr
from version import APP_VERSION
from app_paths import windows_package_family


REPOSITORY = "inksans114/FlowTodo-FluentUI-version"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
RELEASES_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=20"
RELEASES_ATOM_URL = f"{RELEASES_URL}.atom"
USER_AGENT = f"FlowTodo-Updater/{APP_VERSION}"
DOWNLOAD_EXTENSIONS = (".zip", ".msi", ".exe")
DEFAULT_SERVER_MANIFEST = "https://dashboard.cheemsdoge.xyz:24336/updates/latest.json"
MAX_DOWNLOAD_BYTES = 1_500 * 1024 * 1024


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    size: int = 0
    digest: str = ""


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    title: str
    page_url: str
    assets: tuple[ReleaseAsset, ...]
    prerelease: bool = False
    notes: str = ""


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
                    raise RuntimeError(tr("更新压缩包包含不安全的文件路径"))
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError(tr("更新压缩包不能包含符号链接"))
            if not any(Path(entry.filename).name.lower() == "flowtodo.exe" for entry in files):
                raise RuntimeError(tr("更新压缩包中缺少 FlowTodo.exe"))
            bad_file = archive.testzip()
            if bad_file:
                raise RuntimeError(tr("更新压缩包损坏：") + str(bad_file))
    except zipfile.BadZipFile as exc:
        raise RuntimeError(tr("下载的更新包不是有效 ZIP 文件")) from exc


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
            digest=str(asset.get("digest") or ""),
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
        notes=str(item.get("body") or ""),
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
    valid = [release for release in releases if version_key(release.tag) and not release.prerelease]
    return max(valid, key=lambda release: version_key(release.tag), default=None)


def is_packaged_build() -> bool:
    return bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


class UpdateManager(QObject):
    statusChanged=Signal(str,str,str)
    downloadProgress=Signal(int)
    stateChanged=Signal()
    _received=Signal(dict)
    quitRequested=Signal()
    def __init__(self,parent=None,backend=None):
        super().__init__(parent);self.backend=backend;self._busy=False;self.release=None;self.manifest=None;self.asset=None;self._last_check=0;self._was_logged_in=False
        self.cache=Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir())/'FlowTodo'/'updates'
        self._view={'currentVersion':APP_VERSION,'availableVersion':'','status':'idle','message':'启动和登录后检查更新。','progress':0,'notes':'','source':'','packaged':is_packaged_build(),'ready':False}
        self._received.connect(self._receive)
        if backend:backend.accountChanged.connect(self._account_changed)
    def _receive(self,value):self._view.update(value);self.stateChanged.emit()
    def view(self):return {**self._view,'autoDownload':bool(self.setting('updateAutoDownload',True)),'serverUrl':self.setting('updateServerUrl',DEFAULT_SERVER_MANIFEST)}
    def setting(self,key,default):return self.backend.settings_database.get(key,default) if self.backend else default
    def _account_changed(self):
        logged=bool(self.backend._cloud.logged_in())
        if logged and not self._was_logged_in:self.check_for_updates()
        self._was_logged_in=logged
    @Slot()
    def check_for_updates(self,manual=False):
        if windows_package_family():
            self._received.emit({'status':'store','message':'此版本由 Microsoft Store 管理更新，请在商店的下载页面检查更新。','ready':False,'availableVersion':''})
            return
        if self._busy or (not manual and time.time()-self._last_check<600):return
        self._last_check=time.time();self._busy=True;self._received.emit({'status':'checking','message':'正在检查 GitHub 和服务器…'})
        threading.Thread(target=self._check_worker,name='FlowTodoUpdateCheck',daemon=True).start()
    def _check_worker(self):
        try:
            if sys.platform != 'win32':
                release = fetch_latest_release()
                available = bool(release and not release.prerelease and is_newer_version(release.tag))
                message = '发现新版本，请从发布页下载适合当前系统的版本。' if available else '未发现更高的正式版本。'
                self._received.emit({'status': 'available' if available else 'idle',
                                     'availableVersion': release.tag if available else '',
                                     'message': message, 'ready': False, 'source': 'GitHub',
                                     'notes': release.notes if available else ''})
                if available:
                    self.statusChanged.emit('info', message, release.page_url)
                return
            candidates=[];errors=[]
            source=str(self.setting('updateServerUrl',DEFAULT_SERVER_MANIFEST)).strip()
            def from_server():
                from update_files import read_manifest
                if not source:return None
                parsed=urllib.parse.urlsplit(source)
                if parsed.scheme!='https' or parsed.username or parsed.password:raise ValueError('服务器更新清单必须使用 HTTPS。')
                return read_manifest(_request_bytes(source),source)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                tasks={pool.submit(fetch_latest_release):'github',pool.submit(from_server):'server'}
                for future in concurrent.futures.as_completed(tasks):
                    try:
                        value=future.result()
                        if value and tasks[future]=='server':candidates.append((value['version'],'服务器',None,value))
                        elif value and not value.prerelease:candidates.append((value.tag,'GitHub',value,None))
                    except Exception:errors.append(tasks[future])
            candidates=[c for c in candidates if is_newer_version(c[0])]
            if not candidates:
                self._received.emit({'status':'idle','message':'未发现更高的正式版本。'+('部分来源暂时无法连接。' if errors else '')});return
            tag,source_name,release,manifest=max(candidates,key=lambda c:version_key(c[0]));self.release=release;self.manifest=manifest;self.asset=select_windows_asset(release.assets) if release else None
            if release:
                manifest_asset=next((a for a in release.assets if a.name=='FlowTodo-update.json'),None)
                if manifest_asset:
                    from update_files import read_manifest,trusted_url
                    trusted_url(manifest_asset.url,manifest_asset.url)
                    manifest=read_manifest(_request_bytes(manifest_asset.url),manifest_asset.url)
                    if not is_newer_version(manifest['version']) or version_key(manifest['version'])!=version_key(tag):raise ValueError('更新清单版本与发布版本不一致。')
                    self.manifest=manifest
            notes=str((self.manifest or {}).get('notes') or (release.notes if release else ''))[:6000]
            self._received.emit({'status':'available','availableVersion':tag,'source':source_name,'notes':notes,'message':'发现新版本，可以下载；安装将在下次启动时进行。','ready':False})
            if is_packaged_build() and sys.platform=='win32' and self.setting('updateAutoDownload',True):self._download_worker(tag)
        except Exception as error:self._received.emit({'status':'error','message':str(error)[:300]})
        finally:self._busy=False
    @Slot()
    def download_update(self):
        if windows_package_family():return
        if self._busy or not self._view['availableVersion']:return
        if not is_packaged_build() or sys.platform!='win32':self._received.emit({'message':'源码运行模式不替换程序文件；请打包为 Windows 版后使用。'});return
        self._busy=True
        def worker():
            try:self._download_worker(self._view['availableVersion'])
            except Exception as error:self._received.emit({'status':'error','message':str(error)[:300]})
            finally:self._busy=False
        threading.Thread(target=worker,name='FlowTodoUpdateDownload',daemon=True).start()
    def _download_worker(self,tag):
        from update_files import stage_manifest,stage_archive
        if not is_newer_version(tag):return
        stage=self.cache/safe_path_component(tag)/'stage';self._received.emit({'status':'downloading','progress':0,'message':'比对本机文件并下载更新，软件可以继续使用。'})
        progress=lambda n:self._received.emit({'progress':n})
        if self.manifest:stage_manifest(self.manifest,Path(sys.executable).resolve().parent,stage,progress)
        elif self.asset and Path(self.asset.name).suffix.lower()=='.zip':
            archive=self._download_asset(self.asset,tag);stage_archive(archive,tag,Path(sys.executable).resolve().parent,stage)
        else:raise ValueError('发布版本缺少可自动更新的清单或完整 ZIP 包，请从发布页手动安装。')
        self.cache.mkdir(parents=True,exist_ok=True);pending=self.cache/'pending.json';temporary=self.cache/'pending.part'
        temporary.write_text(json.dumps({'version':tag,'stage':str(stage)},ensure_ascii=False),encoding='utf-8');os.replace(temporary,pending)
        self._received.emit({'status':'ready','ready':True,'progress':100,'message':'更新已下载。关闭软件后，下次启动时安装；本地记录与设置保留。'})
        self.statusChanged.emit('success','更新已准备好','下次启动时安装 '+tag+'，现在可以继续使用。')
    def _download_asset(self,asset,tag):
        from update_files import trusted_url,file_hash
        trusted_url(asset.url,asset.url)
        directory=self.cache/safe_path_component(tag);directory.mkdir(parents=True,exist_ok=True);target=directory/safe_path_component(asset.name);temporary=target.with_suffix('.part')
        try:
            request=urllib.request.Request(asset.url,headers={'User-Agent':USER_AGENT})
            with urllib.request.urlopen(request,timeout=30) as response,temporary.open('wb') as output:
                total=int(response.headers.get('Content-Length') or asset.size or 0);received=0
                if total>MAX_DOWNLOAD_BYTES:raise ValueError('更新包体积异常。')
                while True:
                    chunk=response.read(256*1024)
                    if not chunk:break
                    received+=len(chunk)
                    if received>MAX_DOWNLOAD_BYTES:raise ValueError('更新包超过允许体积。')
                    output.write(chunk)
                    if total:self._received.emit({'progress':min(90,int(received*90/total))})
            if not received or total and received!=total:raise ValueError('更新包下载不完整。')
            if asset.digest and file_hash(temporary)!=asset.digest.removeprefix('sha256:'):raise ValueError('更新包校验失败。')
            validate_zip_package(temporary);os.replace(temporary,target);return target
        finally:temporary.unlink(missing_ok=True)
    @staticmethod
    def install_on_start():
        if windows_package_family():return False
        if not is_packaged_build() or sys.platform!='win32':return False
        from update_installer import launch_pending
        cache=Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir())/'FlowTodo'/'updates'
        try:return launch_pending(cache/'pending.json',APP_VERSION,is_newer_version)
        except Exception as error:
            cache.mkdir(parents=True,exist_ok=True);(cache/'startup-error.txt').write_text(str(error)[:500],encoding='utf-8');return False
