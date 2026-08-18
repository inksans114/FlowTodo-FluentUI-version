import QtQuick

Rectangle {
    id: root
    width: 640
    height: 220
    color: "transparent"

    property string taskTitle: "准备开始"
    property string taskSubtitle: ""
    property string phaseLabel: "阶段 1/1"
    property string statusLabel: "专注中"
    property string taskType: "focus"
    property string themeName: "material"
    property string customAccent: ""
    property bool systemDark: false
    property string guardMessage: ""
    property int remainingSeconds: 0
    property int totalSeconds: 0
    property int taskRevision: 0
    property bool running: false
    property bool miniMode: false
    property bool guardVisible: false
    property bool finished: false
    property bool exitCancelled: false
    property bool lightingEffect: true
    property real islandScale: 1.0
    property real entranceScale: 0.82
    property real entranceOpacity: 0
    property real pageOpacity: 1
    property real flipOffset: 0
    property real guardContentOpacity: 0

    readonly property color cardColor: themeName === "cw1" ? (systemDark ? "#24242a" : "#f2f2f2")
        : themeName === "win10" ? (systemDark ? "#202020" : "#f3f3f3")
        : themeName === "default" ? (systemDark ? "#1e3038" : "#f6fbfd")
        : (systemDark ? "#282035" : "#fbf5ff")
    readonly property color secondaryCardColor: themeName === "cw1" ? (systemDark ? "#303038" : "#e4e4e8")
        : themeName === "win10" ? (systemDark ? "#292929" : "#e5e5e5")
        : themeName === "default" ? (systemDark ? "#253b45" : "#ecf8fc")
        : (systemDark ? "#342b43" : "#f7effb")
    readonly property color textColor: themeName === "cw1" || themeName === "win10" ? (systemDark ? "#f5f2f7" : "#202024")
        : themeName === "default" ? (systemDark ? "#d4eef8" : "#16475d")
        : (systemDark ? "#eadfff" : "#4f3d7b")
    readonly property color mutedColor: themeName === "cw1" || themeName === "win10" ? (systemDark ? "#aaa5b2" : "#65636b")
        : themeName === "default" ? (systemDark ? "#9dbecb" : "#5e7c89")
        : (systemDark ? "#baaccf" : "#8a7aa5")
    readonly property color accentColor: taskType === "break" ? "#46b98c"
        : customAccent.length ? customAccent
        : themeName === "win10" ? "#60cdff"
        : themeName === "default" ? "#4d92b4" : "#7054b8"
    readonly property int cardRadius: themeName === "win10" ? 6 : (themeName === "cw1" ? 18 : 31)

    signal pauseRequested()
    signal resumeRequested()
    signal cancelRequested()
    signal dragStarted()
    signal dragMoved(int deltaX, int deltaY)
    signal dragFinished()
    signal displayModeChanged(bool miniMode)
    signal exitFinished()

    function formatTime(value) {
        var seconds = Math.max(0, value)
        var minutes = Math.floor(seconds / 60)
        return ("0" + minutes).slice(-2) + ":" + ("0" + (seconds % 60)).slice(-2)
    }
    function enterIsland() { entrance.restart() }
    function exitIsland() { finished = true; exitAnimation.restart() }
    function showGuard() {
        guardExit.stop()
        if (!guardVisible) {
            guardVisible = true
            guardContentOpacity = 0
            guardEnter.restart()
        } else {
            guardContentOpacity = 1
        }
        guardTimer.restart()
    }
    function hideGuard() {
        guardEnter.stop()
        guardExit.restart()
    }
    function toggleDisplay() {
        if (!finished && !guardVisible) {
            miniMode = !miniMode
            displayModeChanged(miniMode)
        }
    }
    onTaskRevisionChanged: if (taskRevision > 0) pageFlip.restart()

    Item {
        id: islandDeck
        objectName: "islandDeck"
        anchors.centerIn: parent
        width: root.guardVisible ? 482 : (root.miniMode ? 224 : 482)
        height: root.guardVisible ? 72 : (root.miniMode ? 72 : 132)
        opacity: root.entranceOpacity * root.pageOpacity
        scale: root.entranceScale * root.islandScale
        Behavior on width { NumberAnimation { duration: 420; easing.type: Easing.OutBack } }
        Behavior on height { NumberAnimation { duration: 420; easing.type: Easing.OutBack } }
        transform: Translate { x: root.flipOffset }

        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 7
            anchors.leftMargin: 4
            radius: root.guardVisible || root.miniMode ? (root.themeName === "win10" ? 6 : 31) : root.cardRadius
            color: "#24000000"
            visible: root.lightingEffect
        }

        Row {
            id: fullCards
            anchors.centerIn: parent
            spacing: 12
            z: 1
            visible: !root.miniMode && !root.guardVisible
            opacity: visible ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

            Rectangle {
                width: 292; height: 132; radius: root.cardRadius
                color: root.cardColor
                border.width: root.themeName === "win10" ? 1 : 0
                border.color: "#55ffffff"

                Column {
                    anchors.fill: parent
                    anchors.leftMargin: 26; anchors.rightMargin: 26
                    anchors.topMargin: 18; anchors.bottomMargin: 15
                    spacing: 5
                    Text {
                        text: root.phaseLabel + "  ·  " + root.statusLabel
                        color: root.mutedColor; font.family: "Microsoft YaHei UI"
                        font.pixelSize: 13; font.weight: Font.DemiBold
                        elide: Text.ElideRight; width: parent.width
                    }
                    Text {
                        text: root.taskTitle; color: root.textColor
                        font.family: "Microsoft YaHei UI"; font.pixelSize: 22; font.weight: Font.DemiBold
                        elide: Text.ElideRight; width: parent.width
                    }
                    Text {
                        text: root.taskSubtitle; color: root.mutedColor
                        font.family: "Microsoft YaHei UI"; font.pixelSize: 12
                        elide: Text.ElideRight; width: parent.width
                    }
                }
                Row {
                    anchors.right: parent.right; anchors.rightMargin: 17
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 14
                    spacing: 8; z: 2
                    Rectangle {
                        width: 48; height: 26; radius: 13; color: root.accentColor
                        Text { anchors.centerIn: parent; text: root.running ? "暂停" : "继续"; color: "white"; font.family: "Microsoft YaHei UI"; font.pixelSize: 11 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.running ? root.pauseRequested() : root.resumeRequested() }
                    }
                    Rectangle {
                        width: 42; height: 26; radius: 13
                        color: root.themeName === "cw1" || root.themeName === "win10" ? "#53323a" : "#ffe4e2"
                        Text { anchors.centerIn: parent; text: "结束"; color: root.themeName === "cw1" || root.themeName === "win10" ? "#ffd9d4" : "#9e3030"; font.family: "Microsoft YaHei UI"; font.pixelSize: 11 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.cancelRequested() }
                    }
                }
            }

            Rectangle {
                width: 178; height: 132; radius: root.cardRadius; color: root.secondaryCardColor
                border.width: root.themeName === "win10" ? 1 : 0; border.color: "#55ffffff"
                Column {
                    anchors.centerIn: parent; spacing: 5
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "距离结束还有"; color: root.mutedColor; font.family: "Microsoft YaHei UI"; font.pixelSize: 13; font.weight: Font.DemiBold }
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: root.formatTime(root.remainingSeconds); color: root.textColor; font.family: "Microsoft YaHei UI"; font.pixelSize: 31; font.weight: Font.Bold }
                    Rectangle {
                        width: 88; height: 5; radius: 3; color: "#20000000"
                        Rectangle {
                            width: parent.width * (root.totalSeconds > 0 ? Math.max(0, Math.min(1, (root.totalSeconds - root.remainingSeconds) / root.totalSeconds)) : 0)
                            height: parent.height; radius: parent.radius; color: root.accentColor
                            Behavior on width { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
                        }
                    }
                }
            }
        }

        Rectangle {
            z: 1
            anchors.centerIn: parent
            width: 224; height: 72; radius: root.themeName === "win10" ? 6 : 31
            color: root.cardColor; visible: root.miniMode && !root.guardVisible; opacity: visible ? 1 : 0
            border.width: root.themeName === "win10" ? 1 : 0; border.color: "#55ffffff"
            Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            Canvas {
                id: progressRing
                width: 34; height: 34
                anchors.left: parent.left; anchors.leftMargin: 25; anchors.verticalCenter: parent.verticalCenter
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset(); ctx.lineWidth = 4; ctx.lineCap = "round"; ctx.strokeStyle = "#22000000"
                    ctx.beginPath(); ctx.arc(width / 2, height / 2, 13, 0, Math.PI * 2); ctx.stroke()
                    var progress = root.totalSeconds > 0 ? Math.max(0, Math.min(1, (root.totalSeconds - root.remainingSeconds) / root.totalSeconds)) : 0
                    ctx.strokeStyle = root.accentColor; ctx.beginPath(); ctx.arc(width / 2, height / 2, 13, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * progress); ctx.stroke()
                }
                Connections {
                    target: root
                    function onRemainingSecondsChanged() { progressRing.requestPaint() }
                    function onTotalSecondsChanged() { progressRing.requestPaint() }
                    function onAccentColorChanged() { progressRing.requestPaint() }
                }
            }
            Text {
                anchors.left: progressRing.right; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter
                width: 132
                text: root.formatTime(root.remainingSeconds); color: root.textColor
                font.family: "Microsoft YaHei UI"; font.pixelSize: 26; font.weight: Font.Bold
                horizontalAlignment: Text.AlignLeft
            }
        }

        Rectangle {
            z: 2
            anchors.fill: parent
            radius: root.themeName === "win10" ? 6 : 31
            color: root.cardColor
            visible: root.guardVisible
            border.width: root.themeName === "win10" ? 1 : 0
            border.color: "#55ffffff"

            Row {
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 26
                spacing: 14
                opacity: root.guardContentOpacity

                Rectangle {
                    width: 34
                    height: 34
                    radius: 17
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.accentColor
                    Item {
                        anchors.centerIn: parent
                        width: 5
                        height: 18
                        Rectangle {
                            anchors.top: parent.top
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 4
                            height: 12
                            radius: 2
                            color: "white"
                        }
                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 4
                            height: 4
                            radius: 2
                            color: "white"
                        }
                    }
                }
                Text {
                    width: parent.width - 48
                    height: parent.height - 18
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.guardMessage
                    color: root.textColor
                    font.family: "Microsoft YaHei UI"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.Wrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
            }
        }

        Rectangle {
            z: 3
            anchors.centerIn: parent; width: 190; height: 46; radius: 23
            color: root.exitCancelled ? "#a5414d" : root.accentColor
            visible: root.finished; opacity: root.finished ? 1 : 0
            Text { anchors.centerIn: parent; text: root.exitCancelled ? "专注已结束" : "全部任务完成"; color: "white"; font.family: "Microsoft YaHei UI"; font.pixelSize: 14; font.weight: Font.DemiBold }
        }
        MouseArea {
            id: dragArea
            anchors.fill: parent
            z: 0
            property real pressX: 0
            property real pressY: 0
            property bool dragged: false
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            onPressed: function(mouse) {
                pressX = mouse.x
                pressY = mouse.y
                dragged = false
                root.dragStarted()
            }
            onPositionChanged: function(mouse) {
                if (!pressed) return
                var deltaX = mouse.x - pressX
                var deltaY = mouse.y - pressY
                if (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3) dragged = true
                if (dragged) root.dragMoved(Math.round(deltaX), Math.round(deltaY))
            }
            onReleased: {
                root.dragFinished()
                if (!dragged) root.toggleDisplay()
            }
        }
    }

    Timer { id: guardTimer; interval: 3200; onTriggered: root.hideGuard() }
    NumberAnimation {
        id: guardEnter
        target: root
        property: "guardContentOpacity"
        from: 0
        to: 1
        duration: 240
        easing.type: Easing.OutCubic
    }
    SequentialAnimation {
        id: guardExit
        NumberAnimation {
            target: root
            property: "guardContentOpacity"
            to: 0
            duration: 150
            easing.type: Easing.InCubic
        }
        ScriptAction { script: root.guardVisible = false }
    }
    SequentialAnimation {
        id: entrance
        ParallelAnimation {
            NumberAnimation { target: root; property: "entranceOpacity"; to: 1; duration: 280; easing.type: Easing.OutCubic }
            NumberAnimation { target: root; property: "entranceScale"; to: 1; duration: 430; easing.type: Easing.OutBack }
        }
    }
    SequentialAnimation {
        id: pageFlip
        ParallelAnimation {
            NumberAnimation { target: root; property: "flipOffset"; to: -46; duration: 135; easing.type: Easing.InCubic }
            NumberAnimation { target: root; property: "pageOpacity"; to: 0.12; duration: 135; easing.type: Easing.InCubic }
        }
        ScriptAction { script: root.flipOffset = 46 }
        ParallelAnimation {
            NumberAnimation { target: root; property: "flipOffset"; to: 0; duration: 260; easing.type: Easing.OutBack }
            NumberAnimation { target: root; property: "pageOpacity"; to: 1; duration: 200; easing.type: Easing.OutCubic }
        }
    }
    SequentialAnimation {
        id: exitAnimation
        PauseAnimation { duration: 1100 }
        ParallelAnimation {
            NumberAnimation { target: root; property: "entranceOpacity"; to: 0; duration: 210; easing.type: Easing.InQuad }
            NumberAnimation { target: root; property: "entranceScale"; to: 0.9; duration: 240; easing.type: Easing.InQuad }
        }
        ScriptAction { script: root.exitFinished() }
    }
}
