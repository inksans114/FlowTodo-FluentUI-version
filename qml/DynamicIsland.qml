import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 440
    height: 330
    color: "transparent"

    property string taskTitle: "准备开始"
    property string taskSubtitle: ""
    property string phaseLabel: "阶段 1/1"
    property string statusLabel: "专注中"
    property string taskType: "focus"
    property string environmentText: ""
    property string guardMessage: ""
    property int remainingSeconds: 0
    property int totalSeconds: 0
    property bool running: false
    property bool expanded: false
    property bool switching: false
    property bool exitCancelled: false
    property bool guardVisible: false
    property bool finished: false

    signal pauseRequested()
    signal resumeRequested()
    signal cancelRequested()
    signal expansionChanged(bool expanded)
    signal exitFinished()

    function formatTime(value) {
        var seconds = Math.max(0, value)
        var minutes = Math.floor(seconds / 60)
        return ("0" + minutes).slice(-2) + ":" + ("0" + (seconds % 60)).slice(-2)
    }

    function enterIsland() {
        entrance.restart()
    }

    function exitIsland(cancelled) {
        exitCancelled = cancelled
        finished = true
        exitAnimation.restart()
    }

    function showGuard(message) {
        guardMessage = message
        guardVisible = true
        guardTimer.restart()
    }

    onExpandedChanged: expansionChanged(expanded)

    Rectangle {
        id: island
        anchors.horizontalCenter: parent.horizontalCenter
        y: 10
        width: root.expanded ? 380 : 238
        height: root.expanded ? 272 : 54
        radius: root.expanded ? 28 : height / 2
        color: root.taskType === "break" ? "#183b35" : "#151519"
        border.width: root.expanded ? 1 : 0
        border.color: root.taskType === "break" ? "#3c8270" : "#38363e"
        opacity: 0
        scale: 0.82
        clip: true

        Behavior on width {
            NumberAnimation { duration: 420; easing.type: Easing.OutQuint }
        }
        Behavior on height {
            NumberAnimation { duration: 420; easing.type: Easing.OutQuint }
        }
        Behavior on radius {
            NumberAnimation { duration: 340; easing.type: Easing.OutQuint }
        }

        Rectangle {
            anchors.fill: parent
            radius: island.radius
            color: "transparent"
            border.width: 1
            border.color: "#33ffffff"
            visible: root.expanded
        }

        Rectangle {
            id: statusDot
            width: 10
            height: 10
            radius: width / 2
            x: 18
            anchors.verticalCenter: collapsedContent.verticalCenter
            color: root.taskType === "break" ? "#46cea3" : "#8b7cff"

            SequentialAnimation on opacity {
                running: root.running
                loops: Animation.Infinite
                NumberAnimation { to: 0.38; duration: 900; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutSine }
            }
        }

        Item {
            id: collapsedContent
            anchors.fill: parent
            opacity: root.expanded ? 0 : 1
            visible: opacity > 0

            Behavior on opacity {
                NumberAnimation { duration: root.expanded ? 100 : 210; easing.type: Easing.OutCubic }
            }

            Text {
                id: timerLabel
                anchors.left: statusDot.right
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: root.formatTime(root.remainingSeconds)
                color: "#f4f1f8"
                font.family: "Microsoft YaHei UI"
                font.pixelSize: 17
                font.weight: Font.DemiBold
                font.letterSpacing: 0
            }

            Text {
                anchors.left: timerLabel.right
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: root.phaseLabel
                color: "#b8b3bf"
                font.family: "Microsoft YaHei UI"
                font.pixelSize: 12
                elide: Text.ElideRight
                width: 76
            }

            Text {
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                text: root.statusLabel
                color: root.running ? "#d9d2ff" : "#ffc3bb"
                font.family: "Microsoft YaHei UI"
                font.pixelSize: 12
            }
        }

        Item {
            id: expandedContent
            anchors.fill: parent
            anchors.margins: 18
            opacity: root.expanded ? 1 : 0
            visible: opacity > 0
            transform: Translate { y: root.expanded ? 0 : -8 }

            Behavior on opacity {
                NumberAnimation { duration: root.expanded ? 240 : 110; easing.type: Easing.OutCubic }
            }

            Column {
                anchors.fill: parent
                spacing: 9

                Row {
                    width: parent.width
                    spacing: 10

                    Rectangle {
                        width: 34
                        height: 34
                        radius: 12
                        color: root.taskType === "break" ? "#2f6c5c" : "#423b78"
                        Text {
                            anchors.centerIn: parent
                            text: root.taskType === "break" ? "休" : "专"
                            color: "white"
                            font.family: "Microsoft YaHei UI"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                    }

                    Column {
                        width: 255
                        spacing: 2
                        Text {
                            width: parent.width
                            text: root.taskTitle
                            color: "#f4f1f8"
                            font.family: "Microsoft YaHei UI"
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                        Text {
                            width: parent.width
                            text: root.taskSubtitle
                            color: "#b9b4c0"
                            font.family: "Microsoft YaHei UI"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 1
                    color: "#24ffffff"
                }

                Row {
                    width: parent.width
                    Text {
                        text: root.phaseLabel
                        color: "#c8c2d0"
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 12
                    }
                    Text {
                        anchors.right: parent.right
                        text: root.formatTime(root.remainingSeconds)
                        color: "#ffffff"
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 22
                        font.weight: Font.DemiBold
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 5
                    radius: 3
                    color: "#2c2a31"
                    Rectangle {
                        width: parent.width * (root.totalSeconds > 0 ? Math.max(0, Math.min(1, (root.totalSeconds - root.remainingSeconds) / root.totalSeconds)) : 0)
                        height: parent.height
                        radius: parent.radius
                        color: root.taskType === "break" ? "#46cea3" : "#9c8cff"
                        Behavior on width { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
                    }
                }

                Text {
                    visible: root.environmentText.length > 0
                    width: parent.width
                    text: root.environmentText
                    color: "#9fdaff"
                    font.family: "Microsoft YaHei UI"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }

                Item { width: 1; height: 2 }

                Row {
                    width: parent.width
                    spacing: 9
                    Rectangle {
                        width: 162
                        height: 38
                        radius: 19
                        color: root.running ? "#423b78" : "#5a4f9f"
                        Text {
                            anchors.centerIn: parent
                            text: root.running ? "暂停" : "继续"
                            color: "white"
                            font.family: "Microsoft YaHei UI"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.running ? root.pauseRequested() : root.resumeRequested()
                        }
                    }
                    Rectangle {
                        width: 162
                        height: 38
                        radius: 19
                        color: "#4e252b"
                        Text {
                            anchors.centerIn: parent
                            text: "结束专注"
                            color: "#ffd9d4"
                            font.family: "Microsoft YaHei UI"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.cancelRequested()
                        }
                    }
                }
            }
        }

        Rectangle {
            id: guardBanner
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 14
            height: 38
            radius: 12
            color: "#ffe0ab"
            visible: root.guardVisible
            opacity: root.guardVisible ? 1 : 0
            transform: Translate { y: root.guardVisible ? 0 : 10 }
            Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            Text {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                verticalAlignment: Text.AlignVCenter
                text: root.guardMessage
                color: "#3d2700"
                font.family: "Microsoft YaHei UI"
                font.pixelSize: 11
                elide: Text.ElideRight
            }
        }

        Rectangle {
            anchors.centerIn: parent
            width: 220
            height: 44
            radius: 22
            color: root.exitCancelled ? "#4e252b" : "#2f6c5c"
            visible: root.finished
            opacity: root.finished ? 1 : 0
            Text {
                anchors.centerIn: parent
                text: root.exitCancelled ? "专注已结束" : "全部任务完成"
                color: "white"
                font.family: "Microsoft YaHei UI"
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
        }

        MouseArea {
            anchors.fill: parent
            z: -1
            onClicked: {
                if (!root.finished) root.expanded = !root.expanded
            }
        }
    }

    Timer {
        id: guardTimer
        interval: 3200
        onTriggered: root.guardVisible = false
    }

    SequentialAnimation {
        id: entrance
        ParallelAnimation {
            NumberAnimation { target: island; property: "opacity"; from: 0; to: 1; duration: 300; easing.type: Easing.OutCubic }
            NumberAnimation { target: island; property: "scale"; from: 0.82; to: 1; duration: 420; easing.type: Easing.OutBack }
        }
    }

    SequentialAnimation {
        id: exitAnimation
        PauseAnimation { duration: 1200 }
        ParallelAnimation {
            NumberAnimation { target: island; property: "opacity"; to: 0; duration: 220; easing.type: Easing.InQuad }
            NumberAnimation { target: island; property: "scale"; to: 0.9; duration: 250; easing.type: Easing.InQuad }
        }
        ScriptAction { script: root.exitFinished() }
    }
}
