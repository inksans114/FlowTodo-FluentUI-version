import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    title: ""
    wrapperWidth: 1040
    horizontalPadding: 32
    contentSpacing: 16
    LayoutTokens { id: ui }
    StudioTokens { id: look }
    readonly property bool compactLayout: width - horizontalPadding * 2 < ui.compactBreakpoint
    property var tasks: []
    property string query: ""
    property string filterMode: "active"
    property string greeting: I18n.t("你好")
    property var todayTasks: tasks.filter(function(task) {
        var scheduledDate = String(task.scheduledDate || task.dailyDate || "")
        return !scheduledDate || scheduledDate === page.todayKey()
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
        greeting = hour < 5 ? I18n.t("晚上好")
            : hour < 11 ? I18n.t("早上好")
            : hour < 14 ? I18n.t("中午好")
            : hour < 18 ? I18n.t("下午好") : I18n.t("晚上好")
    }
    function submit() {
        var title = newTask.text.trim()
        if (!title.length) return
        homeDictation.finish()
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

    Item { Layout.preferredHeight: 8 }
    RowLayout {
        Layout.fillWidth: true; spacing: 12
        ColumnLayout { Layout.fillWidth: true; spacing: 6
            RowLayout { Layout.fillWidth: true; spacing: 10
                Icon { visible: look.personalized; name: look.personalization.workspaceIcon || "ic_fluent_checkmark_circle_20_regular"; size: 26; color: look.accent }
                Text { Layout.fillWidth: true; text: look.personalized && look.personalization.workspaceName ? look.personalization.workspaceName : I18n.t("今日任务"); font.pixelSize: 28; font.weight: Font.DemiBold; color: look.ink; wrapMode: Text.Wrap }
            }
            Text { Layout.fillWidth: true; text: page.greeting + " · " + Backend.todayLabel; font.pixelSize: 13; color: look.muted; wrapMode: Text.Wrap }
        }
        Button { id: homeMore; objectName: "homeMore"; text: I18n.t("更多"); icon.name: "ic_fluent_more_horizontal_20_regular"; flat: true; onClicked: homeMenu.open()
            QuietMenu { id: homeMenu; parent: homeMore
                MenuItem { text: I18n.t("详细任务"); onTriggered: page.openTaskCreatePage() }
                MenuItem { text: I18n.t("日程"); onTriggered: { var r = page.nav(); if (r) r.push(Qt.resolvedUrl("ScheduleWorkspace.qml")) } }
                MenuItem { text: I18n.t("项目"); onTriggered: { var r = page.nav(); if (r) r.push(Qt.resolvedUrl("ProjectsWorkspace.qml")) } }
                MenuItem { text: I18n.t("关联任务"); onTriggered: Backend.openTaskRelations("") }
            }
        }
    }
    Frame {
        objectName: "homeComposer"
        Layout.fillWidth: true; padding: 16
        background: Rectangle { radius: 14; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 10
            Text { text: I18n.t("记下一件事"); font.pixelSize: 13; font.weight: Font.DemiBold; color: look.muted }
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                TextField { id: newTask; objectName: "homeNewTask"; Layout.fillWidth: true; Layout.preferredHeight: 44; placeholderText: I18n.t("下一件想完成的事…"); Accessible.name: I18n.t("添加今日任务"); onAccepted: page.submit() }
                InlineDictationButton { id: homeDictation; objectName: "homeVoice"; inputTarget: newTask; Layout.preferredWidth: implicitWidth; Layout.minimumWidth: implicitWidth; Layout.maximumWidth: implicitWidth; Layout.preferredHeight: 44 }
                Button { objectName: "homeAddButton"; text: I18n.t("添加"); icon.name: "ic_fluent_add_20_regular"; enabled: newTask.text.trim().length > 0; Layout.preferredHeight: 44; onClicked: page.submit() }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true; Layout.topMargin: 8
        Text { text: page.filterMode === "done" ? I18n.t("已完成") : page.filterMode === "all" ? I18n.t("全部任务") : I18n.t("接下来"); font.pixelSize: 20; font.weight: Font.DemiBold; color: look.ink }
        Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignRight; text: page.visibleTasks.length + I18n.t(" 项") + "   ·   " + I18n.t("今日完成 ") + Backend.completedCount + "   ·   " + I18n.t("专注 ") + Backend.todayFocusMinutes + I18n.t(" 分钟"); font.pixelSize: 12; color: look.muted; wrapMode: Text.Wrap }
    }
    Flow {
        Layout.fillWidth: true; width: parent.width; spacing: 12
        TextField { objectName: "homeSearch"; width: page.compactLayout ? parent.width : 250; placeholderText: I18n.t("搜索任务"); Accessible.name: I18n.t("搜索今日任务"); onTextChanged: page.query = text }
        Segmented {
            id: taskFilter
            width: page.compactLayout ? parent.width : 300
            currentIndex: page.filterMode === "all" ? 0 : page.filterMode === "done" ? 2 : 1
            onCurrentIndexChanged: page.filterMode = ["all", "active", "done"][currentIndex]
            SegmentedItem { text: I18n.t("全部任务"); icon.name: "ic_fluent_list_20_regular" }
            SegmentedItem { text: I18n.t("待完成"); icon.name: "ic_fluent_checkbox_unchecked_20_regular" }
            SegmentedItem { text: I18n.t("已完成"); icon.name: "ic_fluent_checkmark_circle_20_regular" }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        objectName: "homeTaskList"
        spacing: 8
        Repeater {
            model: page.visibleTasks
            delegate: Frame {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: modelData.taskType === "daily" ? 86 : 68
                background: Rectangle { radius: 12; color: look.list; border.color: look.stroke }
                leftPadding: 12
                rightPadding: 8
                topPadding: 8
                bottomPadding: 8
                RowLayout {
                    anchors.fill: parent
                    spacing: 10
                    CheckBox { objectName: "homeToggle_" + modelData.id; Accessible.name: I18n.t("完成任务") + " · " + modelData.title; checked: Boolean(modelData.done); onClicked: Backend.toggleTask(Number(modelData.id), checked) }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text { Layout.fillWidth: true; text: String(modelData.title || I18n.t("未命名任务")); typography: Typography.BodyStrong; color: Boolean(modelData.done) ? Theme.currentTheme.colors.textColor : modelData.dailyStatus === "important" ? "#d13438" : modelData.dailyStatus === "warning" ? "#c58b00" : Theme.currentTheme.colors.textColor; font.strikeout: Boolean(modelData.done); opacity: modelData.done ? 0.58 : 1; elide: Text.ElideRight }
                        Text { Layout.fillWidth: true; text: String(modelData.meta || I18n.t("今天")); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; elide: Text.ElideRight }
                        Text { visible: modelData.taskType === "daily"; text: modelData.dailyStatus === "important" ? I18n.t("昨日未完成 · 需要优先处理") : modelData.dailyStatus === "warning" ? I18n.t("已到提醒时间 · ") + String(modelData.reminderTime || "") : I18n.t("每日重复 · 每天 0:00 重置 · 提醒 ") + String(modelData.reminderTime || ""); typography: Typography.Caption; color: modelData.dailyStatus === "important" ? "#d13438" : modelData.dailyStatus === "warning" ? "#c58b00" : Theme.currentTheme.colors.textSecondaryColor }
                    }
                    Button { flat: true; text: I18n.t("专注"); icon.name: "ic_fluent_play_20_regular"; enabled: !Boolean(modelData.done); onClicked: Backend.prepareRelationNode("task:" + modelData.id) }
                    Button { objectName: "editTask_" + modelData.id; flat: true; text: I18n.t("编辑"); icon.name: "ic_fluent_edit_20_regular"; Accessible.name: I18n.t("编辑任务") + " · " + modelData.title; onClicked: { var r = page.nav(); if (r) r.push(Qt.resolvedUrl("TaskEditorPage.qml"), {taskId: Number(modelData.id)}) } }
                    ToolButton { icon.name: "ic_fluent_delete_20_regular"; ToolTip.text: I18n.t("删除"); ToolTip.visible: hovered; onClicked: Backend.deleteTask(Number(modelData.id)) }
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
            Text { Layout.alignment: Qt.AlignHCenter; text: page.todayTasks.length ? I18n.t("没有匹配的任务") : I18n.t("今天还没有任务"); typography: Typography.BodyStrong }
            Text { Layout.alignment: Qt.AlignHCenter; text: page.todayTasks.length ? I18n.t("调整筛选或关键词") : I18n.t("从上方输入框添加第一项"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
}
