"""RinUI-facing adapter around FlowTodo's existing business backend.

The WebEngine application and the native QML application intentionally share
the same JSON files and the same :class:`main.BackendBridge` implementation.
This module only adds QML-friendly properties, signal aliases, and small
id-based helpers used by the native pages.
"""

from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from main import BackendBridge


class RinUIBackend(BackendBridge):
    """Compatibility facade that keeps the old backend as the source of truth."""

    tasksChanged = Signal()
    groupsChanged = Signal()
    projectsChanged = Signal()
    statsChanged = Signal()
    achievementsChanged = Signal()
    settingsChanged = Signal()
    aiStateChanged = Signal()
    aiRequestChanged = Signal()
    aiRequestFinished = Signal(bool, str)
    longPlanChanged = Signal()
    focusSessionChanged = Signal()
    messageRequested = Signal(str, str, str)
    focusStartResult = Signal(bool, str)
    navigationContextChanged = Signal()
    desktopWidgetVisibilityRequested = Signal(bool)
    focusPreparationRequested = Signal(str, float)

    def __init__(self):
        super().__init__()
        self.native_window = None
        self._last_focus_payload = "{}"
        self._active_group_id = -1
        self._active_project_id = -1
        self._ai_request_running = False
        self.signalTasksUpdated.connect(lambda _payload: self.tasksChanged.emit())
        self.signalGroupsUpdated.connect(lambda _payload: self.groupsChanged.emit())
        self.signalProjectsUpdated.connect(lambda _payload: self.projectsChanged.emit())
        self.signalStatsUpdated.connect(lambda _payload: self.statsChanged.emit())
        self.signalAchievementsUpdated.connect(lambda _payload: self.achievementsChanged.emit())
        self.signalFocusSessionChanged.connect(self._on_focus_session_payload)
        self.signalAiMessage.connect(lambda _payload: self.aiStateChanged.emit())
        self.signalAiPlanReady.connect(self._on_ai_plan_ready)
        self.signalPathSelected.connect(lambda _path: self.settingsChanged.emit())

    def attach_native_window(self, window) -> None:
        self.native_window = window

    def _on_focus_session_payload(self, payload: str) -> None:
        self._last_focus_payload = payload or "{}"
        self.focusSessionChanged.emit()

    def _on_ai_plan_ready(self, payload: str) -> None:
        self._ai_request_running = False
        self.aiRequestChanged.emit()
        self.aiStateChanged.emit()
        try:
            result = json.loads(payload or "{}")
        except (TypeError, ValueError):
            result = {"ok": False, "error": "AI 返回了无法识别的数据"}

        if result.get("ok"):
            long_mode = bool(result.get("longMode"))
            message = str(result.get("message") or ("长期计划已经生成，可以打开预览" if long_mode else "计划已经生成"))
            self.messageRequested.emit("success", "长期计划生成完成" if long_mode else "AI 计划生成完成", message)
            self.aiRequestFinished.emit(True, message)
        else:
            message = str(result.get("error") or "请检查 API 设置和网络连接后重试")
            self.messageRequested.emit("error", "AI 规划失败", message)
            self.aiRequestFinished.emit(False, message)

    def _main_window(self):
        if self.native_window is not None:
            return self.native_window
        windows = QGuiApplication.topLevelWindows()
        return windows[0] if windows else None

    def _emit_settings_changed(self):
        self.settingsChanged.emit()

    @staticmethod
    def _json(value) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _focus_options(self, options) -> dict:
        """Normalize native-page option names to the original focus backend."""
        result = dict(options or {})
        if "shieldEnabled" in result and "disableOtherApps" not in result:
            result["disableOtherApps"] = bool(result.get("shieldEnabled"))
        if result.get("disableOtherApps") and "guardWhitelist" not in result:
            result["guardWhitelist"] = self.settings_database.get("focusGuardWhitelist", [])
        return result

    @Property(str, notify=tasksChanged)
    def tasksJson(self) -> str:
        return self.get_tasks_json()

    @Property(str, notify=groupsChanged)
    def groupsJson(self) -> str:
        return self.get_groups_json()

    @Property(str, notify=projectsChanged)
    def projectsJson(self) -> str:
        return self.get_projects_json()

    @Property(str, notify=settingsChanged)
    def settingsJson(self) -> str:
        return self.get_settings_json()

    @Property(str, notify=statsChanged)
    def statsJson(self) -> str:
        return self.get_stats_json()

    @Property(str, notify=achievementsChanged)
    def achievementsJson(self) -> str:
        return self.get_achievements_json()

    @Property(str, notify=aiStateChanged)
    def aiStateJson(self) -> str:
        return self.get_ai_state_json()

    @Property(bool, notify=aiRequestChanged)
    def aiRequestRunning(self) -> bool:
        return self._ai_request_running

    @Property(str, notify=longPlanChanged)
    def longPlanJson(self) -> str:
        return self.get_long_plan_json()

    @Property(str, notify=focusSessionChanged)
    def focusSessionJson(self) -> str:
        return self._last_focus_payload

    @Property(int, notify=tasksChanged)
    def taskCount(self) -> int:
        return len(self.local_database)

    @Property(int, notify=tasksChanged)
    def completedCount(self) -> int:
        return sum(1 for task in self.local_database if task.get("done"))

    @Property(int, notify=statsChanged)
    def todayFocusMinutes(self) -> int:
        return int(self._build_stats().get("todayFocusSeconds", 0) or 0) // 60

    @Property(str, constant=True)
    def todayLabel(self) -> str:
        now = datetime.now()
        weekdays = "一二三四五六日"
        return f"{now.month}月{now.day}日 · 星期{weekdays[now.weekday()]}"

    @Property(str, notify=settingsChanged)
    def dataPath(self) -> str:
        return str(self.get_current_data_path())

    @Property(float, notify=navigationContextChanged)
    def activeGroupId(self) -> float:
        return float(self._active_group_id)

    @Property(float, notify=navigationContextChanged)
    def activeProjectId(self) -> float:
        return float(self._active_project_id)

    @Slot(float)
    def setActiveGroupId(self, group_id: float) -> None:
        self._active_group_id = int(group_id)
        self.navigationContextChanged.emit()

    @Slot(float)
    def setActiveProjectId(self, project_id: float) -> None:
        self._active_project_id = int(project_id)
        self.navigationContextChanged.emit()

    @Slot()
    def reload(self) -> None:
        self.local_database = self._load_json(self.tasks_file, self.local_database)
        self.groups_database = self._load_json(self.groups_file, self.groups_database)
        self.projects_database = self._load_json(self.projects_file, self.projects_database)
        self.settings_database = self._load_json(self.settings_file, self.settings_database)
        self.stats_database = self._load_json(self.stats_file, self.stats_database)
        self.achievements_database = self._load_json(self.achievements_file, self.achievements_database)
        self.ai_state_database = self._load_json(self.ai_state_file, self.ai_state_database)
        self.long_plan_database = self._load_json(self.long_plan_file, self.long_plan_database)
        self._normalize_settings()
        self.tasksChanged.emit()
        self.groupsChanged.emit()
        self.projectsChanged.emit()
        self.settingsChanged.emit()
        self.statsChanged.emit()
        self.achievementsChanged.emit()
        self.aiStateChanged.emit()
        self.longPlanChanged.emit()

    @Slot(str, str)
    def addTask(self, title: str, meta: str = "") -> None:
        self.add_task(title, meta)

    @Slot(float, bool)
    def toggleTask(self, task_id: float, done: bool) -> None:
        self.toggle_task_status(task_id, done)

    @Slot(float)
    def deleteTask(self, task_id: float) -> None:
        self.delete_task(task_id)

    @Slot(str)
    def addGroup(self, group_json: str) -> None:
        self.add_group(group_json)

    @Slot(str)
    def updateGroup(self, group_json: str) -> None:
        self.update_group(group_json)

    @Slot(float)
    def deleteGroup(self, group_id: float) -> None:
        self.delete_group(group_id)

    @Slot(str)
    def addProject(self, project_json: str) -> None:
        self.add_project(project_json)

    @Slot(str)
    def updateProject(self, project_json: str) -> None:
        self.update_project(project_json)

    @Slot(float)
    def deleteProject(self, project_id: float) -> None:
        self.delete_project(project_id)

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value) -> None:
        settings = dict(self.settings_database)
        settings[key] = value
        self.save_settings(self._json(settings))
        self.settingsChanged.emit()

    @Slot(str, str)
    def setSettingJson(self, key: str, value_json: str) -> None:
        """Store structured QML values without passing JS objects to PySide."""
        try:
            value = json.loads(value_json)
        except (TypeError, ValueError):
            value = value_json
        self.setSetting(key, value)

    @Slot(str, "QVariant", result="QVariant")
    def getSetting(self, key: str, fallback=None):
        return self.settings_database.get(key, fallback)

    @Slot()
    def chooseDataDirectory(self) -> None:
        self.open_directory_dialog()

    def save_settings(self, settings_json):
        super().save_settings(settings_json)
        self.settingsChanged.emit()

    @Slot(float, result=bool)
    def startTask(self, task_id: float) -> bool:
        task = next((item for item in self.local_database if int(item.get("id", -1)) == int(task_id)), None)
        if not task:
            self.focusStartResult.emit(False, "任务不存在")
            return False
        payload = {
            "taskId": task.get("id"),
            "title": task.get("title", "任务专注"),
            "subtitle": task.get("meta", "单任务专注"),
            "minutes": self.settings_database.get("focusDuration", 25),
        }
        try:
            ok = bool(self.start_single_task(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", "无法启动专注", str(error))
        self.focusStartResult.emit(ok, "" if ok else "灵动岛启动失败")
        return ok

    @Slot(float, float, result=bool)
    def startPreparedTask(self, task_id: float, minutes: float) -> bool:
        task = next((item for item in self.local_database if int(item.get("id", -1)) == int(task_id)), None)
        if not task:
            self.focusStartResult.emit(False, "任务不存在")
            return False
        payload = {
            "taskId": task.get("id"),
            "title": task.get("title", "任务专注"),
            "subtitle": task.get("meta", "单任务专注"),
            "minutes": max(1, int(minutes or self.settings_database.get("focusDuration", 25))),
        }
        try:
            ok = bool(self.start_single_task(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", "无法启动专注", str(error))
        self.focusStartResult.emit(ok, "" if ok else "灵动岛启动失败")
        return ok

    @Slot(float)
    def startFocus(self, task_id: float) -> bool:
        return self.startTask(task_id)

    @Slot(float, str, result=bool)
    def startGroupById(self, group_id: float, options_json: str = "{}") -> bool:
        group = next((item for item in self.groups_database if int(item.get("id", -1)) == int(group_id)), None)
        if not group:
            self.focusStartResult.emit(False, "任务流不存在")
            return False
        try:
            options = json.loads(options_json or "{}")
        except (TypeError, ValueError):
            options = {}
        options = self._focus_options(options)
        payload = {
            "groupId": group.get("id"),
            "tasks": [
                {"title": step.get("name") or step.get("title") or "步骤", "time": step.get("duration") or step.get("time") or 25, "type": step.get("type", "focus")}
                for step in group.get("steps", [])
            ],
            "options": options,
        }
        try:
            ok = bool(self.start_group(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", "无法启动任务流", str(error))
        self.focusStartResult.emit(ok, "" if ok else "灵动岛启动失败")
        return ok

    @Slot(float, str, str, result=bool)
    def startPreparedGroup(self, group_id: float, tasks_json: str, options_json: str = "{}") -> bool:
        try:
            tasks = json.loads(tasks_json or "[]")
        except (TypeError, ValueError):
            tasks = []
        try:
            options = json.loads(options_json or "{}")
        except (TypeError, ValueError):
            options = {}
        options = self._focus_options(options)
        try:
            ok = bool(self.start_group(self._json({"groupId": int(group_id), "tasks": tasks, "options": options})))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", "无法启动任务流", str(error))
        self.focusStartResult.emit(ok, "" if ok else "灵动岛启动失败")
        return ok

    @Slot(float, str, result=bool)
    def startProjectById(self, project_id: float, options_json: str = "{}") -> bool:
        project = next((item for item in self.projects_database if int(item.get("id", -1)) == int(project_id)), None)
        if not project:
            self.focusStartResult.emit(False, "项目不存在")
            return False
        try:
            options = json.loads(options_json or "{}")
        except (TypeError, ValueError):
            options = {}
        options = self._focus_options(options)
        milestones = project.get("milestones") or []
        requested = options.pop("targetMilestones", None)
        goal = str(options.pop("goal", "") or project.get("desc") or project.get("description") or "项目专注")
        selected = list(requested or [])
        if not selected:
            selected = [item.get("title") or item.get("name") or "里程碑" for item in milestones if not item.get("done")]
        if not selected:
            selected = [item.get("title") or item.get("name") or "里程碑" for item in milestones]
        payload = {
            "projectId": project.get("id"),
            "goal": goal,
            "targetMilestones": selected,
            "targetMilestoneIndexes": [index for index, item in enumerate(milestones) if (item.get("title") or item.get("name")) in selected],
            "options": options,
        }
        try:
            ok = bool(self.start_project(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", "无法启动项目", str(error))
        self.focusStartResult.emit(ok, "" if ok else "灵动岛启动失败")
        return ok

    @Slot(str, bool)
    def requestAi(self, prompt: str, long_mode: bool = False) -> None:
        if self._ai_request_running:
            self.messageRequested.emit("info", "AI 正在生成", "请等待当前请求完成")
            return
        payload = {
            "messages": [{"role": "user", "content": str(prompt or "")}],
            "longMode": bool(long_mode),
            "replaceOnApply": bool(self.settings_database.get("aiReplaceOnApply", True)),
        }
        self._ai_request_running = True
        self.aiRequestChanged.emit()
        self.messageRequested.emit(
            "info",
            "正在生成长期计划" if long_mode else "正在生成计划",
            "AI 正在根据实时数据整理任务结构，请稍候",
        )
        try:
            self.request_ai_plan(self._json(payload))
        except Exception as error:
            self._ai_request_running = False
            self.aiRequestChanged.emit()
            message = str(error)
            self.messageRequested.emit("error", "无法发起 AI 请求,可能是Api出错", message)
            self.aiRequestFinished.emit(False, message)

    @Slot(str)
    def applyAiPlan(self, plan_json: str) -> None:
        self.apply_ai_plan_json(plan_json)
        self.aiStateChanged.emit()

    @Slot()
    def clearAiMessages(self) -> None:
        self.clear_ai_messages()
        self.aiStateChanged.emit()

    @Slot()
    def showDesktopWidget(self) -> None:
        self.desktopWidgetVisibilityRequested.emit(True)

    @Slot()
    def hideDesktopWidget(self) -> None:
        self.desktopWidgetVisibilityRequested.emit(False)

    @Slot(str, float)
    def requestFocusPreparation(self, kind: str, item_id: float) -> None:
        kind = str(kind or "").strip().lower()
        target_id = int(item_id)
        databases = {
            "task": self.local_database,
            "group": self.groups_database,
            "project": self.projects_database,
        }
        database = databases.get(kind)
        target = next((item for item in (database or []) if int(item.get("id", -1)) == target_id), None)
        if target is None:
            self.messageRequested.emit("error", "无法打开专注准备", "所选内容已经不存在，请刷新小组件")
            return
        if kind == "task" and bool(target.get("done")):
            self.messageRequested.emit("warning", "任务已经完成", "请选择一个待完成任务")
            return
        if kind == "group":
            self.setActiveGroupId(target_id)
        elif kind == "project":
            self.setActiveProjectId(target_id)
        self.focusPreparationRequested.emit(kind, float(target_id))

    @Slot(str)
    def startLongPlan(self, plan_json: str) -> None:
        self.start_long_plan(plan_json)
        self.longPlanChanged.emit()
        self.aiStateChanged.emit()

    @Slot()
    def abandonLongPlan(self) -> None:
        self.abandon_long_plan()
        self.longPlanChanged.emit()

    @Slot(str, result=str)
    def themePreviewUrl(self, theme_id: str) -> str:
        from pathlib import Path

        names = {
            "default": "classwidgets-default.png",
            "cw1": "classwidgets-cw1.png",
            "win10": "classwidgets-win10.png",
            "material": "classwidgets-material.png",
        }
        path = Path(__file__).resolve().parent.parent / "theme_assets" / names.get(theme_id, names["material"])
        return path.resolve().as_uri()

    @Slot(result=str)
    def getFocusGuardAppsJson(self) -> str:
        """Return the selectable Windows applications for the focus guard."""
        return self.get_focus_guard_apps_json()

    @Slot(result=str)
    def getFocusSessionJson(self) -> str:
        return self._last_focus_payload

    @Slot()
    def cancelFocus(self) -> None:
        self.cancel_focus_session()

    @Slot()
    def shutdown(self) -> None:
        self.shutdown_focus_environment()
