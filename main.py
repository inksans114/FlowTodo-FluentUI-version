"""
Cheems Todo - 主服务模块(serve.py)
====================================
基于 PySide6 的桌面待办事项应用后端,通过 QWebChannel 与前端 index.html 通信.

核心类：
- BackendBridge(QObject) : 核心业务逻辑,管理任务/任务流/项目的 CRUD、AI 规划、专注会话等
- MainWindow(QMainWindow) : 主窗口,承载 QWebEngineView 加载前端界面
- DesktopWidgetsProcess : 桌面小组件子进程管理器
- StartupCheckWindow : 启动前环境检查窗口(网络、关键文件)
- NoZoomWebView / QuietWebEnginePage : 自定义 WebEngineView,禁用缩放并过滤控制台噪音

架构概述：
  前端 (index.html) ←→ QWebChannel ←→ BackendBridge ←→ JSON 文件持久化
                                              ↕
                                      DynamicIslandBridge (灵动岛,来自 island.py)

依赖：
- PySide6 (QtWebEngine, QtWebChannel)
- island.py (DynamicIslandBridge, send_windows_notification)
"""

import sys
import os
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-smooth-scrolling --disable-threaded-scrolling")
import json
import re
import copy
import socket
import subprocess
import threading
import traceback
import urllib.error
import urllib.request
import webbrowser
import base64
import ctypes
import ctypes.wintypes
import tempfile
import uuid
from datetime import datetime, timedelta
try:
    import winreg
except ImportError:
    winreg = None
from PySide6.QtCore import QObject, Slot, Signal, QUrl, Qt, QEvent, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
try:
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
except ImportError:  # RinUI/QML 原生打包场景不包含 WebEngine
    QWebEnginePage = QWebEngineSettings = QWebEngineView = QWebChannel = None

# WebEngine 不可用时的占位基类，保证模块可被导入（RinUI 模式不会实例化它们）
if QWebEngineView is None:
    class QWebEnginePage:  # noqa: E305
        pass

    class QWebEngineView:
        pass

    class QWebChannel:
        pass

from island import DynamicIslandBridge, send_windows_notification


class DesktopWidgetsProcess:
    """桌面小组件子进程管理器.

    通过 subprocess.Popen 启动 desktop_widgets_fluent.py 作为独立子进程,
    提供 show_hub / hide / shutdown 生命周期管理,避免主进程阻塞.
    """
    def __init__(self, data_dir):
        """初始化桌面小组件管理器.

        Args:
            data_dir: 数据目录路径,传递给子进程
        """
        """
        self.data_dir = data_dir
        self.process = None
        self.script_path = os.path.join(os.path.dirname(__file__), "desktop_widgets_fluent.py")"""

    def isVisible(self):
        return self.process is not None and self.process.poll() is None

    def show_hub(self):
        """启动桌面小组件子进程(若尚未运行)."""
        """if self.isVisible():
            return
        if not os.path.isfile(self.script_path):
            raise FileNotFoundError(self.script_path)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [sys.executable, self.script_path, "--data-dir", self.data_dir],
            cwd=os.path.dirname(__file__),
            creationflags=creationflags,
        )
"""
    def hide(self):
        self.shutdown()

    def shutdown(self):
        """终止桌面小组件子进程,先温和 terminate 再强制 kill."""
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

class QuietWebEnginePage(QWebEnginePage):
    IGNORED_CONSOLE_MESSAGES = (
        "ResizeObserver loop completed with undelivered notifications.",
        "ResizeObserver loop limit exceeded",
    )

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        if any(text in message for text in self.IGNORED_CONSOLE_MESSAGES):
            return
        super().javaScriptConsoleMessage(level, message, line_number, source_id)


class NoZoomWebView(QWebEngineView):
    """禁用缩放手势和 Ctrl+滚轮缩放的 WebEngineView.

    拦截 Gesture、NativeGesture、wheelEvent、keyPressEvent,
    强制将 zoomFactor 锁定为 1.0,保证前端 MD3 布局不被缩放破坏.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPage(QuietWebEnginePage(self))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setZoomFactor(1.0)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        viewport = getattr(self, "viewport", lambda: None)()
        if viewport is not None:
            viewport.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        pinch_gesture = getattr(Qt.GestureType, "PinchGesture", None)
        if pinch_gesture is not None:
            self.grabGesture(pinch_gesture)
        # Keep Chromium on an opaque backing store. Transparent WebEngine
        # surfaces inside frameless windows can flash during GPU composition.
        self.page().setBackgroundColor(QColor("#1C1B1F"))
        self.page().loadFinished.connect(lambda _ok: self.setZoomFactor(1.0))

    def event(self, event):
        blocked_events = [QEvent.Type.Gesture]
        native_gesture = getattr(QEvent.Type, "NativeGesture", None)
        if native_gesture is not None:
            blocked_events.append(native_gesture)
        if event.type() in blocked_events:
            event.ignore()
            self.setZoomFactor(1.0)
            return True
        return super().event(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.accept()
            self.setZoomFactor(1.0)
            return
        super().wheelEvent(event)
        if self.zoomFactor() != 1.0:
            self.setZoomFactor(1.0)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Minus, Qt.Key.Key_0, Qt.Key.Key_Equal):
                event.accept()
                self.setZoomFactor(1.0)
                return
        super().keyPressEvent(event)
        if self.zoomFactor() != 1.0:
            self.setZoomFactor(1.0)


HIDE_SCROLLBAR_QSS = """
QScrollBar:vertical, QScrollBar:horizontal {
    width: 0px;
    height: 0px;
    margin: 0px;
    padding: 0px;
    border: none;
    background: transparent;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal,
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
"""


STARTUP_NETWORK_TARGETS = (
    ("www.baidu.com", 443),
    ("www.qq.com", 443),
    ("unpkg.com", 443),
)


def _check_network_available(timeout=2.5):
    """检查网络连通性：尝试连接百度、QQ、unpkg 的 443 端口."""
    errors = []
    for host, port in STARTUP_NETWORK_TARGETS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True, ""
        except OSError as e:
            errors.append(f"{host}:{port} - {e}")
    return False, "\n".join(errors)


def _check_required_startup_files(base_dir):
    """检查关键启动文件(index.html, vendor/*)是否存在且大小合理."""
    required_files = (
        ("index.html", 1024),
        (os.path.join("vendor", "mdui.css"), 10_000),
        (os.path.join("vendor", "mdui.global.js"), 100_000),
        (os.path.join("vendor", "material-icons.css"), 500),
        (os.path.join("vendor", "iconfont", "MaterialIcons-Regular.woff2"), 10_000),
    )
    missing = []
    for rel_path, min_size in required_files:
        path = os.path.join(base_dir, rel_path)
        try:
            if not os.path.isfile(path):
                missing.append(f"{rel_path} 不存在")
                continue
            size = os.path.getsize(path)
            if size < min_size:
                missing.append(f"{rel_path} 文件异常,大小只有 {size} 字节")
        except OSError as e:
            missing.append(f"{rel_path} 无法读取：{e}")
    return missing


def run_startup_preflight():
    """启动前飞行检查：网络连通性 + 关键文件完整性.返回错误列表."""
    base_dir = os.path.dirname(__file__)
    errors = []

    network_ok, network_detail = _check_network_available()
    if not network_ok:
        errors.append(
            "网络连接不可用,软件启动被拦截.\n"
            "请先连接网络,或检查防火墙/代理是否阻止本软件访问网络.\n"
            f"{network_detail}"
        )

    file_errors = _check_required_startup_files(base_dir)
    if file_errors:
        errors.append("软件关键文件缺失或损坏：\n" + "\n".join(file_errors))

    return errors


def show_startup_blocker(errors):
    print("[Startup check failed]\n" + "\n\n".join(errors))
    return

class StartupCheckWindow(QMainWindow):
    """启动检测窗口：展示网络/文件检查结果,支持重新检测或退出."""
    def __init__(self, errors, on_ready):
        super().__init__()
        self.on_ready = on_ready
        self.setWindowTitle("Cheems Todo - 启动检测")
        self.resize(880, 620)
        self.setMinimumSize(760, 520)
        self.setStyleSheet("""
            QMainWindow { background: #1C1B1F; }
            QLabel { color: #E6E1E5; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }
            QFrame#panel {
                background: #2B2930;
                border: 1px solid #49454F;
                border-radius: 18px;
            }
            QFrame#card {
                background: #211F26;
                border: 1px solid #625B71;
                border-radius: 14px;
            }
            QPushButton {
                min-height: 42px;
                padding: 0 22px;
                border-radius: 21px;
                border: none;
                font-size: 14px;
                font-weight: 600;
                background: #D0BCFF;
                color: #381E72;
            }
            QPushButton#secondary {
                background: #332D41;
                color: #E6E1E5;
                border: 1px solid #625B71;
            }
            QPushButton:disabled {
                background: #49454F;
                color: #CAC4D0;
            }
        """)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(34, 30, 34, 30)
        root.setSpacing(18)

        header = QFrame()
        header.setObjectName("panel")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)
        header_layout.setSpacing(8)

        title = QLabel("启动前检测")
        title.setStyleSheet("font-size: 30px; font-weight: 800; color: #FFD8E4;")
        subtitle = QLabel("Cheems Todo 发现当前环境还不能安全进入主界面.修复下面的问题后,可以直接重新检测.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 15px; color: #CAC4D0;")
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-size: 14px; color: #D0BCFF; font-weight: 600;")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(self.summary_label)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        scroll.setWidget(self.cards_widget)
        root.addWidget(scroll, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.retry_button = QPushButton("重新检测")
        self.exit_button = QPushButton("退出")
        self.exit_button.setObjectName("secondary")
        self.retry_button.clicked.connect(self.retry)
        self.exit_button.clicked.connect(QApplication.instance().quit)
        actions.addWidget(self.exit_button)
        actions.addWidget(self.retry_button)
        root.addLayout(actions)

        self.setCentralWidget(central)
        self.set_errors(errors)

    def set_errors(self, errors):
        self.errors = list(errors or [])
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.errors:
            self.summary_label.setText("检测通过,正在进入软件.")
            self.cards_layout.addWidget(self._make_card("检测通过", "网络和关键文件都正常.", ok=True))
            return

        self.summary_label.setText(f"发现 {len(self.errors)} 个问题,已暂缓进入主界面.")
        for error in self.errors:
            self.cards_layout.addWidget(self._make_card(*self._describe_error(error)))
        self.cards_layout.addStretch(1)

    def _describe_error(self, error):
        text = str(error or "").strip()
        if "网络" in text or "baidu.com" in text or "unpkg.com" in text:
            return (
                "网络连接未通过",
                text + "\n\n建议：确认电脑已联网；如果使用代理或防火墙,请允许本软件访问网络.",
                False,
            )
        if "文件" in text or "vendor" in text or "index.html" in text:
            return (
                "关键资源文件异常",
                text + "\n\n建议：检查软件目录是否完整,尤其是 vendor 资源文件夹.",
                False,
            )
        return (
            "软件初始化异常",
            text + "\n\n建议：保留这段错误信息,方便定位具体模块.",
            False,
        )

    def _make_card(self, title, body, ok=False):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title_label = QLabel(("通过 - " if ok else "未通过 - ") + title)
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #B9F6CA;"
            if ok else
            "font-size: 18px; font-weight: 800; color: #FFB4AB;"
        )
        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body_label.setStyleSheet("font-size: 13px; line-height: 1.45; color: #CAC4D0;")

        layout.addWidget(title_label)
        layout.addWidget(body_label)
        return card

    def retry(self):
        self.retry_button.setEnabled(False)
        self.summary_label.setText("正在重新检测...")
        QApplication.processEvents()
        errors = run_startup_preflight()
        if errors:
            self.set_errors(errors)
            self.retry_button.setEnabled(True)
            return
        self.set_errors([])
        QApplication.processEvents()
        self.on_ready()


class BackendBridge(QObject):
    """应用核心业务逻辑后端.

    通过 QWebChannel 与前端 index.html 通信,管理：
    - 任务(tasks)      : CRUD + 状态切换
    - 任务流(groups)   : 包含多步骤的番茄钟流程
    - 项目(projects)   : 带里程碑追踪的项目管理
    - 设置(settings)   : 主题、AI 配置、开机自启等
    - 统计(stats)      : 专注时长、完成次数等
    - 成就(achievements): 里程碑式成就系统
    - AI 规划            : 通过 OpenAI 兼容 API 生成任务计划
    - 长期计划(long_plan): AI 生成的周期性长期计划
    - 专注会话            : 启动灵动岛、护盾检测、壁纸切换、白噪音

    数据持久化到 %LOCALAPPDATA%/FlowTodo/data/ 下的 JSON 文件.
    """
    signalTasksUpdated = Signal(str)
    signalGroupsUpdated = Signal(str)
    signalProjectsUpdated = Signal(str)
    signalStatsUpdated = Signal(str)
    signalAchievementsUpdated = Signal(str)
    signalAiMessage = Signal(str)
    signalAiPlanReady = Signal(str)
    signalPathSelected = Signal(str)
    signalWindowStateChanged = Signal(bool)
    signalFocusSessionChanged = Signal(str)
    signalAppActivated = Signal()
    
    def __init__(self):
        super().__init__()
        app_data_root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        # 数据目录：%LOCALAPPDATA%/FlowTodo/data/
        self.data_dir = os.path.join(app_data_root, "FlowTodo", "data")
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        self.tasks_file = os.path.join(self.data_dir, "tasks.json")
        self.groups_file = os.path.join(self.data_dir, "groups.json")
        self.projects_file = os.path.join(self.data_dir, "projects.json")
        self.settings_file = os.path.join(self.data_dir, "settings.json")
        self.daily_file = os.path.join(self.data_dir, "daily_record.json")
        self.stats_file = os.path.join(self.data_dir, "stats.json")
        self.achievements_file = os.path.join(self.data_dir, "achievements.json")
        self.long_plan_file = os.path.join(self.data_dir, "long_plan.json")
        self.ai_state_file = os.path.join(self.data_dir, "ai_state.json")
        self.ai_plans_dir = os.path.join(self.data_dir, "ai_plans")
        if not os.path.exists(self.ai_plans_dir):
            os.makedirs(self.ai_plans_dir)
        
        self.local_database = self._load_json(self.tasks_file, self._get_default_tasks())
        self.groups_database = self._load_json(self.groups_file, self._get_default_groups())
        self.projects_database = self._load_json(self.projects_file, self._get_default_projects())
        self.settings_database = self._load_json(self.settings_file, self._get_default_settings())
        self.daily_record = self._load_json(self.daily_file, {"last_date": None})
        self.stats_database = self._load_json(self.stats_file, self._get_default_stats())
        self.achievements_database = self._load_json(self.achievements_file, {})
        self.long_plan_database = self._load_json(self.long_plan_file, self._get_default_long_plan())
        self.ai_state_database = self._load_json(self.ai_state_file, self._get_default_ai_state())
        self._normalize_settings()
        self._normalize_stats()
        self.island_windows = {}
        self.active_focus_session = None
        self._system_wallpaper_before_focus = None
        self._system_wallpaper_changed = False
        self._focus_wallpaper_file = None
        self._focus_noise_file = None
        self._focus_environment_active = False
        self._focus_guard_enabled = False
        self._focus_guard_allowed_hwnds = set()
        self._focus_guard_allowed_apps = set()
        self._focus_guard_last_hwnd = None
        self._focus_guard_last_alert_at = 0
        self._focus_guard_timer = QTimer(self)
        self._focus_guard_timer.setInterval(1200)
        self._focus_guard_timer.timeout.connect(self._check_focus_guard)
        self.desktop_widgets_window = None
        
        print(f"[Python] 数据初始化完成 | 任务: {len(self.local_database)} | 流程: {len(self.groups_database)} | 项目: {len(self.projects_database)}")

    def attach_desktop_widgets(self, window):
        self.desktop_widgets_window = window

    def _get_default_tasks(self):
        return [{"id": 101, "title": "检查 Python 端连通性", "meta": "系统内置测试数据", "done": False}]

    def _get_default_groups(self):
        return [{"id": 1001, "name": "晨间启动流程", "description": "每天早晨的高效启动", "steps": [{"name": "回顾任务", "duration": 5}, {"name": "深度工作", "duration": 25}], "theme": "primary"}]

    def _get_default_projects(self):
        return [
            {"id": 2001, "name": "软件重构计划", "desc": "全面接入 PySide6 核心和 SQLite", "progress": 0.75, "taskCount": 12, "milestones": [{"title": "完成数据库设计", "done": True}, {"title": "实现 WebChannel 通信", "done": False}]},
            {"id": 2002, "name": "MD3 动效打磨", "desc": "跟进 Google Material 3 规范", "progress": 0.2, "taskCount": 4, "milestones": [{"title": "研究 MD3 规范", "done": True}, {"title": "实现阶梯动画", "done": False}]}
        ]

    def _get_default_settings(self):
        return {
            "theme": "auto",
            "focusDuration": 25,
            "autoNext": False,
            "dataPath": self.data_dir,
            "dailyWallpaperSource": "bing",
            "bgMode": "daily",
            "bgColor": "surface",
            "bgTransparent": False,
            "dailySeedSuffix": "",
            "localBgDataUrl": "",
            "customBgColor": "#1C1B1F",
            "customBgPalette": [],
            "aiBaseUrl": "https://api.openai.com/v1",
            "aiModel": "gpt-4o-mini",
            "aiApiKey": "",
            "aiTemperature": 0.7,
            "aiTimeout": 240,
            "aiAutoApply": True,
            "aiReplaceOnApply": True,
            "autoStart": False,
            "islandTheme": "material",
            "nativeAccent": "#0f6cbd",
            "islandScale": 1.0,
            "islandOpacity": 1.0,
            "islandAnchor": "top_center",
            "islandOffsetX": 0,
            "islandOffsetY": 96,
            "islandLayer": "top",
            "islandLightingEffect": True,
            "desktopWidgetOpacity": 0.96,
            "desktopWidgetAutoShow": False,
            "desktopWidgetLayer": "top",
            "desktopWidgetLocked": False,
            "desktopWidgetWidth": 400,
            "desktopWidgetHeight": 570,
        }

    def _today(self):
        return datetime.now().strftime("%Y-%m-%d")

    def _get_default_stats(self):
        return {
            "totalFocusSeconds": 0,
            "todayFocusSeconds": 0,
            "totalFocusSessions": 0,
            "todayFocusSessions": 0,
            "completedGroupSessions": 0,
            "completedProjectSessions": 0,
            "completedTimerSessions": 0,
            "todayDate": self._today(),
            "lastFocusAt": None,
            "dailyFocusSeconds": {}
        }

    def _get_default_long_plan(self):
        return {
            "active": False,
            "plan": None,
            "startedAt": None,
            "currentCycleIndex": 0,
            "importedDates": [],
            "pendingReview": False
        }

    def _get_default_ai_state(self):
        return {
            "latestPlan": None,
            "latestPath": "",
            "messages": [],
            "updatedAt": None
        }

    def _load_json(self, filepath, default_data):
        """从 JSON 文件加载数据,若文件不存在则用默认值初始化并写入."""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception: pass
        self._save_json(filepath, default_data)
        return default_data

    def _save_json(self, filepath, data):
        """将数据保存到 JSON 文件,UTF-8 编码,indent=2 格式化."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _normalize_settings(self):
        """补全设置中缺失的默认字段,确保向后兼容."""
        changed = False
        defaults = self._get_default_settings()
        if not isinstance(self.settings_database, dict):
            self.settings_database = defaults
            changed = True
        for key, value in defaults.items():
            if key not in self.settings_database:
                self.settings_database[key] = value
                changed = True
        if changed:
            self._save_json(self.settings_file, self.settings_database)

    def _emit_data_updates(self):
        """向前端发射任务、流程、项目、统计、成就的全部更新信号."""
        self.signalTasksUpdated.emit(json.dumps(self.local_database, ensure_ascii=False))
        self.signalGroupsUpdated.emit(json.dumps(self.groups_database, ensure_ascii=False))
        self.signalProjectsUpdated.emit(json.dumps(self.projects_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    def _new_id(self, offset=0):
        """基于当前时间戳生成唯一 ID(毫秒级)."""
        return int(datetime.now().timestamp() * 1000) + offset

    def _fingerprint(self, value):
        """生成字符串的标准化指纹(去空格、小写),用于去重比对."""
        return re.sub(r"\s+", "", str(value or "").strip().lower())

    def _task_key(self, task):
        return self._fingerprint(task.get("title"))

    def _group_key(self, group):
        steps = "|".join(self._fingerprint(step.get("name") or step.get("title")) for step in group.get("steps", []))
        return f"{self._fingerprint(group.get('name'))}:{steps}"

    def _project_key(self, project):
        milestones = "|".join(self._fingerprint(item.get("title") or item.get("name")) for item in project.get("milestones", []))
        return f"{self._fingerprint(project.get('name'))}:{milestones}"

    def _normalize_ai_plan(self, plan):
        """标准化 AI 返回的计划 JSON,统一字段名和默认值."""
        if not isinstance(plan, dict):
            raise ValueError("AI 返回的内容不是 JSON 对象")

        normalized = {
            "title": str(plan.get("title") or "AI 个性化计划"),
            "summary": str(plan.get("summary") or ""),
            "mode": "long" if plan.get("mode") == "long" or isinstance(plan.get("longPlan"), dict) else "short",
            "tasks": [],
            "groups": [],
            "projects": [],
            "longPlan": None
        }

        for index, task in enumerate(plan.get("tasks") or []):
            if not isinstance(task, dict):
                continue
            title = str(task.get("title") or "").strip()
            if not title:
                continue
            normalized["tasks"].append({
                "id": self._new_id(index),
                "title": title,
                "meta": str(task.get("meta") or task.get("description") or "AI 规划任务"),
                "done": bool(task.get("done", False))
            })

        for group_index, group in enumerate(plan.get("groups") or []):
            if not isinstance(group, dict):
                continue
            name = str(group.get("name") or group.get("title") or "").strip()
            if not name:
                continue
            steps = []
            for step_index, step in enumerate(group.get("steps") or []):
                if not isinstance(step, dict):
                    continue
                step_name = str(step.get("name") or step.get("title") or "").strip()
                if not step_name:
                    continue
                steps.append({
                    "name": step_name,
                    "duration": self._positive_int(step.get("duration") or step.get("time"), 25, minimum=1),
                    "type": str(step.get("type") or "focus")
                })
            if not steps:
                steps = [{"name": "开始执行", "duration": 25, "type": "focus"}]
            normalized["groups"].append({
                "id": self._new_id(10000 + group_index),
                "name": name,
                "description": str(group.get("description") or group.get("desc") or "AI 生成任务流"),
                "steps": steps,
                "theme": str(group.get("theme") or "primary")
            })

        for project_index, project in enumerate(plan.get("projects") or []):
            if not isinstance(project, dict):
                continue
            name = str(project.get("name") or project.get("title") or "").strip()
            if not name:
                continue
            milestones = []
            for milestone in project.get("milestones") or []:
                if isinstance(milestone, dict):
                    title = str(milestone.get("title") or milestone.get("name") or "").strip()
                    done = bool(milestone.get("done", False))
                else:
                    title = str(milestone).strip()
                    done = False
                if title:
                    milestones.append({"title": title, "done": done})
            progress = max(0.0, min(1.0, self._safe_float(project.get("progress"), 0.0)))
            if milestones:
                progress = sum(1 for item in milestones if item.get("done")) / len(milestones)
            normalized["projects"].append({
                "id": self._new_id(20000 + project_index),
                "name": name,
                "desc": str(project.get("desc") or project.get("description") or "AI 生成项目"),
                "progress": progress,
                "taskCount": self._safe_int(project.get("taskCount"), len(milestones)),
                "milestones": milestones
            })

        long_plan = plan.get("longPlan")
        if isinstance(long_plan, dict):
            cycles = []
            for cycle_index, cycle in enumerate(long_plan.get("cycles") or []):
                if not isinstance(cycle, dict):
                    continue
                days = []
                for day_index, day in enumerate(cycle.get("days") or []):
                    if not isinstance(day, dict):
                        continue
                    tasks = []
                    for task in day.get("tasks") or []:
                        if isinstance(task, dict):
                            title = str(task.get("title") or "").strip()
                            meta = str(task.get("meta") or task.get("description") or "AI 长期计划")
                        else:
                            title = str(task).strip()
                            meta = "AI 长期计划"
                        if title:
                            tasks.append({"title": title, "meta": meta, "done": False})
                    days.append({
                        "day": self._safe_int(day.get("day"), day_index + 1),
                        "dateOffset": self._safe_int(day.get("dateOffset"), day_index),
                        "focus": str(day.get("focus") or f"第 {day_index + 1} 天"),
                        "tasks": tasks
                    })
                cycles.append({
                    "index": self._safe_int(cycle.get("index"), cycle_index + 1),
                    "title": str(cycle.get("title") or f"第 {cycle_index + 1} 周期"),
                    "goal": str(cycle.get("goal") or ""),
                    "days": days,
                    "reviewPrompt": str(cycle.get("reviewPrompt") or "总结本周期的完成情况、卡点和掌握程度.")
                })
            normalized["mode"] = "long"
            normalized["longPlan"] = {
                "goal": str(long_plan.get("goal") or normalized["title"]),
                "durationText": str(long_plan.get("durationText") or ""),
                "cycleLengthDays": self._positive_int(long_plan.get("cycleLengthDays"), 7, minimum=1),
                "totalCycles": self._positive_int(long_plan.get("totalCycles"), max(1, len(cycles)), minimum=1),
                "roadmap": [str(item) for item in (long_plan.get("roadmap") or []) if str(item).strip()],
                "cycles": cycles[:1] if cycles else [],
                "nextCycleInstruction": str(long_plan.get("nextCycleInstruction") or "周期结束后,请根据复盘反馈重新生成下一周期.")
            }

        return normalized

    def _extract_json_object(self, text):
        """从 AI 返回文本中提取 JSON 对象(支持代码块和裸 JSON)."""
        if not text:
            raise ValueError("AI 返回为空")
        fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
        candidates = []
        if fence_match:
            candidates.append(fence_match.group(1))
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(text[start:end + 1])
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        raise ValueError("没有找到可解析的 JSON 计划")

    def _save_ai_plan(self, plan):
        """将 AI 计划保存到 ai_plans 目录,文件名带时间戳."""
        filename = f"ai-plan-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        path = os.path.join(self.ai_plans_dir, filename)
        self._save_json(path, plan)
        return path

    def _mark_ai_items(self, plan):
        """给 AI 生成的条目打上 _source="ai" 标记,便于后续识别和替换."""
        for task in plan.get("tasks") or []:
            task["_source"] = "ai"
        for group in plan.get("groups") or []:
            group["_source"] = "ai"
        for project in plan.get("projects") or []:
            project["_source"] = "ai"
        return plan

    def _looks_ai_generated_text(self, text):
        return bool(re.search(r"(^|[^A-Za-z])ai([^A-Za-z]|$)|AI\s*(生成|规划|长期|计划)", str(text or ""), re.IGNORECASE))

    def _is_ai_task(self, task):
        text = f"{task.get('meta', '')} {task.get('_source', '')}"
        return task.get("_source") == "ai" or self._looks_ai_generated_text(text)

    def _is_ai_group(self, group):
        text = f"{group.get('description', '')} {group.get('_source', '')}"
        return group.get("_source") == "ai" or self._looks_ai_generated_text(text)

    def _is_ai_project(self, project):
        text = f"{project.get('desc', '')} {project.get('_source', '')}"
        return project.get("_source") == "ai" or self._looks_ai_generated_text(text)

    def _clear_existing_ai_content(self, plan=None):
        """清除已有 AI 内容：按指纹匹配删除旧的 AI 任务/流程/项目."""
        before = {
            "tasks": len(self.local_database),
            "groups": len(self.groups_database),
            "projects": len(self.projects_database)
        }
        incoming_task_keys = {self._task_key(task) for task in (plan or {}).get("tasks", []) if self._task_key(task)}
        incoming_group_names = {self._fingerprint(group.get("name")) for group in (plan or {}).get("groups", []) if self._fingerprint(group.get("name"))}
        incoming_project_names = {self._fingerprint(project.get("name")) for project in (plan or {}).get("projects", []) if self._fingerprint(project.get("name"))}

        self.local_database = [
            task for task in self.local_database
            if not (self._is_ai_task(task) or (incoming_task_keys and self._task_key(task) in incoming_task_keys))
        ]
        self.groups_database = [
            group for group in self.groups_database
            if not (self._is_ai_group(group) or (incoming_group_names and self._fingerprint(group.get("name")) in incoming_group_names))
        ]
        self.projects_database = [
            project for project in self.projects_database
            if not (self._is_ai_project(project) or (incoming_project_names and self._fingerprint(project.get("name")) in incoming_project_names))
        ]
        return {
            "tasks": before["tasks"] - len(self.local_database),
            "groups": before["groups"] - len(self.groups_database),
            "projects": before["projects"] - len(self.projects_database)
        }

    def _save_ai_state(self, latest_plan=None, latest_path=None, messages=None):
        if latest_plan is not None:
            self.ai_state_database["latestPlan"] = latest_plan
        if latest_path is not None:
            self.ai_state_database["latestPath"] = latest_path
        if messages is not None:
            clean_messages = []
            for item in messages[-40:]:
                if not isinstance(item, dict):
                    continue
                role = item.get("role")
                content = str(item.get("content") or "").strip()
                if role in ("user", "assistant", "system") and content:
                    clean_messages.append({"role": role, "content": content})
            self.ai_state_database["messages"] = clean_messages
        self.ai_state_database["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        self._save_json(self.ai_state_file, self.ai_state_database)

    def _apply_ai_plan(self, plan, merge_missing=True, replace_ai=False):
        """将 AI 计划应用到数据库：支持合并缺失项或完全替换 AI 内容."""
        added = {"tasks": 0, "groups": 0, "projects": 0, "groupSteps": 0, "projectMilestones": 0}
        removed = {"tasks": 0, "groups": 0, "projects": 0}
        plan = self._mark_ai_items(copy.deepcopy(plan or {}))
        if replace_ai:
            removed = self._clear_existing_ai_content(plan)
        if merge_missing:
            existing_tasks = {self._task_key(task) for task in self.local_database}
            new_tasks = []
            for task in plan.get("tasks") or []:
                key = self._task_key(task)
                if key and key not in existing_tasks:
                    new_tasks.append(copy.deepcopy(task))
                    existing_tasks.add(key)
            self.local_database = new_tasks + self.local_database
            added["tasks"] = len(new_tasks)

            existing_groups = {self._group_key(group) for group in self.groups_database}
            existing_groups_by_name = {self._fingerprint(group.get("name")): group for group in self.groups_database if self._fingerprint(group.get("name"))}
            for group in plan.get("groups") or []:
                key = self._group_key(group)
                name_key = self._fingerprint(group.get("name"))
                existing_group = existing_groups_by_name.get(name_key)
                if existing_group:
                    steps = existing_group.setdefault("steps", [])
                    existing_steps = {self._fingerprint(step.get("name") or step.get("title")) for step in steps}
                    missing_steps = []
                    for step in group.get("steps") or []:
                        step_key = self._fingerprint(step.get("name") or step.get("title"))
                        if step_key and step_key not in existing_steps:
                            missing_steps.append(copy.deepcopy(step))
                            existing_steps.add(step_key)
                    if missing_steps:
                        steps.extend(missing_steps)
                        added["groupSteps"] += len(missing_steps)
                    continue
                if key and key not in existing_groups:
                    group_to_add = copy.deepcopy(group)
                    self.groups_database.append(group_to_add)
                    existing_groups.add(key)
                    if name_key:
                        existing_groups_by_name[name_key] = group_to_add
                    added["groups"] += 1

            existing_projects = {self._project_key(project) for project in self.projects_database}
            existing_projects_by_name = {self._fingerprint(project.get("name")): project for project in self.projects_database if self._fingerprint(project.get("name"))}
            for project in plan.get("projects") or []:
                key = self._project_key(project)
                name_key = self._fingerprint(project.get("name"))
                existing_project = existing_projects_by_name.get(name_key)
                if existing_project:
                    milestones = existing_project.setdefault("milestones", [])
                    existing_milestones = {self._fingerprint(item.get("title") or item.get("name")) for item in milestones}
                    missing_milestones = []
                    for milestone in project.get("milestones") or []:
                        milestone_key = self._fingerprint(milestone.get("title") or milestone.get("name"))
                        if milestone_key and milestone_key not in existing_milestones:
                            missing_milestones.append(copy.deepcopy(milestone))
                            existing_milestones.add(milestone_key)
                    if missing_milestones:
                        milestones.extend(missing_milestones)
                        existing_project["taskCount"] = max(self._safe_int(existing_project.get("taskCount"), 0), len(milestones))
                        if milestones:
                            existing_project["progress"] = sum(1 for item in milestones if item.get("done")) / len(milestones)
                        added["projectMilestones"] += len(missing_milestones)
                    continue
                if key and key not in existing_projects:
                    project_to_add = copy.deepcopy(project)
                    self.projects_database.append(project_to_add)
                    existing_projects.add(key)
                    if name_key:
                        existing_projects_by_name[name_key] = project_to_add
                    added["projects"] += 1
        else:
            self.local_database = copy.deepcopy(list(plan.get("tasks") or [])) + self.local_database
            self.groups_database.extend(copy.deepcopy(plan.get("groups") or []))
            self.projects_database.extend(copy.deepcopy(plan.get("projects") or []))
            added = {
                "tasks": len(plan.get("tasks") or []),
                "groups": len(plan.get("groups") or []),
                "projects": len(plan.get("projects") or []),
                "groupSteps": 0,
                "projectMilestones": 0
            }
        self._save_json(self.tasks_file, self.local_database)
        self._save_json(self.groups_file, self.groups_database)
        self._save_json(self.projects_file, self.projects_database)
        self._emit_data_updates()
        added["removed"] = removed
        return added

    def _normalize_stats(self):
        """规范化统计数据：补全默认字段,处理跨天重置."""
        changed = False
        defaults = self._get_default_stats()
        if not isinstance(self.stats_database, dict):
            self.stats_database = defaults
            changed = True
        for key, value in defaults.items():
            if key not in self.stats_database:
                self.stats_database[key] = value
                changed = True
        if not isinstance(self.stats_database.get("dailyFocusSeconds"), dict):
            self.stats_database["dailyFocusSeconds"] = {}
            changed = True

        today = self._today()
        if self.stats_database.get("todayDate") != today:
            old_date = self.stats_database.get("todayDate")
            if old_date:
                daily = self.stats_database["dailyFocusSeconds"]
                old_seconds = self._safe_int(self.stats_database.get("todayFocusSeconds"), 0)
                daily[old_date] = max(self._safe_int(daily.get(old_date), 0), old_seconds)
            self.stats_database["todayDate"] = today
            self.stats_database["todayFocusSeconds"] = 0
            self.stats_database["todayFocusSessions"] = 0
            changed = True
        if changed:
            self._save_json(self.stats_file, self.stats_database)

    def _safe_int(self, value, default=0):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _task_stats(self):
        """计算任务统计：总数、已完成、未完成、完成率."""
        total = len(self.local_database)
        done = sum(1 for task in self.local_database if task.get("done"))
        pending = max(0, total - done)
        rate = round((done / total) * 100) if total else 0
        return {"total": total, "done": done, "pending": pending, "completionRate": rate}

    def _project_stats(self):
        """计算项目统计：里程碑进度、平均进度、已完成项目数."""
        total_milestones = 0
        done_milestones = 0
        completed_projects = 0
        progress_values = []
        for project in self.projects_database:
            milestones = project.get("milestones") or []
            project_milestone_count = len(milestones)
            project_done_count = sum(1 for milestone in milestones if milestone.get("done"))
            total_milestones += len(milestones)
            done_milestones += project_done_count
            progress = self._safe_float(project.get("progress"), 0.0)
            if milestones:
                progress = project_done_count / project_milestone_count if project_milestone_count else progress
            progress_values.append(max(0.0, min(1.0, progress)))
            if progress >= 1.0:
                completed_projects += 1
        average_progress = round((sum(progress_values) / len(progress_values)) * 100) if progress_values else 0
        return {
            "total": len(self.projects_database),
            "averageProgress": average_progress,
            "totalMilestones": total_milestones,
            "doneMilestones": done_milestones,
            "completedProjects": completed_projects
        }

    def _build_stats(self):
        """构建完整的统计数据 JSON,聚合任务/项目/专注数据."""
        self._normalize_stats()
        task_stats = self._task_stats()
        project_stats = self._project_stats()
        total_focus_seconds = self._safe_int(self.stats_database.get("totalFocusSeconds"), 0)
        today_focus_seconds = self._safe_int(self.stats_database.get("todayFocusSeconds"), 0)
        return {
            "tasks": task_stats,
            "groups": {"total": len(self.groups_database)},
            "projects": project_stats,
            "focus": {
                "totalSeconds": total_focus_seconds,
                "totalMinutes": total_focus_seconds // 60,
                "todaySeconds": today_focus_seconds,
                "todayMinutes": today_focus_seconds // 60,
                "totalSessions": self._safe_int(self.stats_database.get("totalFocusSessions"), 0),
                "todaySessions": self._safe_int(self.stats_database.get("todayFocusSessions"), 0),
                "completedGroupSessions": self._safe_int(self.stats_database.get("completedGroupSessions"), 0),
                "completedProjectSessions": self._safe_int(self.stats_database.get("completedProjectSessions"), 0),
                "completedTimerSessions": self._safe_int(self.stats_database.get("completedTimerSessions"), 0),
                "lastFocusAt": self.stats_database.get("lastFocusAt")
            }
        }

    def _achievement_definitions(self, stats):
        """定义成就列表及其解锁条件."""
        task_stats = stats["tasks"]
        group_count = stats["groups"]["total"]
        project_stats = stats["projects"]
        focus_stats = stats["focus"]
        all_tasks_done = task_stats["total"] > 0 and task_stats["done"] == task_stats["total"]
        return [
            {
                "id": "first_task_done",
                "title": "初次启动",
                "description": "完成第一个任务",
                "icon": "task_alt",
                "current": task_stats["done"],
                "target": 1
            },
            {
                "id": "focus_60",
                "title": "专注达人",
                "description": "累计专注 60 分钟",
                "icon": "timer",
                "current": focus_stats["totalMinutes"],
                "target": 60
            },
            {
                "id": "three_groups",
                "title": "流程大师",
                "description": "创建 3 个任务流",
                "icon": "account_tree",
                "current": group_count,
                "target": 3
            },
            {
                "id": "perfect_day",
                "title": "完美一天",
                "description": "清空当前所有待办",
                "icon": "stars",
                "current": task_stats["done"] if all_tasks_done else 0,
                "target": max(1, task_stats["total"])
            },
            {
                "id": "project_step",
                "title": "项目推进者",
                "description": "完成一个项目里程碑",
                "icon": "rocket_launch",
                "current": project_stats["doneMilestones"],
                "target": 1
            },
            {
                "id": "island_complete",
                "title": "灵动岛首航",
                "description": "完成一次任务流或项目专注",
                "icon": "hub",
                "current": focus_stats["completedGroupSessions"] + focus_stats["completedProjectSessions"],
                "target": 1
            }
        ]

    def _build_achievements(self):
        """构建成就数据：根据当前统计判断每个成就的解锁状态."""
        stats = self._build_stats()
        if not isinstance(self.achievements_database, dict):
            self.achievements_database = {}
        changed = False
        now = datetime.now().isoformat(timespec="seconds")
        achievements = []
        for item in self._achievement_definitions(stats):
            current = self._safe_int(item.get("current"), 0)
            target = max(1, self._safe_int(item.get("target"), 1))
            unlocked = current >= target
            unlocked_at = self.achievements_database.get(item["id"])
            if unlocked and not unlocked_at:
                unlocked_at = now
                self.achievements_database[item["id"]] = unlocked_at
                changed = True
            is_unlocked = bool(unlocked_at)
            achievements.append({
                **item,
                "current": max(current, target) if is_unlocked else current,
                "target": target,
                "progress": 100 if is_unlocked else min(100, round((current / target) * 100)),
                "unlocked": is_unlocked,
                "unlockedAt": unlocked_at
            })
        if changed:
            self._save_json(self.achievements_file, self.achievements_database)
        return achievements

    def _emit_stats_and_achievements(self):
        """发射统计和成就的更新信号."""
        self.signalStatsUpdated.emit(json.dumps(self._build_stats(), ensure_ascii=False))
        self.signalAchievementsUpdated.emit(json.dumps(self._build_achievements(), ensure_ascii=False))

    def _record_focus_session(self, seconds, mode="timer"):
        """记录一次专注会话：更新总/今日时长和次数,写入 dailyFocusSeconds."""
        seconds = max(0, self._safe_int(seconds, 0))
        if seconds <= 0:
            return
        self._normalize_stats()
        self.stats_database["totalFocusSeconds"] = self._safe_int(self.stats_database.get("totalFocusSeconds"), 0) + seconds
        self.stats_database["todayFocusSeconds"] = self._safe_int(self.stats_database.get("todayFocusSeconds"), 0) + seconds
        self.stats_database["totalFocusSessions"] = self._safe_int(self.stats_database.get("totalFocusSessions"), 0) + 1
        self.stats_database["todayFocusSessions"] = self._safe_int(self.stats_database.get("todayFocusSessions"), 0) + 1
        if mode == "group":
            self.stats_database["completedGroupSessions"] = self._safe_int(self.stats_database.get("completedGroupSessions"), 0) + 1
        elif mode == "project":
            self.stats_database["completedProjectSessions"] = self._safe_int(self.stats_database.get("completedProjectSessions"), 0) + 1
        else:
            self.stats_database["completedTimerSessions"] = self._safe_int(self.stats_database.get("completedTimerSessions"), 0) + 1
        today = self._today()
        self.stats_database["todayDate"] = today
        daily = self.stats_database.setdefault("dailyFocusSeconds", {})
        daily[today] = self._safe_int(daily.get(today), 0) + seconds
        self.stats_database["lastFocusAt"] = datetime.now().isoformat(timespec="seconds")
        self._save_json(self.stats_file, self.stats_database)

    def _long_plan_today_payload(self):
        """计算长期计划今日任务载荷：根据 dateOffset 匹配当天任务并自动导入."""
        state = self.long_plan_database if isinstance(self.long_plan_database, dict) else self._get_default_long_plan()
        if not state.get("active") or not isinstance(state.get("plan"), dict):
            return None
        plan = state["plan"]
        long_plan = plan.get("longPlan") or {}
        cycles = long_plan.get("cycles") or []
        cycle_index = self._safe_int(state.get("currentCycleIndex"), 0)
        if cycle_index >= len(cycles):
            state["pendingReview"] = True
            self._save_json(self.long_plan_file, state)
            return {"pendingReview": True, "plan": plan, "state": state, "message": "当前周期已经结束,需要复盘后生成下一周期."}

        cycle = cycles[cycle_index]
        days = cycle.get("days") or []
        start_date = state.get("startedAt") or self._today()
        try:
            day_offset = max(0, (datetime.strptime(self._today(), "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days)
        except ValueError:
            day_offset = 0
        day = None
        for item in days:
            if self._safe_int(item.get("dateOffset"), -1) == day_offset:
                day = item
                break
        if day is None and day_offset < len(days):
            day = days[day_offset]
        if day is None:
            state["pendingReview"] = True
            self._save_json(self.long_plan_file, state)
            return {"pendingReview": True, "plan": plan, "state": state, "cycle": cycle, "message": "本周期任务已结束,今天适合做周期复盘."}

        today = self._today()
        imported_dates = set(state.get("importedDates") or [])
        imported = False
        added = {"tasks": 0, "groups": 0, "projects": 0}
        if today not in imported_dates:
            tasks = []
            for index, task in enumerate(day.get("tasks") or []):
                title = str(task.get("title") or "").strip()
                if title:
                    tasks.append({
                        "id": self._new_id(30000 + index),
                        "title": title,
                        "meta": str(task.get("meta") or f"长期计划 · {cycle.get('title', '')} · {day.get('focus', '')}"),
                        "done": False
                    })
            added = self._apply_ai_plan({"tasks": tasks, "groups": [], "projects": []}, merge_missing=True)
            state.setdefault("importedDates", []).append(today)
            self._save_json(self.long_plan_file, state)
            imported = True
        return {
            "pendingReview": False,
            "plan": plan,
            "state": state,
            "cycle": cycle,
            "day": day,
            "imported": imported,
            "added": added
        }

    @Slot(result=str)
    def check_daily_welcome(self):
        """[Slot] 每日欢迎检查：判断是否新的一天,返回欢迎提示和长期计划状态."""
        current_date = datetime.now().strftime("%Y-%m-%d")
        last_date = self.daily_record.get("last_date")
        long_plan_today = self._long_plan_today_payload()
        if last_date != current_date:
            self.daily_record["last_date"] = current_date
            self._save_json(self.daily_file, self.daily_record)
            return json.dumps({"need_welcome": True, "longPlan": long_plan_today}, ensure_ascii=False)
        return json.dumps({"need_welcome": False, "longPlan": long_plan_today}, ensure_ascii=False)

    @Slot(result=str)
    def get_stats_json(self):
        return json.dumps(self._build_stats(), ensure_ascii=False)

    @Slot(result=str)
    def get_achievements_json(self):
        return json.dumps(self._build_achievements(), ensure_ascii=False)

    @Slot(result=str)
    def get_tasks_json(self): return json.dumps(self.local_database, ensure_ascii=False)

    @Slot(str, str)
    def add_task(self, title, meta):
        """[Slot] 添加任务：生成 ID,插入列表顶部,保存并发射更新信号."""
        new_item = {"id": int(1000 + len(self.local_database) + len(self.groups_database)*100), "title": title, "meta": meta or "来自客户端", "done": False}
        self.local_database.insert(0, new_item)
        self._save_json(self.tasks_file, self.local_database)
        self.signalTasksUpdated.emit(json.dumps(self.local_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    @Slot(float, bool)
    def toggle_task_status(self, task_id, is_done):
        task_id = int(task_id)
        for task in self.local_database:
            if task["id"] == task_id: task["done"] = is_done; break
        self._save_json(self.tasks_file, self.local_database)
        self.signalTasksUpdated.emit(json.dumps(self.local_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    @Slot(float)
    def delete_task(self, task_id):
        task_id = int(task_id)
        self.local_database = [t for t in self.local_database if t["id"] != task_id]
        self._save_json(self.tasks_file, self.local_database)
        self.signalTasksUpdated.emit(json.dumps(self.local_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    @Slot(result=str)
    def get_groups_json(self): return json.dumps(self.groups_database, ensure_ascii=False)

    @Slot(str)
    def add_group(self, group_json):
        group = json.loads(group_json)
        self.groups_database.append(group)
        self._save_json(self.groups_file, self.groups_database)
        self.signalGroupsUpdated.emit(json.dumps(self.groups_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    @Slot(str)
    def update_group(self, group_json):
        group = json.loads(group_json)
        for i, g in enumerate(self.groups_database):
            if g["id"] == group["id"]: self.groups_database[i] = group; break
        self._save_json(self.groups_file, self.groups_database)
        self.signalGroupsUpdated.emit(json.dumps(self.groups_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    @Slot(float)
    def delete_group(self, group_id):
        group_id = int(group_id)
        self.groups_database = [g for g in self.groups_database if g["id"] != group_id]
        self._save_json(self.groups_file, self.groups_database)
        self.signalGroupsUpdated.emit(json.dumps(self.groups_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    @Slot(result=str)
    def get_projects_json(self): return json.dumps(self.projects_database, ensure_ascii=False)

    @Slot(str)
    def add_project(self, project_json):
        project = json.loads(project_json)
        self.projects_database.append(project)
        self._save_json(self.projects_file, self.projects_database)
        self.signalProjectsUpdated.emit(json.dumps(self.projects_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    @Slot(str)
    def update_project(self, project_json):
        project = json.loads(project_json)
        for i, p in enumerate(self.projects_database):
            if p["id"] == project["id"]: self.projects_database[i] = project; break
        self._save_json(self.projects_file, self.projects_database)
        self.signalProjectsUpdated.emit(json.dumps(self.projects_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    @Slot(float)
    def delete_project(self, project_id):
        project_id = int(project_id)
        self.projects_database = [p for p in self.projects_database if p["id"] != project_id]
        self._save_json(self.projects_file, self.projects_database)
        self.signalProjectsUpdated.emit(json.dumps(self.projects_database, ensure_ascii=False))
        self._emit_stats_and_achievements()

    def _startup_entry_path(self):
        startup_dir = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
        )
        return os.path.join(startup_dir, "FlowDeck_AutoStart.bat")

    def _auto_start_app_name(self):
        return "FlowTodo"

    def _is_packaged_exe(self):
        exe_name = os.path.basename(sys.executable).lower()
        return bool(
            getattr(sys, "frozen", False)
            or "__compiled__" in globals()
            or exe_name not in ("python.exe", "pythonw.exe")
        )

    def _auto_start_command_parts(self):
        """构建自启动命令行：打包版直接用 exe,开发版用 python + 脚本路径."""
        if self._is_packaged_exe():
            return [os.path.abspath(sys.executable)]
        return [os.path.abspath(sys.executable), os.path.abspath(__file__)]

    def _auto_start_command(self):
        return subprocess.list2cmdline(self._auto_start_command_parts())

    def _auto_start_work_dir(self):
        if self._is_packaged_exe():
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(__file__))

    def _run_registry_key_path(self):
        return r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _get_registry_auto_start_value(self):
        if sys.platform != "win32" or winreg is None:
            return None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._run_registry_key_path()) as key:
                value, _ = winreg.QueryValueEx(key, self._auto_start_app_name())
                return str(value)
        except FileNotFoundError:
            return None
        except OSError:
            return None

    def _set_registry_auto_start_value(self, command):
        if sys.platform != "win32" or winreg is None:
            return False
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            self._run_registry_key_path(),
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, self._auto_start_app_name(), 0, winreg.REG_SZ, command)
        return True

    def _delete_registry_auto_start_value(self):
        if sys.platform != "win32" or winreg is None:
            return
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self._run_registry_key_path(),
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, self._auto_start_app_name())
        except FileNotFoundError:
            return
        except OSError:
            return

    def _legacy_startup_entry_matches(self, expected_command):
        entry_path = self._startup_entry_path()
        if not os.path.exists(entry_path):
            return False
        try:
            with open(entry_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return False
        return expected_command.lower() in content.lower()

    def _write_legacy_startup_entry(self, command_parts):
        entry_path = self._startup_entry_path()
        if not entry_path or not os.path.dirname(entry_path):
            raise RuntimeError("无法定位 Windows 启动文件夹")
        os.makedirs(os.path.dirname(entry_path), exist_ok=True)
        escaped_parts = [part.replace("%", "%%") for part in command_parts]
        launch_command = subprocess.list2cmdline(escaped_parts)
        work_dir = self._auto_start_work_dir().replace("%", "%%")
        bat = (
            "@echo off\r\n"
            f'cd /d "{work_dir}"\r\n'
            f'start "" {launch_command}\r\n'
        )
        with open(entry_path, "w", encoding="utf-8") as f:
            f.write(bat)

    def _delete_legacy_startup_entry(self):
        entry_path = self._startup_entry_path()
        if os.path.exists(entry_path):
            os.remove(entry_path)

    def _is_auto_start_enabled(self):
        """检查开机自启是否已启用(优先检查注册表 Run 键,其次启动文件夹)."""
        expected_command = self._auto_start_command()
        registry_value = self._get_registry_auto_start_value()
        if registry_value is not None:
            return registry_value.strip().lower() == expected_command.strip().lower()
        return self._legacy_startup_entry_matches(expected_command)

    def _set_auto_start_enabled(self, enabled):
        """设置开机自启：优先写入注册表 Run 键,失败则回退启动文件夹 .bat."""
        if enabled:
            command = self._auto_start_command()
            if self._set_registry_auto_start_value(command):
                self._delete_legacy_startup_entry()
            else:
                self._write_legacy_startup_entry(self._auto_start_command_parts())
        else:
            self._delete_registry_auto_start_value()
            self._delete_legacy_startup_entry()
        self.settings_database["autoStart"] = bool(enabled)
        self._save_json(self.settings_file, self.settings_database)
        return True

    @Slot(result=str)
    def get_settings_json(self):
        """[Slot] 获取设置 JSON,同时同步开机自启的实际状态."""
        self.settings_database["autoStart"] = self._is_auto_start_enabled()
        return json.dumps(self.settings_database, ensure_ascii=False)

    @Slot(str)
    def save_settings(self, settings_json):
        try:
            settings = json.loads(settings_json)
            if "autoStart" in settings:
                self._set_auto_start_enabled(bool(settings.get("autoStart")))
            self.settings_database.update(settings)
            self._save_json(self.settings_file, self.settings_database)
            self._apply_island_preferences_to_active()
        except Exception as e: print(f"[Python] 保存设置失败: {e}")

    def _island_preferences(self):
        keys = (
            "islandTheme", "islandScale", "islandOpacity", "islandAnchor",
            "islandOffsetX", "islandOffsetY", "islandLayer", "islandLightingEffect", "nativeAccent",
        )
        defaults = self._get_default_settings()
        preferences = {key: self.settings_database.get(key, defaults[key]) for key in keys}
        # The first native build used 18px, which visually sat in the title-bar area.
        # Move that legacy default down without overriding a future explicit offset.
        if preferences["islandOffsetY"] == 18:
            preferences["islandOffsetY"] = defaults["islandOffsetY"]
        return preferences

    def _apply_island_preferences_to_active(self):
        preferences = self._island_preferences()
        for island in list(self.island_windows.values()):
            update_preferences = getattr(island, "update_preferences", None)
            if callable(update_preferences):
                update_preferences(preferences)

    @Slot(bool, result=str)
    def set_auto_start_enabled(self, enabled):
        try:
            self._set_auto_start_enabled(bool(enabled))
            return json.dumps({"ok": True, "enabled": self._is_auto_start_enabled()}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    @Slot(result=bool)
    def get_auto_start_enabled(self):
        return self._is_auto_start_enabled()

    @Slot(str, result=str)
    def get_daily_wallpaper_url(self, seed_json):
        try:
            payload = json.loads(seed_json) if seed_json else {}
        except Exception:
            payload = {}
        seed_text = str(payload.get("seed") or payload.get("suffix") or self._today())
        force = bool(payload.get("force"))
        try:
            req = urllib.request.Request(
                "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=8&mkt=zh-CN",
                headers={"User-Agent": "CheemsTodo/1.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            images = data.get("images") or []
            if not images:
                raise RuntimeError("empty bing wallpaper list")
            seed_value = sum(ord(ch) for ch in seed_text)
            index = seed_value % len(images) if force else 0
            item = images[index]
            url = item.get("url") or ""
            if url.startswith("/"):
                url = f"https://www.bing.com{url}"
            return json.dumps({
                "ok": True,
                "url": url,
                "title": item.get("title") or item.get("copyright") or "Bing 每日壁纸",
                "copyright": item.get("copyright") or "",
                "source": "Bing",
                "index": index
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    def _ai_system_prompt(self, long_mode=False):
        """构建 AI 系统提示词,包含 JSON Schema 和约束规则."""
        base = (
            "你是 Cheems Todo 的个性化规划助手.语气要清楚、具体、专业,不要夸张抒情,"
            "不要编造用户没有给出的背景.用户会告诉你目标、需求或近期状态,你要把它转换成"
            "可以直接导入 Cheems Todo 的每日任务、任务流和项目.\n"
            "输出必须包含两部分：\n"
            "1. 先用 3-5 句中文说明：目标判断、时间约束、执行节奏、今天/本周期先做什么.\n"
            "2. 然后输出且只输出一个 ```json 代码块,JSON 必须是对象,结构如下：\n"
        )
        if long_mode:
            return base + (
                "{\n"
                '  "mode": "long",\n'
                '  "title": "长期计划标题",\n'
                '  "summary": "整体计划摘要",\n'
                '  "tasks": [],\n'
                '  "groups": [{"name": "本周期每日执行任务流", "description": "用途", "steps": [{"name": "步骤名", "duration": 25, "type": "focus"}], "theme": "primary"}],\n'
                '  "projects": [{"name": "长期项目名", "desc": "项目说明", "progress": 0, "taskCount": 4, "milestones": [{"title": "阶段里程碑", "done": false}]}],\n'
                '  "longPlan": {\n'
                '    "goal": "长期目标",\n'
                '    "durationText": "例如：两个月",\n'
                '    "cycleLengthDays": 7,\n'
                '    "totalCycles": 8,\n'
                '    "roadmap": ["第1周期：打基础", "第2周期：巩固", "后续周期：根据复盘动态调整"],\n'
                '    "cycles": [{"index": 1, "title": "第1周期", "goal": "本周期目标", "days": [{"day": 1, "dateOffset": 0, "focus": "今日重点", "tasks": [{"title": "每日任务", "meta": "用时/要求/提示"}]}], "reviewPrompt": "本周期复盘问题"}],\n'
                '    "nextCycleInstruction": "周期结束后根据用户掌握情况生成下一周期."\n'
                "  }\n"
                "}\n"
                "长期计划规则：不要一次性生成完整两个月每日任务；要把长期目标拆为周期,通常 7 天一个周期；"
                "只生成第一个周期的每日任务,后续周期只写 roadmap 概览；当前周期最多 7 天,每天 2-4 个任务."
                "每天任务要按先易后难排列,meta 写清用时、完成标准和资料建议."
                "周期结束需要用户复盘掌握情况后再生成下一周期."
                "如果用户给了明确时间段,durationText 和 totalCycles 必须匹配.字段名必须使用英文."
            )
        return base + (
            "{\n"
            '  "title": "计划标题",\n'
            '  "mode": "short",\n'
            '  "summary": "计划摘要",\n'
            '  "tasks": [{"title": "任务名", "meta": "场景/优先级/提醒", "done": false}],\n'
            '  "groups": [{"name": "任务流名", "description": "用途", "steps": [{"name": "步骤名", "duration": 25, "type": "focus"}], "theme": "primary"}],\n'
            '  "projects": [{"name": "项目名", "desc": "项目说明", "progress": 0, "taskCount": 3, "milestones": [{"title": "里程碑", "done": false}]}]\n'
            "}\n"
            "约束：任务 4-8 个；任务流 1-3 个,每个 3-6 步,每步 duration 为分钟；项目 0-2 个；"
            "不要输出 JSON 以外的第二个代码块；不要在 JSON 内写注释；字段名必须使用英文."
        )

    def _ai_context_message(self):
        """构建 AI 上下文消息,包含当前待办/项目/长期计划状态."""
        pending_tasks = [t.get("title", "") for t in self.local_database if not t.get("done")][:8]
        active_projects = [p.get("name", "") for p in self.projects_database if self._safe_float(p.get("progress"), 0) < 1][:6]
        context = (
            "当前软件数据上下文："
            f"待办任务 {len([t for t in self.local_database if not t.get('done')])} 个,"
            f"任务流 {len(self.groups_database)} 个,项目 {len(self.projects_database)} 个."
            f"待办示例：{pending_tasks or ['暂无']}."
            f"项目示例：{active_projects or ['暂无']}."
            "请避免生成与现有内容明显重复的条目."
        )
        state = self.long_plan_database if isinstance(self.long_plan_database, dict) else {}
        if state.get("active") and isinstance(state.get("plan"), dict):
            plan = state["plan"]
            long_plan = plan.get("longPlan") or {}
            cycle = None
            cycles = long_plan.get("cycles") or []
            cycle_index = self._safe_int(state.get("currentCycleIndex"), 0)
            if 0 <= cycle_index < len(cycles):
                cycle = cycles[cycle_index]
            context += (
                "当前存在 AI 长期计划："
                f"目标《{long_plan.get('goal') or plan.get('title', '')}》,"
                f"周期状态：{'等待复盘' if state.get('pendingReview') else '执行中'}."
            )
            if cycle:
                context += f"当前周期《{cycle.get('title', '')}》,复盘提示：{cycle.get('reviewPrompt', '')}."
            context += "如果用户正在复盘,请根据掌握情况生成下一个周期的每日任务,并保留长期 roadmap."
        return context

    def _ai_chat_endpoint(self):
        base_url = str(self.settings_database.get("aiBaseUrl") or "").strip().rstrip("/")
        if not base_url:
            base_url = "https://api.openai.com/v1"
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    def _ai_request_temperature(self, model):
        base_url = str(self.settings_database.get("aiBaseUrl") or "").strip().lower()
        model_name = str(model or "").strip().lower()
        if "api.moonshot.cn" in base_url or model_name.startswith("kimi"):
            return 1
        return self._safe_float(self.settings_database.get("aiTemperature"), 0.7)

    def _call_ai_chat(self, messages, long_mode=False):
        """调用 OpenAI 兼容 API 发送对话请求,返回助手回复文本."""
        api_key = str(self.settings_database.get("aiApiKey") or "").strip()
        model = str(self.settings_database.get("aiModel") or "gpt-4o-mini").strip()
        if not api_key:
            raise ValueError("请先在设置页填写 AI API Key")
        timeout = self._safe_int(self.settings_database.get("aiTimeout"), 240)
        timeout = max(60, min(600, timeout))
        if long_mode:
            timeout = max(timeout, 240)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": self._ai_request_temperature(model)
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self._ai_chat_endpoint(),
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except (TimeoutError, socket.timeout):
            raise RuntimeError(f"AI 请求超时：接口在 {timeout} 秒内没有返回.长期计划内容较多,可以稍后重试,或在设置页把 AI 请求超时调高.")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"AI 请求失败：HTTP {e.code} {body[:300]}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.timeout):
                raise RuntimeError(f"AI 请求超时：接口在 {timeout} 秒内没有返回.长期计划内容较多,可以稍后重试,或在设置页把 AI 请求超时调高.")
            raise RuntimeError(f"AI 网络连接失败：{e.reason}")
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("AI 返回格式异常,未找到 message.content")

    def _run_ai_plan_request(self, request_json):
        """在后台线程执行 AI 规划请求：校验、调用 API、解析 JSON、应用计划."""
        try:
            payload = json.loads(request_json or "{}")
            raw_messages = payload.get("messages") or []
            long_mode = bool(payload.get("longMode"))
            replace_on_apply = bool(payload.get("replaceOnApply", self.settings_database.get("aiReplaceOnApply", True)))
            active_long_plan = bool(self.long_plan_database.get("active"))
            pending_review = bool(self.long_plan_database.get("pendingReview"))
            if active_long_plan and (not long_mode or not pending_review):
                raise ValueError("当前已有 AI 长期计划.请先放弃当前长期计划；如果是周期复盘,请在周期结束后从开篇页进入 AI 复盘.")
            messages = [
                {"role": "system", "content": self._ai_system_prompt(long_mode=long_mode)},
                {"role": "system", "content": self._ai_context_message()}
            ]
            for item in raw_messages[-10:]:
                if not isinstance(item, dict):
                    continue
                role = item.get("role")
                content = str(item.get("content") or "").strip()
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
            if len(messages) <= 2:
                raise ValueError("请先告诉 AI 你的目标或需求")

            self.signalAiMessage.emit(json.dumps({"role": "assistant", "content": "我先确认目标、时间跨度和每天可投入时间,再拆成任务、任务流和项目结构."}, ensure_ascii=False))
            self.signalAiMessage.emit(json.dumps({"role": "assistant", "content": "如果是长期目标,我只生成当前周期的每日任务,并保留完整路线图；后续周期根据复盘继续调整."}, ensure_ascii=False))
            response_text = self._call_ai_chat(messages, long_mode=long_mode)
            plan = self._normalize_ai_plan(self._extract_json_object(response_text))
            if not long_mode and plan.get("mode") == "long":
                plan["mode"] = "short"
                plan["longPlan"] = None
            saved_path = self._save_ai_plan(plan)
            auto_apply = bool(self.settings_database.get("aiAutoApply", True)) and plan.get("mode") != "long"
            if auto_apply:
                added = self._apply_ai_plan(plan, merge_missing=True, replace_ai=replace_on_apply)
            else:
                added = {"tasks": 0, "groups": 0, "projects": 0}
            assistant_text = re.sub(r"```(?:json)?[\s\S]*?```", "", response_text, flags=re.IGNORECASE).strip()
            if not assistant_text:
                assistant_text = f"已生成《{plan.get('title', 'AI 个性化计划')}》,并准备好导入."
            result = {
                "ok": True,
                "message": assistant_text,
                "plan": plan,
                "path": saved_path,
                "applied": auto_apply,
                "longMode": plan.get("mode") == "long",
                "added": added,
                "counts": {
                    "tasks": len(plan.get("tasks") or []),
                    "groups": len(plan.get("groups") or []),
                    "projects": len(plan.get("projects") or [])
                }
            }
            self.signalAiMessage.emit(json.dumps({"role": "assistant", "content": assistant_text}, ensure_ascii=False))
            persisted_messages = raw_messages + [{"role": "assistant", "content": assistant_text}]
            self._save_ai_state(latest_plan=plan, latest_path=saved_path, messages=persisted_messages)
            self.signalAiPlanReady.emit(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            message = str(e)
            self.signalAiMessage.emit(json.dumps({"role": "assistant", "content": f"AI 规划失败：{message}"}, ensure_ascii=False))
            self.signalAiPlanReady.emit(json.dumps({"ok": False, "error": message}, ensure_ascii=False))

    @Slot(str)
    def request_ai_plan(self, request_json):
        threading.Thread(target=self._run_ai_plan_request, args=(request_json,), daemon=True).start()

    @Slot(str, result=str)
    def apply_ai_plan_json(self, plan_json):
        try:
            payload = json.loads(plan_json)
            if isinstance(payload, dict) and isinstance(payload.get("plan"), dict):
                replace_ai = bool(payload.get("replaceAi", self.settings_database.get("aiReplaceOnApply", True)))
                plan = self._normalize_ai_plan(payload.get("plan"))
            else:
                replace_ai = bool(self.settings_database.get("aiReplaceOnApply", True))
                plan = self._normalize_ai_plan(payload)
            saved_path = self._save_ai_plan(plan)
            added = self._apply_ai_plan(plan, merge_missing=True, replace_ai=replace_ai)
            self._save_ai_state(latest_plan=plan, latest_path=saved_path)
            return json.dumps({"ok": True, "path": saved_path, "added": added}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    @Slot(str, result=str)
    def start_long_plan(self, plan_json):
        try:
            plan = self._normalize_ai_plan(json.loads(plan_json))
            if plan.get("mode") != "long" or not plan.get("longPlan"):
                raise ValueError("这不是有效的长期计划")
            self.long_plan_database = {
                "active": True,
                "plan": plan,
                "startedAt": self._today(),
                "currentCycleIndex": 0,
                "importedDates": [],
                "pendingReview": False
            }
            self._save_json(self.long_plan_file, self.long_plan_database)
            replace_ai = bool(self.settings_database.get("aiReplaceOnApply", True))
            base_added = self._apply_ai_plan({
                "tasks": [],
                "groups": plan.get("groups") or [],
                "projects": plan.get("projects") or []
            }, merge_missing=True, replace_ai=replace_ai)
            today_payload = self._long_plan_today_payload()
            self._save_ai_state(latest_plan=plan)
            return json.dumps({"ok": True, "today": today_payload, "added": base_added, "state": self.long_plan_database}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    @Slot(result=str)
    def abandon_long_plan(self):
        self.long_plan_database = self._get_default_long_plan()
        self._save_json(self.long_plan_file, self.long_plan_database)
        return json.dumps({"ok": True}, ensure_ascii=False)

    @Slot(result=str)
    def get_long_plan_json(self):
        return json.dumps(self.long_plan_database, ensure_ascii=False)

    @Slot(result=str)
    def get_ai_state_json(self):
        return json.dumps(self.ai_state_database if isinstance(self.ai_state_database, dict) else self._get_default_ai_state(), ensure_ascii=False)

    @Slot(str, result=str)
    def save_ai_state_json(self, state_json):
        try:
            state = json.loads(state_json or "{}")
            self._save_ai_state(
                latest_plan=state.get("latestPlan") if "latestPlan" in state else None,
                latest_path=state.get("latestPath") if "latestPath" in state else None,
                messages=state.get("messages") if "messages" in state else None
            )
            return json.dumps({"ok": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    @Slot(result=str)
    def clear_ai_state(self):
        self.ai_state_database = self._get_default_ai_state()
        self._save_json(self.ai_state_file, self.ai_state_database)
        return json.dumps({"ok": True}, ensure_ascii=False)

    @Slot(result=str)
    def clear_ai_messages(self):
        self._save_ai_state(messages=[])
        return json.dumps({"ok": True}, ensure_ascii=False)

    @Slot(result=str)
    def clear_all_user_data(self):
        """[Slot] 清除所有用户数据：重置所有数据库为默认值,删除 AI 计划文件."""
        try:
            self.cancel_focus_session()
            self.shutdown_focus_environment()

            try:
                self._set_auto_start_enabled(False)
            except Exception as e:
                print(f"[Python] disable auto start failed while clearing data: {e}")

            self.local_database = []
            self.groups_database = []
            self.projects_database = []
            self.daily_record = {"last_date": None}
            self.stats_database = self._get_default_stats()
            self.achievements_database = {}
            self.long_plan_database = self._get_default_long_plan()
            self.ai_state_database = self._get_default_ai_state()
            self.settings_database = self._get_default_settings()

            self._save_json(self.tasks_file, self.local_database)
            self._save_json(self.groups_file, self.groups_database)
            self._save_json(self.projects_file, self.projects_database)
            self._save_json(self.daily_file, self.daily_record)
            self._save_json(self.stats_file, self.stats_database)
            self._save_json(self.achievements_file, self.achievements_database)
            self._save_json(self.long_plan_file, self.long_plan_database)
            self._save_json(self.ai_state_file, self.ai_state_database)
            self._save_json(self.settings_file, self.settings_database)

            removed_ai_plans = 0
            if os.path.isdir(self.ai_plans_dir):
                for name in os.listdir(self.ai_plans_dir):
                    path = os.path.join(self.ai_plans_dir, name)
                    if os.path.isfile(path):
                        try:
                            os.remove(path)
                            removed_ai_plans += 1
                        except Exception as e:
                            print(f"[Python] remove ai plan failed: {path} | {e}")

            self._emit_data_updates()
            return json.dumps({
                "ok": True,
                "tasks": self.local_database,
                "groups": self.groups_database,
                "projects": self.projects_database,
                "stats": self._build_stats(),
                "achievements": self._build_achievements(),
                "settings": self.settings_database,
                "longPlan": self.long_plan_database,
                "aiState": self.ai_state_database,
                "removedAiPlans": removed_ai_plans
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    @Slot(result=str)
    def get_clipboard_text(self):
        try:
            clipboard = QApplication.clipboard()
            return clipboard.text() if clipboard else ""
        except Exception:
            return ""

    @Slot(str, result=str)
    def set_clipboard_text(self, text):
        try:
            clipboard = QApplication.clipboard()
            if not clipboard:
                raise RuntimeError("clipboard unavailable")
            clipboard.setText(str(text or ""))
            return json.dumps({"ok": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    @Slot(str, result=str)
    def open_external_url(self, url):
        try:
            webbrowser.open(str(url or ""), new=2)
            return json.dumps({"ok": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    @Slot(str, result=str)
    def parse_ai_plan_json(self, raw_json):
        try:
            raw_text = str(raw_json or "").strip()
            if not raw_text:
                raise ValueError("没有可解析的 JSON 内容")
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                payload = self._extract_json_object(raw_text)
            plan = self._normalize_ai_plan(payload)
            return json.dumps({
                "ok": True,
                "plan": plan,
                "counts": {
                    "tasks": len(plan.get("tasks") or []),
                    "groups": len(plan.get("groups") or []),
                    "projects": len(plan.get("projects") or []),
                    "long": bool(plan.get("mode") == "long" and plan.get("longPlan"))
                }
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    @Slot(str, result=str)
    def import_data_json(self, data_json):
        try:
            data = json.loads(data_json)
            if not isinstance(data, dict):
                raise ValueError("导入文件必须是 JSON 对象")
            self.local_database = data.get("tasks") if isinstance(data.get("tasks"), list) else self.local_database
            self.groups_database = data.get("groups") if isinstance(data.get("groups"), list) else self.groups_database
            self.projects_database = data.get("projects") if isinstance(data.get("projects"), list) else self.projects_database
            self._save_json(self.tasks_file, self.local_database)
            self._save_json(self.groups_file, self.groups_database)
            self._save_json(self.projects_file, self.projects_database)
            self._emit_data_updates()
            return json.dumps({"ok": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    @Slot(result=str)
    def get_current_data_path(self): return self.settings_database.get("dataPath", self.data_dir)

    @Slot()
    def open_directory_dialog(self):
        selected_dir = QFileDialog.getExistingDirectory(QApplication.activeWindow(), "选择数据目录")
        if selected_dir: 
            self.settings_database["dataPath"] = selected_dir
            self._save_json(self.settings_file, self.settings_database)
            self.signalPathSelected.emit(selected_dir)

    def _main_window(self):
        app = QApplication.instance()
        if app is None:
            return None
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                return widget
        return QApplication.activeWindow()

    def _show_main_window(self):
        win = self._main_window()
        if not win:
            return
        win.showNormal()
        win.raise_()
        win.activateWindow()

    def _minimize_main_window(self):
        win = self._main_window()
        if win:
            win.showMinimized()

    def _get_windows_wallpaper(self):
        if sys.platform != "win32":
            return None
        buffer = ctypes.create_unicode_buffer(32768)
        ok = ctypes.windll.user32.SystemParametersInfoW(0x0073, len(buffer), buffer, 0)
        return buffer.value if ok else None

    def _set_windows_wallpaper(self, path):
        if sys.platform != "win32":
            return False
        flags = 0x01 | 0x02  # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        return bool(ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, path or "", flags))

    def _wallpaper_temp_dir(self):
        path = os.path.join(tempfile.gettempdir(), "Cheems_Todo")
        os.makedirs(path, exist_ok=True)
        return path

    def _write_focus_wallpaper(self, data_url):
        """将 Base64 Data URL 解码并写入临时 BMP 文件作为专注壁纸."""
        if not isinstance(data_url, str) or "," not in data_url:
            return None
        try:
            raw = base64.b64decode(data_url.split(",", 1)[1])
        except Exception as e:
            print(f"[Python] 壁纸数据解析失败: {e}")
            return None

        image = QImage()
        if not image.loadFromData(raw):
            print("[Python] 壁纸图片解码失败")
            return None

        path = os.path.join(self._wallpaper_temp_dir(), "focus_wallpaper.bmp")
        if not image.save(path, "BMP"):
            print("[Python] 壁纸临时文件写入失败")
            return None
        return path

    def _write_focus_wallpaper_from_url(self, url):
        """从 URL 下载壁纸图片并写入临时 BMP 文件."""
        if not isinstance(url, str) or not url.strip():
            return None
        try:
            req = urllib.request.Request(url.strip(), headers={"User-Agent": "FlowDeck/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw = resp.read()
        except Exception as e:
            print(f"[Python] daily wallpaper download failed: {e}")
            return None

        image = QImage()
        if not image.loadFromData(raw):
            print("[Python] daily wallpaper decode failed")
            return None

        path = os.path.join(self._wallpaper_temp_dir(), "focus_daily_wallpaper.bmp")
        if not image.save(path, "BMP"):
            print("[Python] daily wallpaper temp file write failed")
            return None
        return path

    def _cleanup_focus_wallpaper_file(self):
        if not self._focus_wallpaper_file:
            return
        try:
            root = os.path.abspath(self._wallpaper_temp_dir())
            path = os.path.abspath(self._focus_wallpaper_file)
            if path.startswith(root + os.sep) and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[Python] 清理专注壁纸临时文件失败: {e}")
        finally:
            self._focus_wallpaper_file = None

    def _write_focus_noise_file(self, data_url, name="white-noise"):
        """将 Base64 白噪音 Data URL 解码并写入临时音频文件."""
        if not isinstance(data_url, str) or "," not in data_url:
            return None
        try:
            header, payload = data_url.split(",", 1)
            raw = base64.b64decode(payload)
        except Exception as e:
            print(f"[Python] 白噪音数据解析失败: {e}")
            return None

        if not raw:
            return None

        mime = ""
        if header.startswith("data:"):
            mime = header[5:].split(";", 1)[0].lower()
        ext = {
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/ogg": ".ogg",
            "audio/webm": ".webm",
            "audio/aac": ".aac",
            "audio/mp4": ".m4a",
        }.get(mime, os.path.splitext(str(name or ""))[1].lower())
        if ext not in (".mp3", ".wav", ".ogg", ".webm", ".aac", ".m4a"):
            ext = ".audio"

        path = os.path.join(self._wallpaper_temp_dir(), f"focus_noise_{uuid.uuid4().hex}{ext}")
        try:
            with open(path, "wb") as f:
                f.write(raw)
            self._focus_noise_file = path
            return QUrl.fromLocalFile(path).toString()
        except Exception as e:
            print(f"[Python] 白噪音临时文件写入失败: {e}")
            return None

    def _cleanup_focus_noise_file(self):
        if not self._focus_noise_file:
            return
        try:
            root = os.path.abspath(self._wallpaper_temp_dir())
            path = os.path.abspath(self._focus_noise_file)
            if path.startswith(root + os.sep) and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[Python] 清理白噪音临时文件失败: {e}")
        finally:
            self._focus_noise_file = None

    def _default_focus_guard_apps(self):
        """返回护盾默认白名单：系统关键进程(资源管理器/任务管理器/设置等)."""
        return [
            {"name": "Windows 资源管理器", "process": "explorer.exe", "path": "", "system": True},
            {"name": "任务管理器", "process": "taskmgr.exe", "path": "", "system": True},
            {"name": "Windows 设置", "process": "systemsettings.exe", "path": "", "system": True},
            {"name": "开始菜单", "process": "startmenuexperiencehost.exe", "path": "", "system": True},
            {"name": "Windows 搜索", "process": "searchhost.exe", "path": "", "system": True},
            {"name": "输入法与文本服务", "process": "textinputhost.exe", "path": "", "system": True},
            {"name": "桌面窗口管理器", "process": "dwm.exe", "path": "", "system": True},
        ]

    def _normalize_process_value(self, value):
        return str(value or "").strip().strip('"').lower()

    def _extract_exe_path(self, value):
        text = str(value or "").strip()
        if not text:
            return ""
        if text.startswith('"'):
            end = text.find('"', 1)
            if end > 1:
                text = text[1:end]
        else:
            text = text.split(",", 1)[0].strip()
            exe_index = text.lower().find(".exe")
            if exe_index != -1:
                text = text[:exe_index + 4]
        text = os.path.expandvars(text).strip().strip('"')
        return text if text.lower().endswith(".exe") else ""

    def _find_installed_app_exe(self, display_icon, install_location, display_name):
        exe_path = self._extract_exe_path(display_icon)
        if exe_path and os.path.exists(exe_path):
            return exe_path
        folder = os.path.expandvars(str(install_location or "").strip().strip('"'))
        if not folder or not os.path.isdir(folder):
            return ""
        try:
            candidates = []
            wanted = self._fingerprint(display_name)
            for name in os.listdir(folder):
                if not name.lower().endswith(".exe"):
                    continue
                path = os.path.join(folder, name)
                if not os.path.isfile(path):
                    continue
                exe_key = self._fingerprint(os.path.splitext(name)[0])
                score = 0 if wanted and (exe_key in wanted or wanted in exe_key) else 1
                candidates.append((score, name.lower(), path))
            if candidates:
                candidates.sort()
                return candidates[0][2]
        except Exception:
            pass
        return ""

    def _read_uninstall_apps_from_registry(self):
        """从 Windows 注册表读取已安装应用列表(Uninstall 键),供护盾白名单选择."""
        if sys.platform != "win32" or winreg is None:
            return []
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        apps = []
        for hive, key_path in roots:
            try:
                with winreg.OpenKey(hive, key_path) as root_key:
                    for index in range(winreg.QueryInfoKey(root_key)[0]):
                        try:
                            sub_name = winreg.EnumKey(root_key, index)
                            with winreg.OpenKey(root_key, sub_name) as app_key:
                                def read_value(name, default=""):
                                    try:
                                        value, _ = winreg.QueryValueEx(app_key, name)
                                        return value
                                    except OSError:
                                        return default

                                if read_value("SystemComponent", 0):
                                    continue
                                display_name = str(read_value("DisplayName", "") or "").strip()
                                if not display_name:
                                    continue
                                exe_path = self._find_installed_app_exe(
                                    read_value("DisplayIcon", ""),
                                    read_value("InstallLocation", ""),
                                    display_name
                                )
                                process = os.path.basename(exe_path).lower() if exe_path else ""
                                if process:
                                    apps.append({
                                        "name": display_name,
                                        "process": process,
                                        "path": exe_path,
                                        "system": False
                                    })
                        except OSError:
                            continue
            except OSError:
                continue
        return apps

    @Slot(result=str)
    def get_focus_guard_apps_json(self):
        seen = set()
        merged = []
        for app in self._default_focus_guard_apps() + self._read_uninstall_apps_from_registry():
            process = self._normalize_process_value(app.get("process"))
            path = self._normalize_process_value(app.get("path"))
            key = path or process
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append({
                "name": str(app.get("name") or process),
                "process": process,
                "path": str(app.get("path") or ""),
                "system": bool(app.get("system"))
            })
        system_apps = [app for app in merged if app.get("system")]
        user_apps = sorted([app for app in merged if not app.get("system")], key=lambda item: item.get("name", "").lower())
        return json.dumps(system_apps + user_apps, ensure_ascii=False)

    def _process_image_path(self, pid):
        if sys.platform != "win32" or not pid:
            return ""
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
            handle = kernel32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                return ""
            try:
                size = ctypes.wintypes.DWORD(32768)
                buffer = ctypes.create_unicode_buffer(size.value)
                if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                    return buffer.value
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return ""
        return ""

    def _focus_guard_allowed_values(self, options):
        values = set()
        options = options or {}
        if "guardWhitelist" in options:
            apps = options.get("guardWhitelist")
        elif "focusGuardWhitelist" in options:
            apps = options.get("focusGuardWhitelist")
        else:
            apps = self._default_focus_guard_apps()
        if not isinstance(apps, list):
            apps = self._default_focus_guard_apps()
        for app in apps:
            if isinstance(app, dict):
                process = self._normalize_process_value(app.get("process"))
                path = self._normalize_process_value(app.get("path"))
            else:
                process = self._normalize_process_value(app)
                path = ""
            if process:
                values.add(process)
            if path:
                values.add(path)
                values.add(os.path.basename(path).lower())
        return values

    def _foreground_window_info(self):
        """获取 Windows 当前前台窗口信息(句柄/进程名/标题/路径)."""
        if sys.platform != "win32":
            return None
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(max(1, length + 1))
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = (buffer.value or "").strip()
            process_path = self._process_image_path(pid.value)
            process_name = os.path.basename(process_path).lower() if process_path else ""
            return int(hwnd), int(pid.value), title, process_name, process_path
        except Exception as e:
            print(f"[Python] 前台窗口检测失败: {e}")
            return None

    def _start_focus_guard(self, options=None):
        """启动专注护盾：定时检测前台窗口,非白名单应用则弹提醒."""
        self._focus_guard_enabled = True
        self._focus_guard_allowed_apps = self._focus_guard_allowed_values(options or {})
        self._focus_guard_last_hwnd = None
        self._focus_guard_last_alert_at = datetime.now().timestamp() + 2.5
        if not self._focus_guard_timer.isActive():
            self._focus_guard_timer.start()

    def _stop_focus_guard(self):
        """停止专注护盾检测."""
        self._focus_guard_enabled = False
        self._focus_guard_allowed_apps = set()
        self._focus_guard_last_hwnd = None
        self._focus_guard_last_alert_at = 0
        if self._focus_guard_timer.isActive():
            self._focus_guard_timer.stop()

    def _check_focus_guard(self):
        """护盾检测逻辑：获取前台窗口,判断是否需要发送提醒."""
        if not self._focus_guard_enabled or not self.active_focus_session:
            return
        info = self._foreground_window_info()
        if not info:
            return
        hwnd, pid, title, process_name, process_path = info
        if pid == os.getpid() or not title:
            return
        process_key = self._normalize_process_value(process_name)
        path_key = self._normalize_process_value(process_path)
        if process_key in self._focus_guard_allowed_apps or path_key in self._focus_guard_allowed_apps:
            return
        now = datetime.now().timestamp()
        if now - self._focus_guard_last_alert_at < 10:
            return
        self._focus_guard_last_hwnd = hwnd
        self._focus_guard_last_alert_at = now
        self._notify_focus_guard(title)

    def _notify_focus_guard(self, title):
        """发送护盾提醒：Windows 通知 + 灵动岛内 guard_banner 横幅."""
        app_title = str(title or "其他应用").strip()[:60]
        message = f"检测到你切到了「{app_title}」,先回到当前专注任务."
        send_windows_notification("CheemsTodo 专注护盾", message, duration=3)
        for island in list(self.island_windows.values()):
            try:
                island.show_guard_alert(app_title)
            except RuntimeError:
                pass
            except Exception as e:
                print(f"[Python] 灵动岛护盾提醒失败: {e}")

    def _apply_focus_environment(self, options):
        """应用专注环境配置：切换壁纸、启动护盾检测."""
        options = options or {}
        self._restore_focus_environment()
        self._focus_environment_active = True

        if options.get("wallpaperEnabled") and (options.get("wallpaperData") or options.get("wallpaperUrl")):
            original_wallpaper = self._get_windows_wallpaper()
            wallpaper_path = None
            if options.get("wallpaperUrl"):
                wallpaper_path = self._write_focus_wallpaper_from_url(options.get("wallpaperUrl"))
            if not wallpaper_path and options.get("wallpaperData"):
                wallpaper_path = self._write_focus_wallpaper(options.get("wallpaperData"))
            if wallpaper_path and self._set_windows_wallpaper(wallpaper_path):
                self._system_wallpaper_before_focus = original_wallpaper
                self._system_wallpaper_changed = True
                self._focus_wallpaper_file = wallpaper_path
            else:
                send_windows_notification("CheemsTodo", "Windows 壁纸切换失败,已继续启动专注.", duration=3)

        if options.get("disableOtherApps") or options.get("disableApps"):
            self._start_focus_guard(options)
            send_windows_notification("CheemsTodo 专注护盾", "已开启前台应用检测,切换到其他软件会提醒你.", duration=3)

    def _restore_focus_environment(self):
        """恢复专注前环境：还原壁纸、停止护盾、清理临时文件."""
        self._stop_focus_guard()
        if self._system_wallpaper_changed:
            self._set_windows_wallpaper(self._system_wallpaper_before_focus or "")
            self._system_wallpaper_before_focus = None
            self._system_wallpaper_changed = False
        self._cleanup_focus_wallpaper_file()
        self._cleanup_focus_noise_file()
        self._focus_environment_active = False

    def shutdown_focus_environment(self):
        """强制关闭所有灵动岛并恢复专注环境(窗口关闭时调用)."""
        for island in list(self.island_windows.values()):
            try:
                island.cancel_focus()
            except RuntimeError:
                pass
        self._restore_focus_environment()

    def _public_focus_options(self, options):
        """提取专注选项的公开字段(供前端显示),过滤敏感数据."""
        options = options or {}
        return {
            "includeBreaks": bool(options.get("includeBreaks")),
            "breakMinutes": options.get("breakMinutes"),
            "disableOtherApps": bool(options.get("disableOtherApps") or options.get("disableApps")),
            "disableApps": bool(options.get("disableOtherApps") or options.get("disableApps")),
            "wallpaperEnabled": bool(options.get("wallpaperEnabled")),
            "wallpaperSource": str(options.get("wallpaperSource") or ""),
            "wallpaperTitle": str(options.get("wallpaperTitle") or ""),
            "whiteNoiseEnabled": bool(options.get("whiteNoiseEnabled") or options.get("whiteNoise")),
            "whiteNoise": bool(options.get("whiteNoiseEnabled") or options.get("whiteNoise")),
            "whiteNoiseName": str(options.get("whiteNoiseName") or ""),
            "docsReady": bool(options.get("docsReady")),
        }

    def _island_focus_options(self, options):
        """处理专注选项中的灵动岛专用字段：白噪音 Data URL → 本地文件路径."""
        options = dict(options or {})
        if (options.get("whiteNoiseEnabled") or options.get("whiteNoise")) and options.get("whiteNoiseData"):
            noise_url = self._write_focus_noise_file(options.get("whiteNoiseData"), options.get("whiteNoiseName"))
            if noise_url:
                options["whiteNoiseData"] = noise_url
            else:
                options["whiteNoiseEnabled"] = False
                options["whiteNoise"] = False
                options.pop("whiteNoiseData", None)
                send_windows_notification("CheemsTodo", "白噪音加载失败,已继续启动专注.", duration=3)
        options.pop("wallpaperData", None)
        options.pop("wallpaperUrl", None)
        return options

    def _launch_island(self, tasks, mode, session, options=None):
        """启动灵动岛专注会话：关闭旧岛、应用环境、创建 DynamicIslandBridge."""
        for island in list(self.island_windows.values()):
            try:
                island.cancel_focus()
            except RuntimeError:
                pass
        self.island_windows.clear()

        self._apply_focus_environment(options or {})
        try:
            island_win = DynamicIslandBridge(
                tasks=tasks,
                mode=mode,
                options=self._island_focus_options(options),
                preferences=self._island_preferences(),
            )
            key = id(island_win)
            self.island_windows[key] = island_win
            island_win.destroyed.connect(lambda _obj=None, key=key: self.island_windows.pop(key, None))
            island_win.signalStateChanged.connect(lambda state, key=key: self._handle_island_state(key, state))
            self.active_focus_session = session
            self._emit_focus_session("started")
            island_win.show()
            self._minimize_main_window()
            return True
        except Exception:
            self.active_focus_session = None
            self._restore_focus_environment()
            raise

    def _emit_focus_session(self, event, island_state=None):
        """发射专注会话状态变化信号到前端."""
        session = dict(self.active_focus_session or {})
        if island_state:
            session.update(island_state)
        session["event"] = event
        self.signalFocusSessionChanged.emit(json.dumps(session, ensure_ascii=False))

    def _handle_island_state(self, key, state_json):
        """处理灵动岛状态回调：完成/取消时执行对应的收尾逻辑."""
        try:
            state = json.loads(state_json)
        except Exception as e:
            print(f"[Python] island state parse failed: {e}")
            return

        event = state.get("event", "updated")
        if event == "completed":
            self._complete_focus_session(state)
        elif event == "cancelled":
            self._cancel_focus_session(state)
        else:
            self._emit_focus_session(event, state)

    def _complete_focus_session(self, state):
        """完成专注会话：记录时长、更新项目进度、恢复环境、显示主窗口."""
        session = self.active_focus_session or {}
        completed_seconds = session.get("focusSeconds") or state.get("totalSeconds") or session.get("totalSeconds") or state.get("completedSeconds") or 0
        self._record_focus_session(completed_seconds, session.get("mode") or state.get("mode") or "timer")
        if session.get("mode") == "project":
            self._apply_project_focus_progress(session)
        self._emit_stats_and_achievements()
        self._emit_focus_session("completed", state)
        self.active_focus_session = None
        self._restore_focus_environment()
        self._show_main_window()

    def _cancel_focus_session(self, state):
        """取消专注会话：恢复环境、显示主窗口."""
        self._emit_focus_session("cancelled", state)
        self.active_focus_session = None
        self._restore_focus_environment()
        self._show_main_window()

    def _apply_project_focus_progress(self, session):
        """将项目专注完成后的里程碑进度同步到数据库."""
        project_id = session.get("projectId")
        target_milestones = set(session.get("targetMilestones") or [])
        target_indexes = set()
        for index in session.get("targetMilestoneIndexes") or []:
            try:
                target_indexes.add(int(index))
            except (TypeError, ValueError):
                pass
        if project_id is None:
            return

        for project in self.projects_database:
            if project.get("id") != project_id:
                continue

            milestones = project.get("milestones") or []
            if milestones and (target_indexes or target_milestones):
                for index, milestone in enumerate(milestones):
                    if (target_indexes and index in target_indexes) or (not target_indexes and milestone.get("title") in target_milestones):
                        milestone["done"] = True
                done_count = sum(1 for milestone in milestones if milestone.get("done"))
                project["progress"] = min(1.0, done_count / len(milestones))
            else:
                project["progress"] = min(1.0, float(project.get("progress", 0) or 0) + 0.1)

            self._save_json(self.projects_file, self.projects_database)
            self.signalProjectsUpdated.emit(json.dumps(self.projects_database, ensure_ascii=False))
            break

    @Slot(float)
    def record_local_focus_session(self, seconds):
        self._record_focus_session(seconds, "timer")
        self._emit_stats_and_achievements()

    def _positive_int(self, value, default, minimum=1):
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            number = default
        return max(minimum, number)

    @Slot(str)
    def start_single_task(self, task_json):
        """[Slot] 启动单任务专注：将单个任务包装为灵动岛任务链."""
        try:
            payload = json.loads(task_json)
        except Exception as e:
            print(f'[Python] start_single_task JSON 解析失败: {e}')
            return

        title = str(payload.get("title") or "推荐任务").strip() or "推荐任务"
        subtitle = str(payload.get("subtitle") or "单任务专注").strip() or "单任务专注"
        minutes = self._positive_int(payload.get("minutes", 25), 25, minimum=1)
        task_id = payload.get("taskId")
        island_tasks = [{
            "title": title,
            "subtitle": subtitle,
            "time": minutes * 60,
            "type": "focus"
        }]
        session = {
            "mode": "single",
            "title": title,
            "subtitle": subtitle,
            "taskId": task_id,
            "totalSeconds": minutes * 60,
            "focusSeconds": minutes * 60,
            "totalTasks": 1,
        }
        try:
            self._launch_island(island_tasks, mode="single", session=session)
        except Exception as e:
            print(f'[Python] Failed to launch single task island: {e}')
            return False
        return True

    @Slot(str)
    def start_group(self, group_json):
        """[Slot] 启动任务流专注：将 group steps 转为灵动岛任务链(可选休息间隔)."""
        try:
            payload = json.loads(group_json)
        except Exception as e:
            print(f'[Python] start_group JSON 解析失败: {e}')
            return

        tasks = payload.get('tasks', [])
        options = payload.get('options', {})
        group_name = "任务流专注"
        group_id = payload.get('groupId')
        for group in self.groups_database:
            if group.get('id') == group_id:
                group_name = group.get('name', group_name)
                break

        island_tasks = []
        break_minutes = self._positive_int(options.get('breakMinutes', 5), 5, minimum=1)
        include_breaks = bool(options.get('includeBreaks'))
        valid_tasks = [t for t in tasks if t.get('title')]

        for index, task in enumerate(valid_tasks):
            minutes = self._positive_int(task.get('time', 25), 25, minimum=1)
            island_tasks.append({
                "title": task.get('title', '任务'),
                "subtitle": task.get('subtitle') or group_name,
                "time": minutes * 60,
                "type": task.get('type', 'focus')
            })
            if include_breaks and index < len(valid_tasks) - 1:
                island_tasks.append({
                    "title": "短休息",
                    "subtitle": group_name,
                    "time": break_minutes * 60,
                    "type": "break"
                })

        if not island_tasks:
            return False

        try:
            session = {
                "mode": "group",
                "title": group_name,
                "subtitle": f"{len(island_tasks)} 个阶段",
                "groupId": group_id,
                "totalSeconds": sum(task["time"] for task in island_tasks),
                "focusSeconds": sum(task["time"] for task in island_tasks if task.get("type") == "focus"),
                "totalTasks": len(island_tasks),
                "options": self._public_focus_options(options),
            }
            return bool(self._launch_island(island_tasks, mode="group", session=session, options=options))
        except Exception as e:
            print('[Python] Failed to launch island:', e)
            return False

    @Slot(str)
    def start_project(self, project_json):
        """[Slot] 启动项目专注：将指定里程碑打包发送给灵动岛,按里程碑分配时间."""
        """项目专注：将项目里程碑打包发送给灵动岛,启动倒计时专注"""
        try: payload = json.loads(project_json)
        except Exception as e:
            print(f'[Python] start_project JSON 解析失败: {e}')
            return
        project_id = payload.get('projectId')
        goal = payload.get('goal', '')
        target_milestones = payload.get('targetMilestones', [])
        target_milestone_indexes = payload.get('targetMilestoneIndexes', [])
        options = payload.get('options', {})
        try:
            estimated_hours = float(options.get('estimatedHours', 2.0))
        except (TypeError, ValueError):
            estimated_hours = 2.0
        estimated_hours = max(0.1, estimated_hours)

        # 查找项目名称
        project_name = "项目专注"
        for proj in self.projects_database:
            if proj.get('id') == project_id:
                project_name = proj.get('name', '项目专注')
                break

        if not target_milestones:
            print('[Python] start_project: 没有里程碑数据')
            return False

        # 每个里程碑分配时间：总时间 / 里程碑数量
        total_minutes = int(estimated_hours * 60)
        per_milestone_minutes = max(5, total_minutes // len(target_milestones))

        island_tasks = []
        for i, ms in enumerate(target_milestones):
            island_tasks.append({
                "title": ms,
                "subtitle": f"{project_name} · {goal}",
                "time": per_milestone_minutes * 60,  # 转换为秒
                "type": "focus"
            })

        if not island_tasks:
            return False

        try:
            session = {
                "mode": "project",
                "title": project_name,
                "subtitle": goal,
                "projectId": project_id,
                "targetMilestones": target_milestones,
                "targetMilestoneIndexes": target_milestone_indexes,
                "totalSeconds": sum(task["time"] for task in island_tasks),
                "focusSeconds": sum(task["time"] for task in island_tasks if task.get("type") == "focus"),
                "totalTasks": len(island_tasks),
                "options": self._public_focus_options(options),
            }
            return bool(self._launch_island(island_tasks, mode="project", session=session, options=options))
        except Exception as e:
            print(f'[Python] Failed to launch project island: {e}')
            return False

    @Slot()
    def cancel_focus_session(self):
        for island in list(self.island_windows.values()):
            try:
                island.cancel_focus()
            except RuntimeError:
                pass

    @Slot()
    def start_window_move(self):
        if QApplication.instance().activeWindow(): QApplication.instance().activeWindow().windowHandle().startSystemMove()
    @Slot()
    def minimize_window(self):
        if QApplication.instance().activeWindow(): QApplication.instance().activeWindow().showMinimized()
    @Slot()
    def toggle_maximize_window(self):
        win = QApplication.instance().activeWindow()
        if not win: return
        target_is_maximized = not getattr(win, '_is_maximized', False)
        win._is_maximized = target_is_maximized
        self.signalWindowStateChanged.emit(target_is_maximized)
        if target_is_maximized:
            win._normal_geometry = win.geometry()
            target_geo = win.screen().availableGeometry()
        else: target_geo = win._normal_geometry
        win.setGeometry(target_geo)
        try:
            win._update_rounded_mask()
        except Exception:
            pass
    @Slot()
    def close_window(self):
        if QApplication.instance().activeWindow(): QApplication.instance().activeWindow().close()

    @Slot(result=str)
    def show_desktop_widgets(self):
        if self.desktop_widgets_window is None:
            return json.dumps({"ok": False, "error": "Desktop widgets are not available"}, ensure_ascii=False)
        self.desktop_widgets_window.show_hub()
        return json.dumps({"ok": True, "visible": True}, ensure_ascii=False)

    @Slot(result=str)
    def hide_desktop_widgets(self):
        if self.desktop_widgets_window is None:
            return json.dumps({"ok": False, "error": "Desktop widgets are not available"}, ensure_ascii=False)
        self.desktop_widgets_window.hide()
        return json.dumps({"ok": True, "visible": False}, ensure_ascii=False)

    @Slot(result=str)
    def toggle_desktop_widgets(self):
        if self.desktop_widgets_window is None:
            return json.dumps({"ok": False, "error": "Desktop widgets are not available"}, ensure_ascii=False)
        if self.desktop_widgets_window.isVisible():
            self.desktop_widgets_window.hide()
            visible = False
        else:
            self.desktop_widgets_window.show_hub()
            visible = True
        return json.dumps({"ok": True, "visible": visible}, ensure_ascii=False)

class MainWindow(QMainWindow):
    """应用主窗口.

    无边框 + 稳定不透明背景,内嵌 NoZoomWebView 加载前端 index.html,
    通过 QWebChannel 注册 BackendBridge 与前端双向通信.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cheems Todo - M3 Desktop Framework")
        self.resize(1280, 800)
        self._is_maximized = False
        self._normal_geometry = self.geometry()
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        self.setAutoFillBackground(True)
        self.setStyleSheet("QMainWindow { background: #1C1B1F; }")
        
        self.browser = NoZoomWebView()
        self.browser.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.browser.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.browser.setStyleSheet("background: #1C1B1F;")
        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        self.channel = QWebChannel()
        self.bridge = BackendBridge()
        self.desktop_widgets = DesktopWidgetsProcess(self.bridge.data_dir)
        self.bridge.attach_desktop_widgets(self.desktop_widgets)
        self.channel.registerObject("pyBackend", self.bridge)
        self.browser.page().setWebChannel(self.channel)

        html_path = os.path.join(os.path.dirname(__file__), "index.html")
        self.browser.setUrl(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.browser)

    def _update_rounded_mask(self):
        """保留旧调用点；圆角由 Windows DWM 绘制，避免锯齿 QRegion 遮罩。"""
        self._apply_windows_corner_preference()

    def _apply_windows_corner_preference(self):
        """Use Windows' antialiased compositor corners when available."""
        if sys.platform != "win32":
            return
        preference_value = 1 if getattr(self, "_is_maximized", False) else 2
        if getattr(self, "_dwm_corner_preference", None) == preference_value:
            return
        try:
            preference = ctypes.c_int(preference_value)
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(int(self.winId())),
                33,  # DWMWA_WINDOW_CORNER_PREFERENCE
                ctypes.byref(preference),
                ctypes.sizeof(preference),
            )
            if result == 0:
                self._dwm_corner_preference = preference_value
        except (AttributeError, OSError):
            # Windows 10 does not expose this attribute; opaque square edges
            # are preferable to a jagged software mask and compositor flicker.
            self._dwm_corner_preference = preference_value

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_windows_corner_preference()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            try:
                self.bridge.signalAppActivated.emit()
            except Exception as e:
                print(f"[Python] app activation signal failed: {e}")

    def closeEvent(self, event):
        """窗口关闭事件：先恢复专注环境、关闭桌面小组件,再执行默认关闭."""
        try:
            self.bridge.shutdown_focus_environment()
        except Exception as e:
            print(f"[Python] 关闭窗口时恢复专注环境失败: {e}")
        try:
            if self.desktop_widgets is not None:
                self.desktop_widgets.shutdown()
        except Exception:
            pass
        super().closeEvent(event)

# ── 应用入口 ────────────────────────────────────────────
if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setStyleSheet((app.styleSheet() or "") + "\n" + HIDE_SCROLLBAR_QSS)

    runtime_windows = {"startup": None, "main": None}

    def launch_main_window():
        try:
            runtime_windows["main"] = MainWindow()
        except Exception:
            errors = ["软件初始化失败：\n" + traceback.format_exc()]
            if runtime_windows["startup"] is None:
                runtime_windows["startup"] = StartupCheckWindow(errors, launch_main_window)
            else:
                runtime_windows["startup"].set_errors(errors)
            runtime_windows["startup"].show()
            return

        if runtime_windows["startup"] is not None:
            runtime_windows["startup"].close()
        runtime_windows["main"].show()

    startup_errors = run_startup_preflight()
    if startup_errors:
        runtime_windows["startup"] = StartupCheckWindow(startup_errors, launch_main_window)
        runtime_windows["startup"].show()
    else:
        launch_main_window()

    sys.exit(app.exec())
