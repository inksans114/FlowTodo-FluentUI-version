import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window as QtWindow
import RinUI

QtWindow.Window {
    id: widget
    title: "FlowTodo 小组件"
    width: 400
    height: 570
    minimumWidth: 320
    maximumWidth: 720
    minimumHeight: 360
    maximumHeight: 900
    color: "transparent"
    transientParent: null
    // Tool windows stay out of the Windows taskbar and Alt+Tab list while
    // remaining independent, movable desktop widgets.
    flags: Qt.Window | Qt.Tool | Qt.FramelessWindowHint
        | (windowLayer === "top" ? Qt.WindowStaysOnTopHint : 0)
        | (windowLayer === "bottom" ? Qt.WindowStaysOnBottomHint : 0)

    property int currentSection: 0
    property string windowLayer: "top"
    property bool widgetLocked: false
    property var tasks: []
    property var groups: []
    property var projects: []
    readonly property var currentItems: currentSection === 0
        ? tasks.filter(function(item) { return !Boolean(item.done) })
        : currentSection === 1 ? groups : projects

    function reload() {
        try { tasks = JSON.parse(Backend.tasksJson) } catch (error) { tasks = [] }
        try { groups = JSON.parse(Backend.groupsJson) } catch (error) { groups = [] }
        try { projects = JSON.parse(Backend.projectsJson) } catch (error) { projects = [] }
    }
    function kind() { return ["task", "group", "project"][currentSection] }
    function sectionTitle() { return ["待办任务", "任务流", "项目"][currentSection] }
    function itemTitle(item) { return String(item.title || item.name || "未命名") }
    function itemSubtitle(item) {
        if (currentSection === 0)
            return String(item.meta || "待开始")
        if (currentSection === 1) {
            var steps = item.steps || []
            var minutes = 0
            for (var i = 0; i < steps.length; i++)
                minutes += Number(steps[i].duration || steps[i].time || 0)
            return steps.length + " 个步骤 · " + minutes + " 分钟"
        }
        var milestones = item.milestones || []
        var done = milestones.filter(function(entry) { return Boolean(entry.done) }).length
        return done + "/" + milestones.length + " 个里程碑"
    }
    function itemIcon() {
        return currentSection === 0 ? "ic_fluent_checkbox_unchecked_20_regular"
            : currentSection === 1 ? "ic_fluent_flow_20_regular" : "ic_fluent_board_20_regular"
    }
    function clampPosition() {
        var maxX = Math.max(QtWindow.Screen.virtualX, QtWindow.Screen.virtualX + QtWindow.Screen.desktopAvailableWidth - width)
        var maxY = Math.max(QtWindow.Screen.virtualY, QtWindow.Screen.virtualY + QtWindow.Screen.desktopAvailableHeight - height)
        x = Math.max(QtWindow.Screen.virtualX, Math.min(x, maxX))
        y = Math.max(QtWindow.Screen.virtualY, Math.min(y, maxY))
    }
    function savePosition() {
        Backend.setSetting("desktopWidgetX", Math.round(x))
        Backend.setSetting("desktopWidgetY", Math.round(y))
    }
    function showWidget() {
        applyPreferences()
        reload()
        clampPosition()
        show()
        if (windowLayer !== "bottom") {
            raise()
            requestActivate()
        }
    }
    function hideWidget() {
        if (visible)
            savePosition()
        hide()
    }
    function openPreparation(item) {
        Backend.requestFocusPreparation(kind(), Number(item.id))
    }
    function applyPreferences() {
        var wasVisible = visible
        opacity = Math.max(0.35, Math.min(1, Number(Backend.getSetting("desktopWidgetOpacity", 0.96))))
        width = Math.max(minimumWidth, Math.min(maximumWidth, Number(Backend.getSetting("desktopWidgetWidth", 400))))
        height = Math.max(minimumHeight, Math.min(maximumHeight, Number(Backend.getSetting("desktopWidgetHeight", 570))))
        widgetLocked = Boolean(Backend.getSetting("desktopWidgetLocked", false))
        var savedLayer = String(Backend.getSetting("desktopWidgetLayer", "top"))
        var nextLayer = ["top", "normal", "bottom"].indexOf(savedLayer) >= 0 ? savedLayer : "top"
        var layerChanged = windowLayer !== nextLayer
        windowLayer = nextLayer
        clampPosition()
        if (wasVisible && layerChanged) {
            Qt.callLater(function() {
                widget.show()
                if (widget.windowLayer === "top")
                    widget.raise()
            })
        }
    }
    function toggleLocked() {
        widgetLocked = !widgetLocked
        Backend.setSetting("desktopWidgetLocked", widgetLocked)
    }

    Component.onCompleted: {
        x = Number(Backend.getSetting("desktopWidgetX", QtWindow.Screen.virtualX + QtWindow.Screen.desktopAvailableWidth - width - 24))
        y = Number(Backend.getSetting("desktopWidgetY", QtWindow.Screen.virtualY + 72))
        clampPosition()
        applyPreferences()
        reload()
    }
    onClosing: savePosition()

    Connections {
        target: Backend
        function onTasksChanged() { widget.reload() }
        function onGroupsChanged() { widget.reload() }
        function onProjectsChanged() { widget.reload() }
        function onSettingsChanged() { widget.applyPreferences() }
    }

    Rectangle {
        anchors.fill: parent
        radius: 12
        antialiasing: true
        color: Theme.currentTheme.colors.backgroundColor
        border.width: 1
        border.color: Theme.currentTheme.colors.controlBorderColor

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 10

            Item {
                id: dragArea
                Layout.fillWidth: true
                Layout.preferredHeight: 38

                MouseArea {
                    id: windowDragArea
                    objectName: "DesktopWidgetDragArea"
                    anchors.fill: parent
                    anchors.rightMargin: 118
                    enabled: !widget.widgetLocked
                    acceptedButtons: Qt.LeftButton
                    cursorShape: enabled ? Qt.SizeAllCursor : Qt.ArrowCursor
                    property bool manualDrag: false
                    property point lastGlobal: Qt.point(0, 0)
                    onPressed: function(mouse) {
                        lastGlobal = mapToGlobal(mouse.x, mouse.y)
                        manualDrag = !widget.startSystemMove()
                    }
                    onPositionChanged: function(mouse) {
                        if (!manualDrag || !pressed)
                            return
                        var currentGlobal = mapToGlobal(mouse.x, mouse.y)
                        widget.x += currentGlobal.x - lastGlobal.x
                        widget.y += currentGlobal.y - lastGlobal.y
                        lastGlobal = mapToGlobal(mouse.x, mouse.y)
                    }
                    onReleased: function(mouse) {
                        manualDrag = false
                        widget.clampPosition()
                    }
                }
                RowLayout {
                    anchors.fill: parent
                    spacing: 8
                    Icon {
                        name: "ic_fluent_checkmark_circle_20_regular"
                        size: 22
                        color: Theme.currentTheme.colors.primaryColor
                    }
                    Text { Layout.fillWidth: true; text: "FlowTodo"; typography: Typography.BodyStrong }
                    Row {
                        id: headerActions
                        spacing: 2
                        ToolButton {
                            icon.name: widget.widgetLocked
                                ? "ic_fluent_lock_closed_20_regular"
                                : "ic_fluent_lock_open_20_regular"
                            highlighted: widget.widgetLocked
                            ToolTip.text: widget.widgetLocked ? "解除固定" : "固定位置"
                            ToolTip.visible: hovered
                            onClicked: widget.toggleLocked()
                        }
                        ToolButton {
                            icon.name: "ic_fluent_arrow_sync_20_regular"
                            ToolTip.text: "刷新"
                            ToolTip.visible: hovered
                            onClicked: { Backend.reload(); widget.reload() }
                        }
                        ToolButton {
                            icon.name: "ic_fluent_dismiss_20_regular"
                            ToolTip.text: "隐藏小组件"
                            ToolTip.visible: hovered
                            onClicked: widget.hideWidget()
                        }
                    }
                }
            }

            Segmented {
                Layout.fillWidth: true
                currentIndex: widget.currentSection
                onCurrentIndexChanged: widget.currentSection = currentIndex
                SegmentedItem { text: "任务"; icon.name: "ic_fluent_task_list_ltr_20_regular" }
                SegmentedItem { text: "任务流"; icon.name: "ic_fluent_flow_20_regular" }
                SegmentedItem { text: "项目"; icon.name: "ic_fluent_board_20_regular" }
            }

            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: widget.sectionTitle(); typography: Typography.BodyStrong }
                Text {
                    text: widget.currentItems.length + " 项"
                    typography: Typography.Caption
                    color: Theme.currentTheme.colors.textSecondaryColor
                }
            }

            ListView {
                id: itemList
                objectName: "DesktopWidgetItemList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 6
                model: widget.currentItems
                ScrollBar.vertical: ScrollBar {}

                delegate: Frame {
                    required property var modelData
                    width: itemList.width - (itemList.ScrollBar.vertical.visible ? 10 : 0)
                    height: Math.max(72, contentColumn.implicitHeight + topPadding + bottomPadding)
                    leftPadding: 12
                    rightPadding: 8
                    topPadding: 8
                    bottomPadding: 8
                    RowLayout {
                        anchors.fill: parent
                        spacing: 9
                        Item {
                            Layout.preferredWidth: 28
                            Layout.preferredHeight: 32
                            CheckBox {
                                anchors.centerIn: parent
                                width: 32
                                height: 32
                                visible: widget.currentSection === 0
                                checked: Boolean(modelData.done)
                                objectName: "DesktopTaskCheckbox_" + String(modelData.id)
                                onClicked: Backend.toggleTask(Number(modelData.id), checked)
                            }
                            Icon {
                                anchors.centerIn: parent
                                visible: widget.currentSection !== 0
                                name: widget.itemIcon()
                                size: 20
                                color: Theme.currentTheme.colors.primaryColor
                            }
                        }
                        ColumnLayout {
                            id: contentColumn
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                Layout.fillWidth: true
                                text: widget.itemTitle(modelData)
                                typography: Typography.BodyStrong
                                color: Boolean(modelData.done) ? Theme.currentTheme.colors.textColor
                                    : modelData.dailyStatus === "important" ? "#d13438"
                                    : modelData.dailyStatus === "warning" ? "#c58b00"
                                    : Theme.currentTheme.colors.textColor
                                wrapMode: Text.Wrap
                            }
                            Text {
                                Layout.fillWidth: true
                                text: modelData.taskType === "daily"
                                    ? (modelData.dailyStatus === "important" ? "昨日未完成 · 需要优先处理"
                                        : modelData.dailyStatus === "warning" ? "已到提醒时间 · " + String(modelData.reminderTime || "")
                                        : "每日重复 · 每天 0:00 重置 · 提醒 " + String(modelData.reminderTime || ""))
                                    : widget.itemSubtitle(modelData)
                                typography: Typography.Caption
                                color: modelData.dailyStatus === "important" ? "#d13438"
                                    : modelData.dailyStatus === "warning" ? "#c58b00"
                                    : Theme.currentTheme.colors.textSecondaryColor
                                wrapMode: Text.Wrap
                            }
                        }
                        Button {
                            text: "专注"
                            highlighted: true
                            icon.name: "ic_fluent_play_20_regular"
                            onClicked: widget.openPreparation(modelData)
                        }
                    }
                }

                ColumnLayout {
                    anchors.centerIn: parent
                    visible: widget.currentItems.length === 0
                    spacing: 7
                    Icon {
                        Layout.alignment: Qt.AlignHCenter
                        name: widget.currentSection === 0 ? "ic_fluent_checkmark_circle_20_regular" : widget.itemIcon()
                        size: 34
                        color: Theme.currentTheme.colors.textSecondaryColor
                    }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: widget.currentSection === 0 ? "没有待办任务" : "这里还没有内容"
                        typography: Typography.BodyStrong
                    }
                }
            }
        }
    }
}
