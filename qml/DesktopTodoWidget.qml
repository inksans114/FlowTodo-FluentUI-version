import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window as QtWindow
import RinUI
import "i18n"

QtWindow.Window {
    id: widget
    title: I18n.t("FlowTodo 小组件")
    width: 360
    height: 570
    minimumWidth: 320
    maximumWidth: 720
    minimumHeight: 144
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
    function sectionTitle() { return [I18n.t("待办任务"), I18n.t("任务流"), I18n.t("项目")][currentSection] }
    function itemTitle(item) { return String(item.title || item.name || I18n.t("未命名")) }
    function itemSubtitle(item) {
        if (currentSection === 0)
            return String(item.meta || I18n.t("待开始"))
        if (currentSection === 1) {
            var steps = item.steps || []
            var minutes = 0
            for (var i = 0; i < steps.length; i++)
                minutes += Number(steps[i].duration || steps[i].time || 0)
            return steps.length + I18n.t(" 个步骤 · ") + minutes + I18n.t(" 分钟")
        }
        var milestones = item.milestones || []
        var done = milestones.filter(function(entry) { return Boolean(entry.done) }).length
        return done + "/" + milestones.length + I18n.t(" 个里程碑")
    }
    function itemIcon() {
        return currentSection === 0 ? "ic_fluent_checkbox_unchecked_20_regular"
            : currentSection === 1 ? "ic_fluent_flow_20_regular" : "ic_fluent_board_20_regular"
    }
    function screenSnapshot() {
        return {
            name: String(QtWindow.Screen.name || ""),
            x: Number(QtWindow.Screen.virtualX),
            y: Number(QtWindow.Screen.virtualY),
            width: Number(QtWindow.Screen.desktopAvailableWidth),
            height: Number(QtWindow.Screen.desktopAvailableHeight)
        }
    }
    function mapSavedPosition() {
        var old = Backend.getSetting("desktopWidgetWorkArea", null)
        if (!old || Number(old.width) <= 0 || Number(old.height) <= 0)
            return
        var current = screenSnapshot()
        var oldX = Number(old.x)
        var oldY = Number(old.y)
        var relativeX = (Number(Backend.getSetting("desktopWidgetX", x)) - oldX) / Number(old.width)
        var relativeY = (Number(Backend.getSetting("desktopWidgetY", y)) - oldY) / Number(old.height)
        x = current.x + relativeX * current.width
        y = current.y + relativeY * current.height
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
        Backend.setSettingJson("desktopWidgetWorkArea", JSON.stringify(screenSnapshot()))
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
        fitContent()
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
        mapSavedPosition()
        clampPosition()
        applyPreferences()
        reload()
    }
    onScreenChanged: {
        mapSavedPosition()
        clampPosition()
    }
    onClosing: savePosition()

    Connections {
        target: Backend
        function onTasksChanged() { widget.reload() }
        function onGroupsChanged() { widget.reload() }
        function onProjectsChanged() { widget.reload() }
        function onSettingsChanged() { widget.applyPreferences() }
    }

    property bool ready: false
    property bool compactMode: Boolean(Backend.getSetting("desktopWidgetCompact",true))
    function fitContent() {
        if(compactMode) height=Math.min(Math.max(200,Number(Backend.getSetting("desktopWidgetHeight",570))),76+Math.max(1,Math.min(currentItems.length,8))*72)
    }
    onCurrentItemsChanged: if(ready) fitContent()
    Timer { interval: 0; running: true; onTriggered: { widget.ready=true; widget.fitContent() } }
    Rectangle {
        anchors.fill: parent; radius: 16
        color: Theme.currentTheme.colors.backgroundColor
        border.color: Qt.alpha(Theme.currentTheme.colors.textSecondaryColor,0.16)
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 8
            Item {
                Layout.fillWidth: true; Layout.preferredHeight: 32
                MouseArea {
                    objectName: "DesktopWidgetDragArea"
                    anchors.fill: parent; anchors.rightMargin: 70
                    enabled: !widget.widgetLocked; cursorShape: Qt.SizeAllCursor
                    property bool manualDrag: false
                    property point lastGlobal: Qt.point(0,0)
                    onPressed: function(mouse) { lastGlobal=mapToGlobal(mouse.x,mouse.y); manualDrag=!widget.startSystemMove() }
                    onPositionChanged: function(mouse) {
                        if(!manualDrag || !pressed) return
                        var p=mapToGlobal(mouse.x,mouse.y)
                        widget.x+=p.x-lastGlobal.x;widget.y+=p.y-lastGlobal.y
                        lastGlobal=mapToGlobal(mouse.x,mouse.y)
                    }
                    onReleased: { manualDrag=false;widget.clampPosition() }
                }
                RowLayout {
                    anchors.fill: parent; spacing: 6
                    Text { text: widget.sectionTitle(); font.pixelSize: 14; font.weight: Font.DemiBold }
                    Text { text: widget.currentItems.length; font.pixelSize: 12; color: Theme.currentTheme.colors.textSecondaryColor }
                    Item { Layout.fillWidth: true }
                    ToolButton { id: options; objectName: "desktopWidgetOptions"; implicitWidth: 30; implicitHeight: 30; flat: true; icon.name: "ic_fluent_more_horizontal_20_regular"; Accessible.name: I18n.t("组件选项"); onClicked: optionsMenu.open() }
                    ToolButton { objectName: "desktopWidgetHide"; implicitWidth: 30; implicitHeight: 30; flat: true; icon.name: "ic_fluent_dismiss_20_regular"; Accessible.name: I18n.t("隐藏组件"); onClicked: widget.hideWidget() }
                }
            }
            ListView {
                id: itemList
                objectName: "DesktopWidgetItemList"
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 4
                model: widget.currentItems
                ScrollBar.vertical: ScrollBar { }
                displaced: Transition { NumberAnimation { properties: "y"; duration: Backend.systemMotionEnabled ? 150 : 0; easing.type: Easing.OutCubic } }
                delegate: Rectangle {
                    id: row
                    required property var modelData
                    width: itemList.width; height: 68; radius: 10
                    color: hover.hovered ? Theme.currentTheme.colors.controlColor : "transparent"
                    Behavior on color { ColorAnimation { duration: Backend.systemMotionEnabled ? 120 : 0 } }
                    HoverHandler { id: hover }
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 6; spacing: 8
                        CheckBox { objectName: "DesktopTaskCheckbox_"+String(modelData.id); visible: widget.currentSection===0; Layout.preferredWidth: 28; Layout.preferredHeight: 32; checked: Boolean(modelData.done); Accessible.name: I18n.t("完成 ") + widget.itemTitle(modelData); onClicked: Backend.toggleTask(Number(modelData.id),checked) }
                        Icon { visible: widget.currentSection!==0; name: widget.itemIcon(); size: 18; color: Theme.currentTheme.colors.primaryColor }
                        ColumnLayout { Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 3
                            Text { Layout.fillWidth: true; text: widget.itemTitle(modelData); font.pixelSize: 14; font.weight: Font.Medium; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.15 }
                            Text { Layout.fillWidth: true; text: modelData.dailyStatus==="important" ? I18n.t("昨日未完成") : widget.itemSubtitle(modelData); visible: text.length>0 && text!==I18n.t("待开始"); font.pixelSize: 11; elide: Text.ElideRight; maximumLineCount: 1; wrapMode: Text.NoWrap; color: Theme.currentTheme.colors.textSecondaryColor }
                        }
                        ToolButton { objectName: "desktopFocus_"+String(modelData.id); implicitWidth: 32; implicitHeight: 32; flat: true; icon.name: "ic_fluent_play_20_regular"; opacity: hover.hovered || activeFocus ? 1 : 0.55; Accessible.name: I18n.t("专注 ") + widget.itemTitle(modelData); ToolTip.text: I18n.t("开始专注"); ToolTip.visible: hovered; onClicked: widget.openPreparation(modelData) }
                    }
                }
                Text { anchors.centerIn: parent; visible: !widget.currentItems.length; text: I18n.t("暂时没有待办，歇一会儿。"); font.pixelSize: 13; color: Theme.currentTheme.colors.textSecondaryColor }
            }
        }
    }
    Menu {
        id: optionsMenu; parent: options
        x: parent.width-width; y: parent.height+4
        MenuItem { text: I18n.t("待办任务"); checkable: true; checked: widget.currentSection===0; onTriggered: widget.currentSection=0 }
        MenuItem { text: I18n.t("任务流"); checkable: true; checked: widget.currentSection===1; onTriggered: widget.currentSection=1 }
        MenuItem { text: I18n.t("项目"); checkable: true; checked: widget.currentSection===2; onTriggered: widget.currentSection=2 }
        MenuSeparator { }
        MenuItem { text: I18n.t("固定位置"); checkable: true; checked: widget.widgetLocked; onTriggered: widget.toggleLocked() }
        MenuItem { text: I18n.t("紧凑高度"); checkable: true; checked: widget.compactMode; onTriggered: { widget.compactMode=!widget.compactMode; Backend.setSetting("desktopWidgetCompact",widget.compactMode); widget.applyPreferences(); widget.fitContent() } }
        MenuItem { text: I18n.t("刷新内容"); onTriggered: { Backend.reload(); widget.reload() } }
    }
}
