import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "AccountOverview"
    title: I18n.t("我的专注数据")
    wrapperWidth: 1040
    horizontalPadding: 32
    contentSpacing: 18
    LayoutTokens { id: ui }
    readonly property bool compactLayout: width - horizontalPadding * 2 < 920

    property var stats: ({tasks: {}, groups: {}, projects: {}, focus: {}})
    property var tasks: []
    property var taskHistory: []
    property var focusSessions: []
    property var achievements: []
    property var calendarCells: []
    property var monthMarkers: []
    property string selectedDate: page.todayKey()
    property int historyWeeks: compactLayout ? 52 : 26
    readonly property real cellSize: Math.max(8, (activityScroller.width - (page.historyWeeks - 1) * page.gridGap) / page.historyWeeks)
    readonly property int gridGap: compactLayout ? 3 : 4
    readonly property real calendarGridWidth: page.historyWeeks * page.cellSize + (page.historyWeeks - 1) * page.gridGap
    readonly property int weekdayLabelWidth: 22
    readonly property int calendarContentWidth: page.weekdayLabelWidth + 8 + page.calendarGridWidth
    readonly property string activityRangeLabel: page.compactLayout ? I18n.t("近一年") : I18n.t("近半年")
    property bool layoutSettled: true
    readonly property string today: page.todayKey()
    property var selectedTasks: page.tasks.concat(page.taskHistory).filter(function(item) {
        var date = String(item.scheduledDate || item.dailyDate || "")
        return date === page.selectedDate || String(item.historyDate || "") === page.selectedDate
    })
    property var selectedFocusSessions: page.focusSessions.filter(function(item) {
        return String(item.date || "") === page.selectedDate
    })
    readonly property int selectedTaskTotal: page.selectedTasks.length
    readonly property int selectedTaskDone: page.selectedTasks.filter(function(item) { return Boolean(item.done) }).length
    readonly property int selectedTaskRate: page.selectedTaskTotal ? Math.round(page.selectedTaskDone / page.selectedTaskTotal * 100) : 0

    function pad(value) { return value < 10 ? "0" + value : String(value) }
    function todayKey() {
        var now = new Date()
        return now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate())
    }
    function dateKey(date) {
        return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate())
    }
    function dateFromKey(key) {
        var parts = String(key).split("-")
        return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
    }
    function shiftDate(key, days) {
        var date = dateFromKey(key)
        date.setDate(date.getDate() + days)
        return dateKey(date)
    }
    function displayDate(key) {
        var date = dateFromKey(key)
        return date.getMonth() + 1 + I18n.t("月") + date.getDate() + I18n.t("日")
    }
    function focusSecondsFor(key) {
        var daily = (page.stats.focus || {}).dailyFocusSeconds || {}
        return Number(daily[key] || 0)
    }
    function formatFocusDuration(seconds) {
        var minutes = Math.round(Number(seconds || 0) / 60)
        return minutes + I18n.t(" 分钟")
    }
    function focusLevel(seconds) {
        var minutes = Number(seconds || 0) / 60
        return minutes <= 0 ? 0 : minutes < 15 ? 1 : minutes < 30 ? 2 : minutes < 60 ? 3 : 4
    }
    function cellColor(level) {
        if (level === 0) return Theme.currentTheme.colors.controlAltSecondaryColor
        if (level === 1) return Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.24)
        if (level === 2) return Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.43)
        if (level === 3) return Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.67)
        return Theme.currentTheme.colors.primaryColor
    }
    function buildCalendar() {
        var daily = (page.stats.focus || {}).dailyFocusSeconds || {}
        var cells = []
        var end = new Date()
        var mondayOffset = (end.getDay() + 6) % 7
        end.setDate(end.getDate() - mondayOffset)
        var start = new Date(end)
        start.setDate(start.getDate() - (page.historyWeeks - 1) * 7)
        // GridLayout is row-major: keep each weekday on one row and each week in a column.
        for (var day = 0; day < 7; day++) {
            for (var week = 0; week < page.historyWeeks; week++) {
                var date = new Date(start)
                date.setDate(start.getDate() + week * 7 + day)
                var key = dateKey(date)
                var seconds = Number(daily[key] || 0)
                cells.push({key: key, seconds: seconds, level: page.focusLevel(seconds)})
            }
        }
        var markers = []
        var lastMonth = -1
        for (var markerWeek = 0; markerWeek < page.historyWeeks; markerWeek++) {
            var markerDate = new Date(start)
            markerDate.setDate(start.getDate() + markerWeek * 7)
            if (markerDate.getMonth() !== lastMonth) {
                markers.push({label: (markerDate.getMonth() + 1) + I18n.t("月"), column: markerWeek})
                lastMonth = markerDate.getMonth()
            }
        }
        page.monthMarkers = markers
        return cells
    }
    function nav() {
        var item = page
        while (item) {
            if (item.objectName === "MainNavigationView") return item
            item = item.parent
        }
        return null
    }
    function openSchedule() {
        var router = page.nav()
        if (router) router.push(Qt.resolvedUrl("ScheduleWorkspace.qml"), {selectedDate: page.selectedDate})
    }
    function rebuildCalendar() {
        page.layoutSettled = false
        page.calendarCells = page.buildCalendar()
        Qt.callLater(function() { page.layoutSettled = true })
    }
    function reload() {
        try { page.stats = JSON.parse(Backend.statsJson) } catch (error) { page.stats = {tasks: {}, groups: {}, projects: {}, focus: {}} }
        try { page.tasks = JSON.parse(Backend.tasksJson) } catch (error) { page.tasks = [] }
        page.taskHistory = (page.stats.tasks || {}).history || []
        page.focusSessions = (page.stats.focus || {}).sessions || []
        try { page.achievements = JSON.parse(Backend.achievementsJson) } catch (error) { page.achievements = [] }
        page.rebuildCalendar()
    }

    Component.onCompleted: page.reload()
    Timer {
        id: layoutRebuildTimer
        interval: 120
        repeat: false
        onTriggered: page.rebuildCalendar()
    }
    onCompactLayoutChanged: {
        layoutRebuildTimer.restart()
        layoutPulse.restart()
    }
    SequentialAnimation {
        id: layoutPulse
        NumberAnimation { target: activitySection; property: "opacity"; to: 0.84; duration: 70; easing.type: Easing.OutCubic }
        NumberAnimation { target: activitySection; property: "opacity"; to: 1.0; duration: 180; easing.type: Easing.OutCubic }
    }
    Connections {
        target: Backend
        function onStatsChanged() { page.reload() }
        function onTasksChanged() { page.reload() }
        function onAchievementsChanged() { page.reload() }
    }

    RowLayout {
        Layout.fillWidth: true
        Button {
            objectName: "focusDataBackButton"
            text: I18n.t("返回我的账户")
            icon.name: "ic_fluent_arrow_left_20_regular"
            onClicked: { var router = page.nav(); if (router) router.pop() }
        }
        Item { Layout.fillWidth: true }
        Button { text: I18n.t("查看日程"); highlighted: true; icon.name: "ic_fluent_calendar_ltr_20_regular"; onClicked: page.openSchedule() }
        Button {
            text: I18n.t("查看成就")
            icon.name: "ic_fluent_trophy_20_regular"
            onClicked: { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("AchievementsPage.qml")) }
        }
    }

    GridLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        columns: page.compactLayout ? 1 : 2
        columnSpacing: ui.cardGap
        rowSpacing: ui.cardGap

        Frame {
            id: activitySection
            objectName: "activitySection"
            Layout.alignment: Qt.AlignTop
            Layout.fillWidth: true
            Layout.preferredWidth: page.compactLayout ? 0 : 640
            Layout.minimumWidth: 0
            leftPadding: 18; rightPadding: 18; topPadding: 16; bottomPadding: 16
            contentItem: ColumnLayout {
                spacing: 12
                RowLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; text: I18n.t("专注活动"); typography: Typography.Subtitle }
                    Text { text: page.activityRangeLabel; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                }
                Text { Layout.fillWidth: true; text: I18n.t("每天的专注时长会以方块记录，点击某一天查看计划和专注记录。"); wrapMode: Text.Wrap; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 7 * page.cellSize + 18 + 6 * page.gridGap + 34
                    spacing: 8
                    Column {
                        Layout.preferredWidth: page.weekdayLabelWidth
                        Layout.alignment: Qt.AlignTop
                        topPadding: 23
                        spacing: page.gridGap
                        Repeater {
                            model: [I18n.t("一"), "", I18n.t("三"), "", I18n.t("五"), "", I18n.t("日")]
                            delegate: Text {
                                width: page.weekdayLabelWidth
                                height: page.cellSize
                                text: modelData
                                typography: Typography.Caption
                                color: Theme.currentTheme.colors.textSecondaryColor
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                    Flickable {
                        id: activityScroller
                        objectName: "activityScroller"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        contentWidth: page.calendarGridWidth
                        contentHeight: height
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                        Item {
                            width: page.calendarGridWidth
                            height: activityScroller.height
                            Repeater {
                                model: page.monthMarkers
                                delegate: Text {
                                    required property var modelData
                                    x: Math.min(modelData.column * (page.cellSize + page.gridGap), Math.max(0, page.calendarGridWidth - 42))
                                    y: 0
                                    width: Math.min(42, page.calendarGridWidth - x)
                                    text: modelData.label
                                    elide: Text.ElideRight
                                    typography: Typography.Caption
                                    color: Theme.currentTheme.colors.textSecondaryColor
                                }
                            }
                            Grid {
                                id: activityGrid
                                objectName: "activityGrid"
                                x: 0
                                y: 23
                                width: page.calendarGridWidth
                                columns: page.historyWeeks
                                rowSpacing: page.gridGap
                                columnSpacing: page.gridGap
                                Repeater {
                                    model: page.calendarCells
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: page.cellSize
                                        height: page.cellSize
                                        radius: 3
                                        color: page.cellColor(modelData.level)
                                        border.width: modelData.key === page.selectedDate ? 2 : modelData.key === page.today ? 1 : 0
                                        border.color: modelData.key === page.selectedDate ? Theme.currentTheme.colors.primaryColor : Theme.currentTheme.colors.textSecondaryColor
                                        scale: activityMouse.containsMouse ? 1.12 : 1
                                        Behavior on scale { NumberAnimation { duration: 100 } }
                                        MouseArea { id: activityMouse; anchors.fill: parent; hoverEnabled: true; onClicked: page.selectedDate = modelData.key }
                                        ToolTip.visible: activityMouse.containsMouse
                                        ToolTip.text: modelData.key + " · " + (Math.round(modelData.seconds / 60) || 0) + I18n.t(" 分钟")
                                    }
                                }
                            }
                            Row {
                                id: activityLegend
                                x: 0
                                y: 23 + 7 * (page.cellSize + page.gridGap) + 6
                                width: 24 + 8 + 5 * page.cellSize + 4 * page.gridGap + 8 + 24
                                height: page.cellSize
                                spacing: 8
                                Text { width: 24; height: page.cellSize; text: I18n.t("少"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; verticalAlignment: Text.AlignVCenter }
                                Row {
                                    spacing: page.gridGap
                                    Repeater { model: [0, 1, 2, 3, 4]; delegate: Rectangle { width: page.cellSize; height: page.cellSize; radius: 3; color: page.cellColor(modelData) } }
                                }
                                Text { width: 24; height: page.cellSize; text: I18n.t("多"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; verticalAlignment: Text.AlignVCenter }
                            }
                        }
                    }
                }
            }
        }

        Frame {
            Layout.alignment: Qt.AlignTop
            objectName: "selectedDayCard"
            Layout.preferredWidth: page.compactLayout ? 0 : 340
            Layout.fillWidth: true
            Layout.minimumWidth: page.compactLayout ? 0 : 310
            leftPadding: 18; rightPadding: 18; topPadding: 16; bottomPadding: 16
            contentItem: ColumnLayout {
                spacing: 14
                RowLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; text: page.displayDate(page.selectedDate); typography: Typography.Subtitle }
                    Text { text: page.selectedDate === page.today ? I18n.t("今天") : ""; typography: Typography.Caption; color: Theme.currentTheme.colors.primaryColor }
                }
                Frame {
                    Layout.fillWidth: true; Layout.preferredHeight: 66
                    leftPadding: 12; rightPadding: 12; topPadding: 10; bottomPadding: 10
                    contentItem: RowLayout {
                        Icon { name: "ic_fluent_timer_20_regular"; size: 22; color: Theme.currentTheme.colors.primaryColor }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text { text: Math.round(page.focusSecondsFor(page.selectedDate) / 60) + I18n.t(" 分钟"); typography: Typography.BodyStrong }
                            Text { text: I18n.t("专注时长"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; text: I18n.t("当天计划"); typography: Typography.BodyStrong }
                    Text { text: page.selectedTasks.length + I18n.t(" 项"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 8
                    Repeater {
                        model: page.selectedTasks.slice(0, 3)
                        delegate: Frame {
                            required property var modelData
                            Layout.fillWidth: true; Layout.preferredHeight: 64
                            leftPadding: 14; rightPadding: 14; topPadding: 12; bottomPadding: 12
                            contentItem: RowLayout { spacing: 8
                                Icon { name: modelData.done ? "ic_fluent_checkmark_circle_20_regular" : "ic_fluent_checkbox_unchecked_20_regular"; size: 17; color: modelData.done ? "#107c10" : Theme.currentTheme.colors.primaryColor }
                                Text { Layout.fillWidth: true; text: String(modelData.title || I18n.t("未命名任务")); typography: Typography.Caption; elide: Text.ElideRight; font.strikeout: Boolean(modelData.done) }
                                Text { text: String(modelData.scheduledTime || ""); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: page.selectedFocusSessions.length > 0
                    Text { Layout.fillWidth: true; text: I18n.t("专注记录"); typography: Typography.BodyStrong }
                    Text { text: page.selectedFocusSessions.length + I18n.t(" 次"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: page.selectedFocusSessions.length > 0
                    Repeater {
                        model: page.selectedFocusSessions.slice(0, 3)
                        delegate: Frame {
                            required property var modelData
                            Layout.fillWidth: true; Layout.preferredHeight: 64
                            leftPadding: 14; rightPadding: 14; topPadding: 12; bottomPadding: 12
                            contentItem: RowLayout { spacing: 8
                                Icon { name: "ic_fluent_timer_20_regular"; size: 17; color: Theme.currentTheme.colors.primaryColor }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredWidth: 0
                                    spacing: 5
                                    Text { Layout.fillWidth: true; text: String(modelData.title || I18n.t("专注会话")); typography: Typography.Caption; elide: Text.ElideRight }
                                    Text { Layout.fillWidth: true; text: String(modelData.subtitle || ""); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; elide: Text.ElideRight }
                                }
                                Text { text: page.formatFocusDuration(modelData.seconds); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                            }
                        }
                    }
                }
                Item { Layout.preferredHeight: 8; Layout.minimumHeight: 8; Layout.maximumHeight: 8 }
                Text { Layout.fillWidth: true; visible: page.selectedTasks.length === 0 && page.selectedFocusSessions.length === 0; text: I18n.t("这一天还没有计划或专注记录"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                Button { Layout.fillWidth: true; text: I18n.t("打开当天日程"); icon.name: "ic_fluent_arrow_right_20_regular"; onClicked: page.openSchedule() }
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        leftPadding: 18; rightPadding: 18; topPadding: 14; bottomPadding: 14
        contentItem: RowLayout { spacing: 18
            Text { Layout.fillWidth: true; text: page.selectedTaskTotal ? I18n.t("当天任务 ") + page.selectedTaskDone + " / " + page.selectedTaskTotal : I18n.t("当天任务 0 项"); typography: Typography.BodyStrong }
            ProgressBar { visible: page.selectedTaskTotal > 0; Layout.preferredWidth: 230; from: 0; to: 100; value: page.selectedTaskRate }
            Text { text: page.selectedTaskTotal > 0 ? page.selectedTaskRate + "%" : I18n.t("暂无进度"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
}
