import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "专注模式"
    wrapperWidth: 940
    horizontalPadding: 36
    contentSpacing: 12
    property var tasks: []
    property var session: ({})
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function reloadTasks() { try { tasks = JSON.parse(Backend.tasksJson).filter(function(item) { return !item.done }) } catch (error) { tasks = [] } }
    function reloadSession() { try { session = JSON.parse(Backend.focusSessionJson) } catch (error) { session = {} } }
    function begin(task) { if (Backend.startTask(Number(task.id))) { var router = nav(); if (router) router.push(Qt.resolvedUrl("FocusSessionNative.qml"), {mode: "single", titleText: String(task.title || "专注会话")}) } }
    Component.onCompleted: { reloadTasks(); reloadSession() }
    Connections {
        target: Backend
        function onTasksChanged() { page.reloadTasks() }
        function onFocusSessionChanged() { page.reloadSession() }
    }

    RowLayout { Layout.fillWidth: true
        Text { Layout.fillWidth: true
                text: "选择待办后，桌面灵动岛会自动展开并同步倒计时"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
        Button { visible: Boolean(page.session.event) && page.session.event !== "completed" && page.session.event !== "cancelled"
                text: "查看当前会话"
                icon.name: "ic_fluent_timer_20_regular"; onClicked: { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("FocusSessionNative.qml"), {mode: String(page.session.mode || "single"), titleText: String(page.session.title || "专注会话")}) } }
    }
    Frame {
        Layout.fillWidth: true
        Layout.preferredHeight: 86
        leftPadding: 16
                rightPadding: 16
                topPadding: 12
                bottomPadding: 12
        RowLayout { anchors.fill: parent
                spacing: 14
            Rectangle { width: 44
                height: 44
                radius: 8
                color: Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.14)
                Icon { anchors.centerIn: parent; name: "ic_fluent_timer_20_regular"; size: 24
                color: Theme.currentTheme.colors.primaryColor } }
            ColumnLayout { Layout.fillWidth: true
                spacing: 2
                Text { text: "快速开始"
                typography: Typography.BodyStrong }
                Text { text: "默认时长 " + Backend.getSetting("focusDuration", 25) + " 分钟，可在设置中调整"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
            Text { text: page.tasks.length + " 个待办可开始"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
    Text { Layout.topMargin: 4
                text: "待办任务"
                typography: Typography.BodyStrong }
    ColumnLayout {
        Layout.fillWidth: true
                spacing: 4
        Repeater { model: page.tasks; delegate: Frame {
            required property var modelData
            Layout.fillWidth: true
                Layout.preferredHeight: 62
                leftPadding: 12
                rightPadding: 8
            RowLayout { anchors.fill: parent
                spacing: 10
                Icon { name: "ic_fluent_checkbox_unchecked_20_regular"; size: 20
                color: Theme.currentTheme.colors.textSecondaryColor }
                ColumnLayout { Layout.fillWidth: true
                spacing: 1
                Text { Layout.fillWidth: true
                text: String(modelData.title || "任务")
                typography: Typography.BodyStrong
                elide: Text.ElideRight }
                Text { Layout.fillWidth: true
                text: String(modelData.meta || "今天")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                elide: Text.ElideRight } }
                Button { text: "开始"
                highlighted: true
                icon.name: "ic_fluent_play_20_regular"; onClicked: page.begin(modelData) }
            }
        } }
    }
    Item { Layout.fillWidth: true
                Layout.preferredHeight: 160
                visible: page.tasks.length === 0
                ColumnLayout { anchors.centerIn: parent
                spacing: 6
                Icon { Layout.alignment: Qt.AlignHCenter; name: "ic_fluent_checkmark_circle_20_regular"; size: 38
                color: Theme.currentTheme.colors.textSecondaryColor }
                Text { Layout.alignment: Qt.AlignHCenter
                text: "当前没有待办任务"
                typography: Typography.BodyStrong }
                Text { Layout.alignment: Qt.AlignHCenter
                text: "先在今日任务中添加一项，再回来启动专注"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } } }
}

