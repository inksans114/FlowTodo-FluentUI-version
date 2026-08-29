import QtQuick
import QtQuick.Controls
import QtQuick.Window as QtWindow
import RinUI

QtWindow.Window {
    id: paper
    visible: false
    title: noteTitle
    color: "transparent"
    opacity: Number(Backend.getSetting("notesOpacity", 0.96))
    flags: Qt.Window | Qt.Tool | Qt.FramelessWindowHint
        | (alwaysOnTop ? Qt.WindowStaysOnTopHint : 0)

    property string noteId: ""
    property string noteTitle: "未命名便签"
    property string noteContent: ""
    property bool collapsed: false
    property bool alwaysOnTop: false
    property real paperX: 120
    property real paperY: 120
    property real paperWidth: 320
    property real paperHeight: 360

    signal noteEdited(string noteId, string title, string content)
    signal geometryCommitted(string noteId, real x, real y, real width, real height)
    signal collapseRequested(string noteId)
    signal deleteRequested(string noteId)
    signal hideRequested(string noteId)
    signal showRequested(string noteId)

    width: collapsed ? 128 : paperWidth
    height: collapsed ? 52 : paperHeight
    x: paperX
    y: paperY

    onCollapsedChanged: {
        width = collapsed ? 128 : paperWidth
        height = collapsed ? 52 : paperHeight
    }

    function syncOpacity() {
        opacity = Math.max(0.45, Math.min(1, Number(Backend.getSetting("notesOpacity", 0.96))))
    }

    onPaperXChanged: if (Math.abs(x - paperX) > 1) x = paperX
    onPaperYChanged: if (Math.abs(y - paperY) > 1) y = paperY
    onPaperWidthChanged: if (!collapsed && Math.abs(width - paperWidth) > 1) width = paperWidth
    onPaperHeightChanged: if (!collapsed && Math.abs(height - paperHeight) > 1) height = paperHeight
    onXChanged: if (visible && !collapsed) geometryCommitted(noteId, x, y, width, height)
    onYChanged: if (visible && !collapsed) geometryCommitted(noteId, x, y, width, height)
    onClosing: function(close) {
        close.accepted = false
        hideRequested(noteId)
    }

    Connections {
        target: Backend
        function onSettingsChanged() { paper.syncOpacity() }
    }

    Rectangle {
        id: surface
        anchors.fill: parent
        radius: paper.collapsed ? 13 : 10
        color: Theme.currentTheme.colors.backgroundColor
        border.width: paper.collapsed ? 2 : 1
        border.color: paper.collapsed ? Theme.currentTheme.colors.primaryColor : Theme.currentTheme.colors.controlBorderColor
        antialiasing: true

        MouseArea {
            id: capsuleInteraction
            visible: paper.collapsed
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeAllCursor
            property point pressGlobal: Qt.point(0, 0)
            property bool dragging: false
            property bool systemMoveStarted: false
            onPressed: function(mouse) {
                pressGlobal = mapToGlobal(mouse.x, mouse.y)
                dragging = false
                systemMoveStarted = false
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                var current = mapToGlobal(mouse.x, mouse.y)
                var distance = Math.abs(current.x - pressGlobal.x) + Math.abs(current.y - pressGlobal.y)
                if (!dragging && distance >= 6) {
                    dragging = true
                    systemMoveStarted = paper.startSystemMove()
                }
                if (dragging && !systemMoveStarted) {
                    paper.x += current.x - pressGlobal.x
                    paper.y += current.y - pressGlobal.y
                    pressGlobal = current
                }
            }
            onReleased: {
                if (!dragging)
                    paper.collapseRequested(paper.noteId)
                else
                    paper.geometryCommitted(paper.noteId, paper.x, paper.y, paper.width, paper.height)
            }
        }

        MouseArea {
            id: titleDragArea
            visible: !paper.collapsed
            x: 0
            y: 0
            width: parent.width
            height: 48
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.SizeAllCursor
            property point pressGlobal: Qt.point(0, 0)
            property bool dragging: false
            property bool systemMoveStarted: false
            onPressed: function(mouse) {
                pressGlobal = mapToGlobal(mouse.x, mouse.y)
                dragging = false
                systemMoveStarted = false
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                var current = mapToGlobal(mouse.x, mouse.y)
                var distance = Math.abs(current.x - pressGlobal.x) + Math.abs(current.y - pressGlobal.y)
                if (!dragging && distance >= 6) {
                    dragging = true
                    systemMoveStarted = paper.startSystemMove()
                }
                if (dragging && !systemMoveStarted) {
                    paper.x += current.x - pressGlobal.x
                    paper.y += current.y - pressGlobal.y
                    pressGlobal = current
                }
            }
            onReleased: if (dragging) paper.geometryCommitted(paper.noteId, paper.x, paper.y, paper.width, paper.height)
        }

        Icon {
            id: noteIcon
            x: 12
            y: 14
            size: paper.collapsed ? 18 : 20
            name: "ic_fluent_note_20_regular"
            color: Theme.currentTheme.colors.primaryColor
        }

        Text {
            visible: paper.collapsed
            x: 36
            y: 10
            width: parent.width - 48
            height: 20
            text: paper.noteTitle
            elide: Text.ElideRight
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textPrimaryColor
        }

        Text {
            visible: paper.collapsed
            x: 36
            y: 29
            width: parent.width - 48
            height: 16
            text: paper.noteContent.length ? paper.noteContent.replace(/\s+/g, " ") : "空便签"
            elide: Text.ElideRight
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
        }

        TextField {
            id: titleInput
            visible: !paper.collapsed
            x: 42
            y: 9
            width: parent.width - 126
            height: 30
            text: paper.noteTitle
            placeholderText: "便签标题"
            background: Rectangle { color: "transparent" }
            onTextChanged: if (paper.visible && text !== paper.noteTitle) paper.noteEdited(paper.noteId, text, bodyInput.text)
        }

        ToolButton {
            visible: !paper.collapsed
            x: parent.width - 84
            y: 7
            width: 34
            height: 34
            icon.name: "ic_fluent_arrow_minimize_20_regular"
            ToolTip.text: "折叠为胶囊"
            ToolTip.visible: hovered
            onClicked: paper.collapseRequested(paper.noteId)
        }

        ToolButton {
            visible: !paper.collapsed
            x: parent.width - 45
            y: 7
            width: 34
            height: 34
            icon.name: "ic_fluent_dismiss_20_regular"
            ToolTip.text: "隐藏便签"
            ToolTip.visible: hovered
            onClicked: paper.hideRequested(paper.noteId)
        }

        Frame {
            id: bodyFrame
            visible: !paper.collapsed
            x: 10
            y: 50
            width: parent.width - 20
            height: parent.height - 60
            padding: 0
            background: Rectangle {
                radius: 6
                color: Qt.alpha(Theme.currentTheme.colors.controlColor, 0.72)
                border.width: 1
                border.color: Theme.currentTheme.colors.controlBorderColor
            }
            ScrollView {
                anchors.fill: parent
                anchors.margins: 8
                clip: true
                TextArea {
                    id: bodyInput
                    width: Math.max(0, parent.width)
                    text: paper.noteContent
                    readOnly: false
                    wrapMode: TextEdit.Wrap
                    placeholderText: "写下今天要记住的事..."
                    selectByMouse: true
                    background: Rectangle { color: "transparent" }
                    onTextChanged: if (paper.visible && text !== paper.noteContent) paper.noteEdited(paper.noteId, titleInput.text, text)
                }
            }
        }
    }
}
