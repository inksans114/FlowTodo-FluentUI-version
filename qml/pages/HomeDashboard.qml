import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: page.greeting + "，今日任务"
    wrapperWidth: 980
    horizontalPadding: 36
    contentSpacing: 12
    property var tasks: []
    property string query: ""
    property string filterMode: "active"
    property string greeting: "你好"
    property var todayTasks: tasks.filter(function(task) {
        var scheduledDate = String(task.scheduledDate || task.dailyDate || "")
        return scheduledDate === page.todayKey()
    })
    property var visibleTasks: todayTasks.filter(function(task) {
        var matchesFilter = filterMode === "all" || (filterMode === "done" ? Boolean(task.done) : !Boolean(task.done))
        var text = (String(task.title || "") + " " + String(task.meta || "")).toLowerCase()
        return matchesFilter && (!query.trim().length || text.indexOf(query.trim().toLowerCase()) >= 0)
    })
    function todayKey() { var now = new Date(); return now.getFullYear() + "-" + (now.getMonth() + 1 < 10 ? "0" : "") + (now.getMonth() + 1) + "-" + (now.getDate() < 10 ? "0" : "") + now.getDate() }
    function reload() { try { tasks = JSON.parse(Backend.tasksJson) } catch (error) { tasks = [] } }
    function nav() {
        var item = page
        while (item) {
            if (item.objectName === "MainNavigationView") return item
            item = item.parent
        }
        return null
    }
    function updateGreeting() {
        var hour = new Date().getHours()
        greeting = hour < 5 ? "晚上好"
            : hour < 11 ? "早上好"
            : hour < 14 ? "中午好"
            : hour < 18 ? "下午好" : "晚上好"
    }
    function submit() {
        var title = newTask.text.trim()
        if (!title.length) return
        Backend.addTask(title, "")
        newTask.clear()
        newTask.forceActiveFocus()
    }
    function openTaskCreatePage() {
        var router = page.nav()
        if (router) router.push(Qt.resolvedUrl("TaskCreatePage.qml"))
    }
    Component.onCompleted: { updateGreeting(); reload() }
    Timer { interval: 60000; running: page.visible; repeat: true; onTriggered: page.updateGreeting() }
    Connections { target: Backend; function onTasksChanged() { page.reload() } }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Text { Layout.fillWidth: true; text: Backend.todayLabel; typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor }
        TextField { Layout.preferredWidth: 220; placeholderText: "搜索任务"; onTextChanged: page.query = text }
        Segmented {
            id: taskFilter
            Layout.preferredWidth: 276
            currentIndex: page.filterMode === "all" ? 0 : page.filterMode === "done" ? 2 : 1
            onCurrentIndexChanged: page.filterMode = ["all", "active", "done"][currentIndex]

            SegmentedItem { text: "全部任务"; icon.name: "ic_fluent_list_20_regular" }
            SegmentedItem { text: "待完成"; icon.name: "ic_fluent_checkbox_unchecked_20_regular" }
            SegmentedItem { text: "已完成"; icon.name: "ic_fluent_checkmark_circle_20_regular" }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        MetricCard { label: "待完成"; value: String(page.todayTasks.filter(function(item) { return !item.done }).length); iconName: "ic_fluent_checkbox_unchecked_20_regular"; accent: "#0f6cbd" }
        MetricCard { label: "今日完成"; value: String(Backend.completedCount); iconName: "ic_fluent_checkmark_circle_20_regular"; accent: "#0f7b0f" }
        MetricCard { label: "今日专注"; value: Backend.todayFocusMinutes + " 分钟"; iconName: "ic_fluent_timer_20_regular"; accent: "#8764b8" }
    }

    Frame {
        Layout.fillWidth: true
        Layout.preferredHeight: 78
        leftPadding: 16
        rightPadding: 16
        topPadding: 12
        bottomPadding: 12
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Rectangle {
                    width: 32
                    height: 32
                    radius: 8
                    color: Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.14)
                    Icon { anchors.centerIn: parent; name: "ic_fluent_add_20_regular"; size: 18; color: Theme.currentTheme.colors.primaryColor }
                }
                TextField {
                    id: newTask
                    Layout.fillWidth: true
                    placeholderText: "添加下一件要做的事"
                    onAccepted: page.submit()
                }
                Button { text: "添加"; highlighted: true; icon.name: "ic_fluent_arrow_enter_20_regular"; onClicked: page.submit() }
                Button { flat: true; text: "更多选项"; icon.name: "ic_fluent_options_20_regular"; onClicked: page.openTaskCreatePage() }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 4
        Text { Layout.fillWidth: true; text: page.filterMode === "done" ? "已完成" : page.filterMode === "all" ? "全部任务" : "接下来"; typography: Typography.BodyStrong }
        Text { text: page.visibleTasks.length + " 项"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4
        Repeater {
            model: page.visibleTasks
            delegate: Frame {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: modelData.taskType === "daily" ? 82 : 64
                leftPadding: 12
                rightPadding: 8
                topPadding: 8
                bottomPadding: 8
                RowLayout {
                    anchors.fill: parent
                    spacing: 10
                    CheckBox { checked: Boolean(modelData.done); onClicked: Backend.toggleTask(Number(modelData.id), checked) }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text { Layout.fillWidth: true; text: String(modelData.title || "未命名任务"); typography: Typography.BodyStrong; color: Boolean(modelData.done) ? Theme.currentTheme.colors.textColor : modelData.dailyStatus === "important" ? "#d13438" : modelData.dailyStatus === "warning" ? "#c58b00" : Theme.currentTheme.colors.textColor; font.strikeout: Boolean(modelData.done); opacity: modelData.done ? 0.58 : 1; elide: Text.ElideRight }
                        Text { Layout.fillWidth: true; text: String(modelData.meta || "今天"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; elide: Text.ElideRight }
                        Text { visible: modelData.taskType === "daily"; text: modelData.dailyStatus === "important" ? "昨日未完成 · 需要优先处理" : modelData.dailyStatus === "warning" ? "已到提醒时间 · " + String(modelData.reminderTime || "") : "每日重复 · 每天 0:00 重置 · 提醒 " + String(modelData.reminderTime || ""); typography: Typography.Caption; color: modelData.dailyStatus === "important" ? "#d13438" : modelData.dailyStatus === "warning" ? "#c58b00" : Theme.currentTheme.colors.textSecondaryColor }
                    }
                    Button { flat: true; text: "专注"; icon.name: "ic_fluent_play_20_regular"; enabled: !Boolean(modelData.done); onClicked: Backend.startTask(Number(modelData.id)) }
                    ToolButton { icon.name: "ic_fluent_delete_20_regular"; ToolTip.text: "删除"; ToolTip.visible: hovered; onClicked: Backend.deleteTask(Number(modelData.id)) }
                }
            }
        }
    }

    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: 150
        visible: page.visibleTasks.length === 0
        ColumnLayout {
            anchors.centerIn: parent
            spacing: 6
            Icon { Layout.alignment: Qt.AlignHCenter; name: page.todayTasks.length ? "ic_fluent_search_20_regular" : "ic_fluent_clipboard_task_list_ltr_20_regular"; size: 36; color: Theme.currentTheme.colors.textSecondaryColor }
            Text { Layout.alignment: Qt.AlignHCenter; text: page.todayTasks.length ? "没有匹配的任务" : "今天还没有任务"; typography: Typography.BodyStrong }
            Text { Layout.alignment: Qt.AlignHCenter; text: page.todayTasks.length ? "调整筛选或关键词" : "从上方输入框添加第一项"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
}
