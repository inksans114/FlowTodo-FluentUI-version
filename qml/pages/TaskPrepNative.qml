import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "任务启动准备"
    wrapperWidth: 760
    horizontalPadding: 36
    contentSpacing: 12

    property double taskId: -1
    property var task: ({})
    property int durationMinutes: Number(Backend.getSetting("focusDuration", 25))
    property bool pageReady: false

    function navigationView() {
        var item = page
        while (item) {
            if (item.objectName === "MainNavigationView")
                return item
            item = item.parent
        }
        return null
    }
    function load() {
        var tasks = []
        try { tasks = JSON.parse(Backend.tasksJson) } catch (error) { tasks = [] }
        task = tasks.find(function(item) { return Number(item.id) === Number(taskId) }) || ({})
    }
    function goBack() {
        var router = navigationView()
        if (router)
            router.pop()
    }
    function start() {
        if (!task.title)
            return
        if (Backend.startPreparedTask(taskId, durationMinutes)) {
            var router = navigationView()
            if (router)
                router.push(Qt.resolvedUrl("FocusSessionNative.qml"), {
                    mode: "single",
                    titleText: String(task.title || "任务专注")
                })
        }
    }

    Component.onCompleted: { pageReady = true; load() }
    onTaskIdChanged: if (pageReady) load()
    Connections { target: Backend; function onTasksChanged() { page.load() } }

    RowLayout {
        Layout.fillWidth: true
        ToolButton {
            icon.name: "ic_fluent_arrow_left_20_regular"
            ToolTip.text: "返回"
            ToolTip.visible: hovered
            onClicked: page.goBack()
        }
        Text { text: "返回"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        Item { Layout.fillWidth: true }
    }

    Frame {
        Layout.fillWidth: true
        leftPadding: 20
        rightPadding: 20
        topPadding: 18
        bottomPadding: 18
        RowLayout {
            anchors.fill: parent
            spacing: 14
            Rectangle {
                width: 46
                height: 46
                radius: 8
                antialiasing: true
                color: Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.14)
                Icon {
                    anchors.centerIn: parent
                    name: "ic_fluent_task_list_ltr_20_regular"
                    size: 24
                    color: Theme.currentTheme.colors.primaryColor
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Text {
                    Layout.fillWidth: true
                    text: String(page.task.title || "任务不存在")
                    typography: Typography.Subtitle
                    wrapMode: Text.Wrap
                }
                Text {
                    Layout.fillWidth: true
                    text: String(page.task.meta || "单任务专注")
                    typography: Typography.Body
                    color: Theme.currentTheme.colors.textSecondaryColor
                    wrapMode: Text.Wrap
                }
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        leftPadding: 20
        rightPadding: 20
        topPadding: 18
        bottomPadding: 18
        ColumnLayout {
            anchors.fill: parent
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: "本次专注时长"; typography: Typography.Subtitle }
                Text {
                    text: page.durationMinutes + " 分钟"
                    typography: Typography.BodyStrong
                    color: Theme.currentTheme.colors.primaryColor
                }
            }
            Slider {
                Layout.fillWidth: true
                from: 5
                to: 180
                stepSize: 5
                value: page.durationMinutes
                onMoved: page.durationMinutes = Math.round(value)
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: "5 分钟"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true }
                SpinBox {
                    from: 5
                    to: 180
                    stepSize: 5
                    value: page.durationMinutes
                    onValueModified: page.durationMinutes = value
                }
                Text { text: "分钟"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Button { text: "取消"; onClicked: page.goBack() }
        Button {
            text: "开始专注"
            highlighted: true
            enabled: Boolean(page.task.title) && !Boolean(page.task.done)
            icon.name: "ic_fluent_play_20_regular"
            onClicked: page.start()
        }
    }
}
