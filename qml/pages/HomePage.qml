import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "今日任务"
    wrapperWidth: 1040
    horizontalPadding: 34

    property var tasks: []
    property string searchQuery: ""
    property var filteredTasks: tasks.filter(function(task) {
        var query = searchQuery.trim().toLowerCase()
        if (!query.length) return true
        return String(task.title || "").toLowerCase().indexOf(query) >= 0
            || String(task.meta || "").toLowerCase().indexOf(query) >= 0
    })

    function reloadTasks() {
        try {
            tasks = JSON.parse(Backend.tasksJson)
        } catch (error) {
            tasks = []
        }
    }

    function submitTask() {
        var value = newTaskTitle.text.trim()
        if (!value.length) return
        if (taskType.currentIndex === 1)
            Backend.addDailyTask(value, newTaskMeta.text.trim(), dailyReminder.time || "18:00")
        else
            Backend.addTask(value, newTaskMeta.text.trim())
        newTaskTitle.clear()
        newTaskMeta.clear()
        newTaskTitle.forceActiveFocus()
    }

    Component.onCompleted: reloadTasks()
    Connections {
        target: Backend
        function onTasksChanged() { page.reloadTasks() }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        MetricCard {
            label: "全部任务"
            value: String(Backend.taskCount)
            iconName: "ic_fluent_list_20_regular"
            accent: "#4099b2"
        }
        MetricCard {
            label: "今日已完成"
            value: String(Backend.completedCount)
            iconName: "ic_fluent_checkmark_circle_20_regular"
            accent: "#2eaa76"
        }
        MetricCard {
            label: "今日专注"
            value: Backend.todayFocusMinutes + " 分钟"
            iconName: "ic_fluent_timer_20_regular"
            accent: "#7054b8"
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "快速添加"
        description: Backend.todayLabel
        icon.name: "ic_fluent_add_circle_20_regular"

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
            TextField {
                id: newTaskTitle
                Layout.fillWidth: true
                placeholderText: "任务名称"
                onAccepted: page.submitTask()
            }
            TextField {
                id: newTaskMeta
                Layout.preferredWidth: 150
                placeholderText: "备注（可选）"
                onAccepted: page.submitTask()
            }
            Button {
                text: "添加"
                highlighted: true
                icon.name: "ic_fluent_add_20_regular"
                onClicked: page.submitTask()
            }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                ComboBox {
                    id: taskType
                    Layout.preferredWidth: 190
                    model: ["普通任务", "每日重复任务"]
                    onActivated: function(index) {
                        if (index === 1 && !dailyReminder.time) Qt.callLater(function() { dailyReminder.setTime("18:00") })
                    }
                }
                Text {
                    text: taskType.currentIndex === 1 ? "每天 0:00 自动重置，可设置未完成提醒" : "一次性任务，完成后保留记录"
                    typography: Typography.Caption
                    color: Theme.currentTheme.colors.textSecondaryColor
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                Text { visible: taskType.currentIndex === 1; text: "提醒时间"; typography: Typography.Caption }
                TimePicker {
                    id: dailyReminder
                    visible: taskType.currentIndex === 1
                    Layout.preferredWidth: 130
                    use24Hour: true
                    hourText: "时"
                    minuteText: "分"
                }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        Text {
            Layout.fillWidth: true
            text: "任务列表"
            typography: Typography.BodyStrong
        }
        TextField {
            Layout.preferredWidth: 260
            placeholderText: "搜索任务"
            leftPadding: 36
            onTextChanged: page.searchQuery = text
            IconWidget {
                anchors.left: parent.left
                anchors.leftMargin: 11
                anchors.verticalCenter: parent.verticalCenter
                icon: "ic_fluent_search_20_regular"
                size: 17
                color: Theme.currentTheme.colors.textSecondaryColor
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        visible: page.filteredTasks.length > 0

        Repeater {
            model: page.filteredTasks
            delegate: Frame {
                id: taskCard
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: taskCard.modelData.taskType === "daily" ? 94 : 78
                leftPadding: 16
                rightPadding: 12
                topPadding: 10
                bottomPadding: 10
                hoverable: true

                RowLayout {
                    anchors.fill: parent
                    spacing: 12
                    CheckBox {
                        checked: Boolean(taskCard.modelData.done)
                        onClicked: Backend.toggleTask(Number(taskCard.modelData.id), checked)
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: String(taskCard.modelData.title || "未命名任务")
                            typography: Typography.BodyStrong
                            color: Boolean(taskCard.modelData.done) ? Theme.currentTheme.colors.textColor
                                : taskCard.modelData.dailyStatus === "important" ? "#d13438"
                                : taskCard.modelData.dailyStatus === "warning" ? "#c58b00"
                                : Theme.currentTheme.colors.textColor
                            font.strikeout: Boolean(taskCard.modelData.done)
                            opacity: taskCard.modelData.done ? 0.62 : 1
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: String(taskCard.modelData.meta || taskCard.modelData.description || "今天")
                            typography: Typography.Caption
                            color: Theme.currentTheme.colors.textSecondaryColor
                            elide: Text.ElideRight
                        }
                        Text {
                            visible: taskCard.modelData.taskType === "daily"
                            text: taskCard.modelData.dailyStatus === "important" ? "昨日未完成 · 需要优先处理"
                                : taskCard.modelData.dailyStatus === "warning" ? "已到提醒时间 · " + String(taskCard.modelData.reminderTime || "")
                                : "每日重复 · 每天 0:00 重置 · 提醒 " + String(taskCard.modelData.reminderTime || "")
                            typography: Typography.Caption
                            color: taskCard.modelData.dailyStatus === "important" ? "#d13438"
                                : taskCard.modelData.dailyStatus === "warning" ? "#c58b00"
                                : Theme.currentTheme.colors.textSecondaryColor
                        }
                    }
                    Button {
                        text: "专注"
                        highlighted: true
                        enabled: !Boolean(taskCard.modelData.done)
                        icon.name: "ic_fluent_timer_20_regular"
                        onClicked: Backend.startFocus(Number(taskCard.modelData.id))
                    }
                    ToolButton {
                        icon.name: "ic_fluent_delete_20_regular"
                        ToolTip.text: "删除任务"
                        ToolTip.visible: hovered
                        onClicked: Backend.deleteTask(Number(taskCard.modelData.id))
                    }
                }
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        Layout.preferredHeight: 170
        visible: page.filteredTasks.length === 0

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 10
            IconWidget {
                Layout.alignment: Qt.AlignHCenter
                icon: page.tasks.length ? "ic_fluent_search_20_regular" : "ic_fluent_checkmark_circle_20_regular"
                size: 36
                color: Theme.currentTheme.colors.textSecondaryColor
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: page.tasks.length ? "没有匹配的任务" : "今天还没有任务"
                typography: Typography.BodyStrong
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: page.tasks.length ? "换个关键词试试" : "从上方快速添加第一项"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
            }
        }
    }
}
