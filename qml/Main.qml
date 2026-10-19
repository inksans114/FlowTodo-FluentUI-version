import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "i18n"
import "components"

FluentWindow {
    id: window
    visible: true
    title: "FlowTodo"
    icon: Qt.resolvedUrl("../logopromax.ico")
    width: 1180
    height: 760
    minimumWidth: 900
    minimumHeight: 620
    navigationView.navMinimumExpandWidth: 960
    navigationView.navExpandWidth: 224

    navigationItems: [
        { title: I18n.t("今日任务"), page: Qt.resolvedUrl("pages/HomeDashboard.qml"), icon: "ic_fluent_checkmark_circle_20_regular" },
        { title: I18n.t("AI 助手"), page: Qt.resolvedUrl("pages/AiWorkspace.qml"), icon: "ic_fluent_sparkle_20_regular" },
        { title: I18n.t("专注"), page: Qt.resolvedUrl("pages/FocusWorkspace.qml"), icon: "ic_fluent_timer_20_regular" },
        { title: I18n.t("任务流"), page: Qt.resolvedUrl("pages/GroupsWorkspace.qml"), icon: "ic_fluent_flow_20_regular" },
        { title: I18n.t("工具"), page: Qt.resolvedUrl("pages/ToolsHub.qml"), icon: "ic_fluent_apps_list_detail_20_regular", position: Position.Bottom },
        { title: I18n.t("设置"), page: Qt.resolvedUrl("pages/SettingsHub.qml"), icon: "ic_fluent_settings_20_regular", position: Position.Bottom }
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
        var custom = JSON.parse(Backend.appearanceJson)
        if (custom.active) Theme.setThemeColor(custom[Theme.currentTheme.isDark ? "dark" : "light"].accent)
        Theme.setBackdropEffect(String(Backend.getSetting("nativeBackdrop", "none")))
    }

    navigationView.objectName: "MainNavigationView"
    navigationView.navigationBar.footerHeight: 56

    AccountMenu {
        parent: navigationView.navigationBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        collapsed: navigationView.navigationBar.collapsed
        onAccountRequested: {
            var cloud = JSON.parse(Backend.cloudJson)
            navigationView.push(Qt.resolvedUrl(cloud.loggedIn ? "pages/UserAccount.qml" : "pages/LoginPage.qml"))
        }
        onAiRequested: navigationView.push(Qt.resolvedUrl("pages/AiSettings.qml"))
        onSettingsRequested: navigationView.push(Qt.resolvedUrl("pages/SettingsHub.qml"))
        onHelpRequested: window.floatLayer.createInfoBar({severity: Severity.Info, title: I18n.t("账户与额度"), text: I18n.t("当前为本地账户。默认测试服务额度尚未接入；自定义 API 的余额请在服务商处查看。")})
    }

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

    RelationCompletionDialog { id: relationCompletion }
    FlowPreparationDialog { id: flowPreparation }
    FlowInvalidDialog { id: flowInvalid }

    Loader {
        id: studioLoader
        active: false
        source: Qt.resolvedUrl("FocusStudioWindow.qml")
    }

    Loader {
        id: supervisionLoader
        active: false
        source: Qt.resolvedUrl("SupervisionWindow.qml")
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
        function onAccountLoginRequested() { navigationView.push(Qt.resolvedUrl("pages/LoginPage.qml")) }
        target: Backend
        function onFlowInvalidRequested(reason) { flowInvalid.reason = reason; flowInvalid.open() }
        function onFlowPreparationRequested(nodeKey) { window.showNormal(); flowPreparation.present(nodeKey) }
        function onTaskRelationsRequested(nodeKey) {
            navigationView.push(Qt.resolvedUrl("pages/TaskRelationsPage.qml"), {focusNodeKey: nodeKey})
        }
        function onRelationPreparationRequested(nodeKey) {
            flowPreparation.present(nodeKey)
        }
        function onRelationCompletionRequested(nodeKey, complete) {
            window.showNormal()
            window.raise()
            window.requestActivate()
            relationCompletion.present(nodeKey, complete)
        }
        function onSupervisionViewRequested(view) {
            supervisionLoader.active = true
            if (supervisionLoader.item) {
                supervisionLoader.item.present(view)
                if (view === "full") window.hide()
                else window.showNormal()
            } else Backend.stopSupervision()
        }
        function onSupervisionViewClosed() {
            if (supervisionLoader.item) supervisionLoader.item.hide()
            window.showNormal()
        }
        function onImmersiveFocusRequested(scene) {
            if (Backend.focusWebAvailable) {
                window.hide()
                return
            }
            studioLoader.active = true
            if (studioLoader.item) {
                studioLoader.item.showFullScreen()
                studioLoader.item.requestActivate()
                window.hide()
            } else {
                Backend.exitFocusStudio()
            }
        }
        function onImmersiveFocusClosed() {
            if (studioLoader.item) studioLoader.item.hide()
            window.showNormal()
            window.raise()
            window.requestActivate()
        }
        function onSettingsChanged() {
            window.applySavedAppearance()
        }
        function onAccountChanged() { window.applySavedAppearance() }
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
