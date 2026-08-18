import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "桌面小组件"
    wrapperWidth: 860
    horizontalPadding: 36
    contentSpacing: 14

    property var tasks: []
    property var groups: []
    property var projects: []
    property bool loading: true

    function reload() {
        try { tasks = JSON.parse(Backend.tasksJson) } catch (error) { tasks = [] }
        try { groups = JSON.parse(Backend.groupsJson) } catch (error) { groups = [] }
        try { projects = JSON.parse(Backend.projectsJson) } catch (error) { projects = [] }
    }
    Component.onCompleted: {
        reload()
        autoShow.checked = Boolean(Backend.getSetting("desktopWidgetAutoShow", false))
        loading = false
    }
    Connections {
        target: Backend
        function onTasksChanged() { page.reload() }
        function onGroupsChanged() { page.reload() }
        function onProjectsChanged() { page.reload() }
    }

    RowLayout {
        Layout.fillWidth: true
        Text {
            Layout.fillWidth: true
            text: "任务、任务流和项目"
            typography: Typography.Body
            color: Theme.currentTheme.colors.textSecondaryColor
        }
        Button {
            text: "打开小组件"
            highlighted: true
            icon.name: "ic_fluent_open_20_regular"
            onClicked: Backend.showDesktopWidget()
        }
    }

    Frame {
        Layout.fillWidth: true
        leftPadding: 20
        rightPadding: 20
        topPadding: 18
        bottomPadding: 18
        RowLayout {
            anchors.fill: parent
            spacing: 22
            Repeater {
                model: [
                    { label: "待办任务", value: page.tasks.filter(function(item) { return !item.done }).length, icon: "ic_fluent_task_list_ltr_20_regular" },
                    { label: "任务流", value: page.groups.length, icon: "ic_fluent_flow_20_regular" },
                    { label: "项目", value: page.projects.length, icon: "ic_fluent_board_20_regular" }
                ]
                delegate: RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Icon { name: modelData.icon; size: 24; color: Theme.currentTheme.colors.primaryColor }
                    ColumnLayout {
                        spacing: 1
                        Text { text: String(modelData.value); typography: Typography.Subtitle }
                        Text { text: modelData.label; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                    }
                }
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        leftPadding: 20
        rightPadding: 20
        topPadding: 14
        bottomPadding: 14
        RowLayout {
            anchors.fill: parent
            spacing: 12
            Icon { name: "ic_fluent_pin_20_regular"; size: 22; color: Theme.currentTheme.colors.primaryColor }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Text { text: "随应用启动"; typography: Typography.BodyStrong }
            }
            Switch {
                id: autoShow
                onClicked: if (!page.loading) Backend.setSetting("desktopWidgetAutoShow", checked)
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Button { text: "刷新数据"; icon.name: "ic_fluent_arrow_sync_20_regular"; onClicked: Backend.reload() }
        Button { text: "隐藏小组件"; icon.name: "ic_fluent_dismiss_20_regular"; onClicked: Backend.hideDesktopWidget() }
    }
}
