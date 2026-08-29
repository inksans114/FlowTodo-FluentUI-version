import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "新建任务"
    wrapperWidth: 700
    horizontalPadding: 36
    contentSpacing: 14
    property bool loading: false
    property bool reminderEnabled: false

    function nav() {
        var item = page
        while (item) {
            if (item.objectName === "MainNavigationView") return item
            item = item.parent
        }
        return null
    }
    function closePage() {
        var router = page.nav()
        if (router) router.pop()
    }
    function createTask() {
        var title = taskTitle.text.trim()
        if (!title.length) {
            taskTitle.forceActiveFocus()
            return
        }
        if (taskType.currentIndex === 1)
            Backend.addDailyTask(title, taskMeta.text.trim(), page.reminderEnabled ? (reminder.time || "18:00") : "")
        else
            Backend.addTask(title, taskMeta.text.trim())
        page.closePage()
    }

    RowLayout {
        Layout.fillWidth: true
        ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"; ToolTip.text: "返回"; ToolTip.visible: hovered; onClicked: page.closePage() }
        Text { text: "返回今日任务"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        Item { Layout.fillWidth: true }
    }

    Text { Layout.fillWidth: true; text: "把一件事写清楚，再决定它要不要重复。"; typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor }

    Frame {
        Layout.fillWidth: true
        leftPadding: 20; rightPadding: 20; topPadding: 20; bottomPadding: 20
        ColumnLayout {
            anchors.fill: parent
            spacing: 14
            Text { text: "任务内容"; typography: Typography.Subtitle }
            TextField { id: taskTitle; Layout.fillWidth: true; placeholderText: "任务名称"; onAccepted: page.createTask() }
            TextField { id: taskMeta; Layout.fillWidth: true; placeholderText: "备注（可选）"; onAccepted: page.createTask() }
        }
    }

    Frame {
        Layout.fillWidth: true
        leftPadding: 20; rightPadding: 20; topPadding: 20; bottomPadding: 20
        ColumnLayout {
            anchors.fill: parent
            spacing: 14
            Text { text: "任务类型"; typography: Typography.Subtitle }
            ComboBox {
                id: taskType
                Layout.fillWidth: true
                model: ["普通任务", "每日重复任务"]
                onActivated: function(index) { if (index !== 1) page.reminderEnabled = false }
            }
            Text { Layout.fillWidth: true; text: taskType.currentIndex === 1 ? "每天 0:00 自动重置；开启提醒后，到点发送系统通知" : "完成后保留记录，不会自动重复"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap }
            RowLayout {
                Layout.fillWidth: true
                visible: taskType.currentIndex === 1
                CheckBox {
                    text: "到点提醒"
                    checked: page.reminderEnabled
                    onClicked: {
                        page.reminderEnabled = checked
                        if (checked && !reminder.time) reminder.setTime("18:00")
                    }
                }
                Item { Layout.fillWidth: true }
                Text { visible: page.reminderEnabled; text: "点击时间可自由选择"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                Item { visible: !page.reminderEnabled; Layout.fillWidth: true }
                TimePicker { id: reminder; visible: page.reminderEnabled; enabled: page.reminderEnabled; Layout.preferredWidth: 130; use24Hour: true; hourText: "时"; minuteText: "分" }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Button { text: "取消"; onClicked: page.closePage() }
        Button { text: "创建任务"; highlighted: true; icon.name: "ic_fluent_checkmark_20_regular"; onClicked: page.createTask() }
    }
}
