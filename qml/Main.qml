import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentWindow {
    id: window
    visible: true
    title: "FlowTodo"
    width: 1180
    height: 760
    minimumWidth: 900
    minimumHeight: 620
    navigationView.navMinimumExpandWidth: 960
    navigationView.navExpandWidth: 224

    navigationItems: [
        {
            title: "今日任务",
            page: Qt.resolvedUrl("pages/HomeDashboard.qml"),
            icon: "ic_fluent_checkmark_circle_20_regular"
        },
        {
            title: "日程",
            page: Qt.resolvedUrl("pages/ScheduleWorkspace.qml"),
            icon: "ic_fluent_calendar_ltr_20_regular"
        },
        {
            title: "任务流",
            page: Qt.resolvedUrl("pages/GroupsWorkspace.qml"),
            icon: "ic_fluent_flow_20_regular"
        },
        {
            title: "项目",
            page: Qt.resolvedUrl("pages/ProjectsWorkspace.qml"),
            icon: "ic_fluent_board_20_regular"
        },
        {
            title: "专注模式",
            page: Qt.resolvedUrl("pages/FocusWorkspace.qml"),
            icon: "ic_fluent_timer_20_regular"
        },
        {
            title: "AI 规划",
            page: Qt.resolvedUrl("pages/AiWorkspace.qml"),
            icon: "ic_fluent_sparkle_20_regular"
        },
        {
            title: "账户统计",
            page: Qt.resolvedUrl("pages/AccountOverview.qml"),
            icon: "ic_fluent_person_20_regular"
        },
        {
            title: "桌面小组件",
            page: Qt.resolvedUrl("pages/WidgetHub.qml"),
            icon: "ic_fluent_apps_list_detail_20_regular",
            position: Position.Bottom
        },
        {
            title: "桌面便签",
            page: Qt.resolvedUrl("pages/NoteHub.qml"),
            icon: "ic_fluent_note_20_regular",
            position: Position.Bottom
        },
        {
            title: "系统设置",
            page: Qt.resolvedUrl("pages/SettingsHub.qml"),
            icon: "ic_fluent_settings_20_regular",
            position: Position.Bottom
        }
    ]

    function applySavedAppearance() {
        var mode = String(Backend.getSetting("theme", "auto"))
        Theme.setTheme(mode === "dark" ? Theme.mode.Dark
            : mode === "light" ? Theme.mode.Light : Theme.mode.Auto)

        var accents = {
            "default": "#4099b2",
            "cw1": "#65758b",
            "win10": "#0078d4",
            "material": "#7054b8"
        }
        var uiTheme = String(Backend.getSetting("nativeUiTheme", "material"))
        var customAccent = String(Backend.getSetting("nativeAccent", ""))
        Theme.setThemeColor(customAccent.length ? customAccent : (accents[uiTheme] || accents.material))
        Theme.setBackdropEffect(String(Backend.getSetting("nativeBackdrop", "none")))
    }

    navigationView.objectName: "MainNavigationView"

    function openSettingsPage() {
        navigationView.push(Qt.resolvedUrl("pages/SettingsPage.qml"))
    }

    function openFocusPreparation(kind, itemId) {
        window.showNormal()
        window.raise()
        window.requestActivate()
        if (kind === "task") {
            navigationView.safePush(Qt.resolvedUrl("pages/TaskPrepNative.qml"), true, false, { taskId: itemId })
        } else if (kind === "group") {
            navigationView.safePush(Qt.resolvedUrl("pages/GroupPrepWorkspace.qml"), true, false, { groupId: itemId })
        } else if (kind === "project") {
            navigationView.safePush(Qt.resolvedUrl("pages/ProjectPrepNative.qml"), true, false, { projectId: itemId })
        }
    }

    DesktopTodoWidget {
        id: desktopWidget
        visible: false
    }

    Timer {
        interval: 160
        running: true
        repeat: false
        onTriggered: {
            window.applySavedAppearance()
            if (Boolean(Backend.getSetting("desktopWidgetAutoShow", false)))
                desktopWidget.showWidget()
        }
    }

    Connections {
        target: Backend
        function onSettingsChanged() {
            window.applySavedAppearance()
        }
        function onDesktopWidgetVisibilityRequested(show) {
            if (show)
                desktopWidget.showWidget()
            else
                desktopWidget.hideWidget()
        }
        function onFocusPreparationRequested(kind, itemId) {
            window.openFocusPreparation(kind, itemId)
        }
        function onMessageRequested(level, title, message) {
            var severity = level === "success" ? Severity.Success
                : level === "warning" ? Severity.Warning
                : level === "error" ? Severity.Error : Severity.Info
            window.floatLayer.createInfoBar({
                severity: severity,
                title: title,
                text: message
            })
        }
    }
}
