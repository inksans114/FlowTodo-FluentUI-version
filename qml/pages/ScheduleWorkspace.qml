import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "日程"
    wrapperWidth: 1040
    horizontalPadding: 34
    contentSpacing: 12

    property var tasks: []
    property var taskHistory: []
    property var focusSessions: []
    property var weekDays: []
    property string selectedDate: page.todayKey()
    property string today: page.todayKey()
    property string weekTitle: ""
    property string selectedTitle: ""
    property string selectedMeta: ""
    property string selectedTime: ""
    property bool pageReady: false
    property var selectedTasks: page.tasks.concat(page.taskHistory).filter(function(item) {
        return String(item.scheduledDate || item.dailyDate || "") === page.selectedDate
            || String(item.historyDate || "") === page.selectedDate
    })
    property var selectedFocusSessions: page.focusSessions.filter(function(item) {
        return String(item.date || "") === page.selectedDate
    })
    property var weekTasks: page.tasks.concat(page.taskHistory).filter(function(item) {
        var dates = page.weekDays.map(function(day) { return day.key })
        return dates.indexOf(String(item.scheduledDate || item.dailyDate || "")) >= 0
    })

    function pad(value) { return value < 10 ? "0" + value : String(value) }
    function todayKey() { var now = new Date(); return dateKey(now) }
    function dateKey(date) { return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate()) }
    function dateFromKey(key) { var parts = String(key).split("-"); return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2])) }
    function shiftDate(key, days) { var date = dateFromKey(key); date.setDate(date.getDate() + days); return dateKey(date) }
    function weekday(date) { return ["日", "一", "二", "三", "四", "五", "六"][date.getDay()] }
    function monthDay(key) { var date = dateFromKey(key); return date.getMonth() + 1 + "/" + date.getDate() }
    function buildWeek() {
        var selected = dateFromKey(page.selectedDate)
        var mondayOffset = (selected.getDay() + 6) % 7
        selected.setDate(selected.getDate() - mondayOffset)
        var result = []
        for (var i = 0; i < 7; i++) {
            var date = new Date(selected)
            date.setDate(selected.getDate() + i)
            result.push({key: dateKey(date), day: date.getDate(), weekday: weekday(date), isToday: dateKey(date) === page.today})
        }
        page.weekTitle = result[0].key.slice(0, 7).replace("-", "年") + "月 · 第 " + Math.ceil(Number(result[0].key.slice(8, 10)) / 7) + " 周"
        return result
    }
    function reload() {
        try { page.tasks = JSON.parse(Backend.tasksJson) } catch (error) { page.tasks = [] }
        try {
            var stats = JSON.parse(Backend.statsJson)
            page.taskHistory = (stats.tasks || {}).history || []
            page.focusSessions = (stats.focus || {}).sessions || []
        } catch (error) {
            page.taskHistory = []
            page.focusSessions = []
        }
        page.weekDays = page.buildWeek()
    }
    function selectDate(key) { page.selectedDate = key; page.weekDays = page.buildWeek() }
    function goWeek(offset) { page.selectedDate = page.shiftDate(page.selectedDate, offset * 7); page.weekDays = page.buildWeek() }
    function addTask() {
        var title = page.selectedTitle.trim()
        if (!title.length) return
        Backend.addScheduledTask(title, page.selectedMeta.trim(), page.selectedDate, page.selectedTime)
        page.selectedTitle = ""
        page.selectedMeta = ""
        page.selectedTime = ""
    }
    function resetToday() { page.selectedDate = page.today; page.weekDays = page.buildWeek() }
    function focus(task) { if (!Boolean(task.done)) Backend.startTask(Number(task.id)) }

    Component.onCompleted: { pageReady = true; page.reload() }
    Connections {
        target: Backend
        function onTasksChanged() { page.reload() }
        function onStatsChanged() { page.reload() }
    }

    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: "规划接下来几天，把任务放到真正会执行的时间里。"; typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor }
        Button { text: "回到今天"; icon.name: "ic_fluent_calendar_today_20_regular"; onClicked: page.resetToday() }
        Button { text: "上一周"; icon.name: "ic_fluent_chevron_left_20_regular"; onClicked: page.goWeek(-1) }
        Button { text: "下一周"; icon.name: "ic_fluent_chevron_right_20_regular"; onClicked: page.goWeek(1) }
    }

    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: "周任务"; typography: Typography.Subtitle }
        Text { text: page.weekTasks.filter(function(item) { return !item.done }).length + " 项待完成"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        Text { text: page.weekTitle; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 6
        Repeater {
            model: page.weekDays
            delegate: Frame {
                id: dayFrame
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 82
                leftPadding: 9; rightPadding: 9; topPadding: 9; bottomPadding: 9
                property bool selected: modelData.key === page.selectedDate
                background: Rectangle {
                    radius: 7
                    color: dayFrame.selected ? Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.14) : Theme.currentTheme.colors.cardColor
                    border.width: dayFrame.selected ? 2 : dayFrame.modelData.isToday ? 1 : Theme.currentTheme.appearance.borderWidth
                    border.color: dayFrame.selected ? Theme.currentTheme.colors.primaryColor : dayFrame.modelData.isToday ? Theme.currentTheme.colors.primaryColor : Theme.currentTheme.colors.cardBorderColor
                }
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 3
                    Text { Layout.alignment: Qt.AlignHCenter; text: modelData.weekday; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 30; height: 30; radius: 15
                        color: dayFrame.selected ? Theme.currentTheme.colors.primaryColor : "transparent"
                        Text { anchors.centerIn: parent; text: modelData.day; typography: Typography.BodyStrong; color: dayFrame.selected ? Theme.currentTheme.colors.textOnAccentColor : Theme.currentTheme.colors.textColor }
                    }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: page.tasks.concat(page.taskHistory).filter(function(item) { return String(item.scheduledDate || item.dailyDate || item.historyDate || "") === modelData.key }).length || page.focusSessions.filter(function(item) { return String(item.date || "") === modelData.key }).length ? "·" : ""
                        color: Theme.currentTheme.colors.primaryColor
                    }
                }
                MouseArea { anchors.fill: parent; onClicked: page.selectDate(modelData.key) }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        spacing: 12

        Frame {
            Layout.alignment: Qt.AlignTop
            Layout.fillWidth: true
            Layout.preferredWidth: 650
            Layout.minimumWidth: 500
            leftPadding: 18; rightPadding: 18; topPadding: 16; bottomPadding: 16
            ColumnLayout {
                anchors.fill: parent
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; text: page.selectedDate === page.today ? "今天的安排" : page.monthDay(page.selectedDate) + " 的安排"; typography: Typography.Subtitle }
                    Text { text: page.selectedTasks.length + " 项"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Repeater {
                        model: page.selectedTasks
                        delegate: Frame {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 62
                            leftPadding: 12; rightPadding: 10; topPadding: 9; bottomPadding: 9
                            RowLayout { anchors.fill: parent; spacing: 10
                                CheckBox { enabled: !Boolean(modelData.historyDate); checked: Boolean(modelData.done); onClicked: Backend.toggleTask(Number(modelData.id), checked) }
                                ColumnLayout { Layout.fillWidth: true; spacing: 1
                                    Text { Layout.fillWidth: true; text: String(modelData.title || "未命名任务"); typography: Typography.BodyStrong; elide: Text.ElideRight; font.strikeout: Boolean(modelData.done) }
                                    Text { Layout.fillWidth: true; text: modelData.historyDate ? "已完成 · 历史记录" : String(modelData.meta || "没有备注"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; elide: Text.ElideRight }
                                }
                                Text { text: String(modelData.scheduledTime || ""); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                                Button { flat: true; text: "专注"; icon.name: "ic_fluent_play_20_regular"; enabled: !Boolean(modelData.done) && !Boolean(modelData.historyDate); onClicked: page.focus(modelData) }
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: page.selectedFocusSessions.length > 0
                    Text { Layout.fillWidth: true; text: "专注记录"; typography: Typography.BodyStrong }
                    Text { text: page.selectedFocusSessions.length + " 次"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    visible: page.selectedFocusSessions.length > 0
                    Repeater {
                        model: page.selectedFocusSessions
                        delegate: Frame {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 52
                            leftPadding: 12; rightPadding: 10; topPadding: 8; bottomPadding: 8
                            RowLayout { anchors.fill: parent; spacing: 10
                                Icon { name: "ic_fluent_timer_20_regular"; size: 20; color: Theme.currentTheme.colors.primaryColor }
                                ColumnLayout { Layout.fillWidth: true; spacing: 1
                                    Text { Layout.fillWidth: true; text: String(modelData.title || "专注会话"); typography: Typography.BodyStrong; elide: Text.ElideRight }
                                    Text { Layout.fillWidth: true; text: String(modelData.subtitle || ""); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; elide: Text.ElideRight }
                                }
                                Text { text: Math.round(Number(modelData.seconds || 0) / 60) + " 分钟"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                            }
                        }
                    }
                }
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 140
                    visible: page.selectedTasks.length === 0 && page.selectedFocusSessions.length === 0
                    ColumnLayout {
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 24, 260)
                        spacing: 5
                        Icon { Layout.alignment: Qt.AlignHCenter; width: 30; height: 30; name: "ic_fluent_calendar_add_20_regular"; size: 30; color: Theme.currentTheme.colors.textSecondaryColor }
                        Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: "这一天还没有任务或专注记录"; typography: Typography.BodyStrong }
                        Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: "在右侧添加一项计划"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                    }
                }
            }
        }

        Frame {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 300
            Layout.fillWidth: true
            Layout.minimumWidth: 270
            leftPadding: 18; rightPadding: 18; topPadding: 16; bottomPadding: 16
            ColumnLayout {
                anchors.fill: parent
                spacing: 9
                RowLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; text: "添加到 " + page.monthDay(page.selectedDate); typography: Typography.Subtitle }
                    Icon { name: "ic_fluent_calendar_add_20_regular"; size: 21; color: Theme.currentTheme.colors.primaryColor }
                }
                TextField { id: titleField; Layout.fillWidth: true; placeholderText: "任务名称"; onTextChanged: page.selectedTitle = text; onAccepted: page.addTask() }
                TextField { Layout.fillWidth: true; placeholderText: "备注（可选）"; onTextChanged: page.selectedMeta = text; onAccepted: page.addTask() }
                RowLayout {
                    Layout.fillWidth: true
                    CheckBox {
                        id: scheduleTimeEnabled
                        text: "到点提醒"
                        onClicked: {
                            if (checked) {
                                if (!scheduleTime.time) scheduleTime.setTime("09:00")
                                page.selectedTime = scheduleTime.time || "09:00"
                            } else {
                                page.selectedTime = ""
                            }
                        }
                    }
                    Item { Layout.fillWidth: true }
                    TimePicker {
                        id: scheduleTime
                        visible: scheduleTimeEnabled.checked
                        enabled: scheduleTimeEnabled.checked
                        Layout.preferredWidth: 138
                        use24Hour: true
                        hourText: "时"
                        minuteText: "分"
                        onTimeChanged: if (scheduleTimeEnabled.checked) page.selectedTime = time
                    }
                }
                Text {
                    Layout.fillWidth: true
                    visible: scheduleTimeEnabled.checked
                    text: "到点后，应用运行时发送一次系统提醒"
                    typography: Typography.Caption
                    color: Theme.currentTheme.colors.textSecondaryColor
                }
                Button { Layout.fillWidth: true; highlighted: true; text: "添加到这一天"; icon.name: "ic_fluent_add_20_regular"; onClicked: { page.addTask(); titleField.forceActiveFocus() } }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.currentTheme.colors.dividerBorderColor; Layout.topMargin: 4; Layout.bottomMargin: 4 }
                Text { Layout.fillWidth: true; text: "本周概览"; typography: Typography.BodyStrong }
                Text { Layout.fillWidth: true; text: page.weekTasks.filter(function(item) { return item.done }).length + " 项已完成"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                Text { Layout.fillWidth: true; text: page.weekTasks.filter(function(item) { return !item.done }).length + " 项待完成"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillHeight: true }
                Text { Layout.fillWidth: true; text: "日程会与今日任务共享数据。"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap }
            }
        }
    }
}
