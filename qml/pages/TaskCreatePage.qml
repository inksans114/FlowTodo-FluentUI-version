import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("新建任务")
    wrapperWidth: 700
    horizontalPadding: 36
    contentSpacing: 14
    property bool loading: false
    property bool reminderEnabled: false
    property int focusMinutes: Number(Backend.getSetting("focusDuration", 25))

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
            Backend.addPomodoroTask(title, taskMeta.text.trim(), page.focusMinutes)
        else if (taskType.currentIndex === 2)
            Backend.addDailyTask(title, taskMeta.text.trim(), page.reminderEnabled ? (reminder.time || "18:00") : "")
        else
            Backend.addTask(title, taskMeta.text.trim())
        page.closePage()
    }

    RowLayout {
        Layout.fillWidth: true
        ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"; ToolTip.text: I18n.t("返回"); ToolTip.visible: hovered; onClicked: page.closePage() }
        Text { text: I18n.t("返回今日任务"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        Item { Layout.fillWidth: true }
    }

    Text { Layout.fillWidth: true; text: I18n.t("把一件事写清楚，再决定它要不要重复。"); typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor }

    Frame {
        Layout.fillWidth: true
        leftPadding: 20; rightPadding: 20; topPadding: 20; bottomPadding: 20
        ColumnLayout {
            anchors.fill: parent
            spacing: 14
            Text { text: I18n.t("任务内容"); typography: Typography.Subtitle }
            TextField { id: taskTitle; Layout.fillWidth: true; placeholderText: I18n.t("任务名称"); onAccepted: page.createTask() }
            TextField { id: taskMeta; Layout.fillWidth: true; placeholderText: I18n.t("备注（可选）"); onAccepted: page.createTask() }
        }
    }

    Frame {
        Layout.fillWidth: true
        leftPadding: 20; rightPadding: 20; topPadding: 20; bottomPadding: 20
        ColumnLayout {
            anchors.fill: parent
            spacing: 14
            Text { text: I18n.t("任务类型"); typography: Typography.Subtitle }
            ComboBox {
                id: taskType
                Layout.fillWidth: true
                model: [I18n.t("普通任务"), I18n.t("番茄钟任务"), I18n.t("每日重复任务")]
                onActivated: function(index) { if (index !== 2) page.reminderEnabled = false }
            }
            Text { Layout.fillWidth: true; text: taskType.currentIndex === 2 ? I18n.t("每天 0:00 自动重置；开启提醒后，到点发送系统通知") : taskType.currentIndex === 1 ? I18n.t("启动任务时使用单独的专注时长") : I18n.t("完成后保留记录，不会自动重复"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap }
            RowLayout {
                Layout.fillWidth: true
                visible: taskType.currentIndex === 1
                Text { text: I18n.t("专注时长"); typography: Typography.Body }
            SpinBox { from: 1; to: 180; stepSize: 1; value: page.focusMinutes; onValueChanged: page.focusMinutes = value }
                Text { text: I18n.t("分钟"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true }
            }
            RowLayout {
                Layout.fillWidth: true
                visible: taskType.currentIndex === 2
                CheckBox {
                    text: I18n.t("到点提醒")
                    checked: page.reminderEnabled
                    onClicked: {
                        page.reminderEnabled = checked
                        if (checked && !reminder.time) reminder.setTime("18:00")
                    }
                }
                Item { Layout.fillWidth: true }
                Text { visible: page.reminderEnabled; text: I18n.t("点击时间可自由选择"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                Item { visible: !page.reminderEnabled; Layout.fillWidth: true }
                TimePicker { id: reminder; visible: page.reminderEnabled; enabled: page.reminderEnabled; Layout.preferredWidth: 130; use24Hour: true; hourText: I18n.t("时"); minuteText: I18n.t("分") }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Button { text: I18n.t("取消"); onClicked: page.closePage() }
        Button { text: I18n.t("创建任务"); highlighted: true; icon.name: "ic_fluent_checkmark_20_regular"; onClicked: page.createTask() }
    }
}
