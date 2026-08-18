"""Small native data bridge for the FlowTodo QML experiment."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot


DEFAULT_SETTINGS = {
    "theme": "auto",
    "focusDuration": 25,
    "autoNext": False,
    "autoStart": False,
    "bgMode": "daily",
    "nativeUiTheme": "material",
    "nativeBackdrop": "none",
    "islandTheme": "material",
    "islandScale": 1.0,
    "islandOpacity": 1.0,
    "islandAnchor": "top_center",
    "islandOffsetX": 0,
    "islandOffsetY": 96,
    "islandLayer": "top",
    "islandLightingEffect": True,
}


class NativeBackend(QObject):
    tasksChanged = Signal()
    settingsChanged = Signal()
    statsChanged = Signal()
    messageRequested = Signal(str, str, str)

    def __init__(self, project_root: Path):
        super().__init__()
        app_data = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        self.data_dir = app_data / "FlowTodo" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.data_dir / "tasks.json"
        self.settings_file = self.data_dir / "settings.json"
        self.stats_file = self.data_dir / "stats.json"
        self.theme_assets = project_root / "theme_assets"
        self._tasks = self._read_json(self.tasks_file, [])
        self._settings = self._read_json(self.settings_file, DEFAULT_SETTINGS.copy())
        self._stats = self._read_json(self.stats_file, {})
        self._settings = {**DEFAULT_SETTINGS, **self._settings}
        self._islands = {}
        self._mtimes = {}
        self._remember_mtimes()

        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(1200)
        self._watch_timer.timeout.connect(self._reload_external_changes)
        self._watch_timer.start()

    @staticmethod
    def _read_json(path: Path, fallback):
        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value
        except (OSError, ValueError, TypeError):
            return fallback

    @staticmethod
    def _write_json(path: Path, value) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".native.tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def _remember_mtimes(self) -> None:
        for path in (self.tasks_file, self.settings_file, self.stats_file):
            try:
                self._mtimes[path] = path.stat().st_mtime_ns
            except OSError:
                self._mtimes[path] = 0

    def _reload_external_changes(self) -> None:
        changed = []
        for path in (self.tasks_file, self.settings_file, self.stats_file):
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                mtime = 0
            if mtime != self._mtimes.get(path, 0):
                self._mtimes[path] = mtime
                changed.append(path)

        if self.tasks_file in changed:
            self._tasks = self._read_json(self.tasks_file, self._tasks)
            self.tasksChanged.emit()
        if self.settings_file in changed:
            loaded = self._read_json(self.settings_file, self._settings)
            self._settings = {**DEFAULT_SETTINGS, **loaded}
            self.settingsChanged.emit()
        if self.stats_file in changed:
            self._stats = self._read_json(self.stats_file, self._stats)
            self.statsChanged.emit()

    @Property(str, notify=tasksChanged)
    def tasksJson(self) -> str:
        return json.dumps(self._tasks, ensure_ascii=False)

    @Property(str, notify=settingsChanged)
    def settingsJson(self) -> str:
        return json.dumps(self._settings, ensure_ascii=False)

    @Property(int, notify=tasksChanged)
    def taskCount(self) -> int:
        return len(self._tasks)

    @Property(int, notify=tasksChanged)
    def completedCount(self) -> int:
        return sum(1 for task in self._tasks if task.get("done"))

    @Property(int, notify=statsChanged)
    def todayFocusMinutes(self) -> int:
        return int(self._stats.get("todayFocusSeconds", 0) or 0) // 60

    @Property(str, constant=True)
    def todayLabel(self) -> str:
        weekdays = "一二三四五六日"
        now = datetime.now()
        return f"{now.month}月{now.day}日  星期{weekdays[now.weekday()]}"

    @Property(str, constant=True)
    def dataPath(self) -> str:
        return str(self.data_dir)

    @Slot()
    def reload(self) -> None:
        self._tasks = self._read_json(self.tasks_file, self._tasks)
        loaded = self._read_json(self.settings_file, self._settings)
        self._settings = {**DEFAULT_SETTINGS, **loaded}
        self._stats = self._read_json(self.stats_file, self._stats)
        self._remember_mtimes()
        self.tasksChanged.emit()
        self.settingsChanged.emit()
        self.statsChanged.emit()

    @Slot(str, str)
    def addTask(self, title: str, meta: str) -> None:
        title = title.strip()
        if not title:
            self.messageRequested.emit("warning", "无法添加任务", "请先输入任务名称")
            return
        self._tasks = self._read_json(self.tasks_file, self._tasks)
        self._tasks.insert(
            0,
            {
                "id": int(time.time_ns() // 1_000_000),
                "title": title,
                "meta": meta.strip() or "今天",
                "done": False,
            },
        )
        self._save_tasks()
        self.messageRequested.emit("success", "任务已添加", title)

    @Slot(float, bool)
    def toggleTask(self, task_id: float, done: bool) -> None:
        target = int(task_id)
        self._tasks = self._read_json(self.tasks_file, self._tasks)
        for task in self._tasks:
            if int(task.get("id", -1)) == target:
                task["done"] = bool(done)
                break
        self._save_tasks()

    @Slot(float)
    def deleteTask(self, task_id: float) -> None:
        target = int(task_id)
        self._tasks = self._read_json(self.tasks_file, self._tasks)
        self._tasks = [task for task in self._tasks if int(task.get("id", -1)) != target]
        self._save_tasks()
        self.messageRequested.emit("info", "任务已删除", "可在原版 FlowTodo 中继续管理其他数据")

    def _save_tasks(self) -> None:
        self._write_json(self.tasks_file, self._tasks)
        self._remember_mtimes()
        self.tasksChanged.emit()

    @Slot(str, "QVariant", result="QVariant")
    def getSetting(self, key: str, fallback=None):
        return self._settings.get(key, fallback)

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value) -> None:
        loaded = self._read_json(self.settings_file, self._settings)
        self._settings = {**DEFAULT_SETTINGS, **loaded}
        self._settings[key] = value
        self._write_json(self.settings_file, self._settings)
        self._remember_mtimes()
        self.settingsChanged.emit()

    @Slot(str, result=str)
    def themePreviewUrl(self, theme_id: str) -> str:
        names = {
            "default": "classwidgets-default.png",
            "cw1": "classwidgets-cw1.png",
            "win10": "classwidgets-win10.png",
            "material": "classwidgets-material.png",
        }
        path = self.theme_assets / names.get(theme_id, names["material"])
        return path.resolve().as_uri()

    @Slot(float)
    def startFocus(self, task_id: float) -> None:
        target = int(task_id)
        task = next(
            (item for item in self._tasks if int(item.get("id", -1)) == target),
            None,
        )
        if task is None:
            return
        try:
            from island import DynamicIslandBridge

            duration = max(1, int(self._settings.get("focusDuration", 25))) * 60
            preferences = {
                key: self._settings.get(key, DEFAULT_SETTINGS[key])
                for key in (
                    "islandTheme",
                    "islandScale",
                    "islandOpacity",
                    "islandAnchor",
                    "islandOffsetX",
                    "islandOffsetY",
                    "islandLayer",
                    "islandLightingEffect",
                )
            }
            island = DynamicIslandBridge(
                tasks=[{
                    "title": str(task.get("title") or "专注任务"),
                    "subtitle": str(task.get("meta") or ""),
                    "time": duration,
                    "type": "focus",
                }],
                mode="group",
                preferences=preferences,
            )
            key = id(island)
            self._islands[key] = island
            island.destroyed.connect(lambda _obj=None, item_key=key: self._islands.pop(item_key, None))
            island.show()
            self.messageRequested.emit("success", "专注已开始", task.get("title", ""))
        except Exception as exc:
            self.messageRequested.emit("error", "无法启动专注", str(exc))

    @Slot()
    def shutdown(self) -> None:
        self._watch_timer.stop()
        for island in list(self._islands.values()):
            island.close()
        self._islands.clear()
