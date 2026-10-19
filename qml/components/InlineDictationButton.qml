import QtQuick
import QtQuick.Controls
import RinUI
import "../i18n"

Button {
    id: root
    property Item inputTarget
    property string idleText: ""
    property bool requesting: false
    property bool expanded: false
    property bool motionEnabled: Backend.systemMotionEnabled
    readonly property bool active: requesting || expanded
    implicitWidth: active ? 156 : idleText.length ? 94 : 44
    implicitHeight: 44
    padding: 12
    focusPolicy: Qt.NoFocus
    clip: true
    scale: down ? 0.96 : 1
    Behavior on scale { enabled: root.motionEnabled; NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
    Accessible.name: active ? I18n.t("返回键盘输入") : I18n.t("语音输入")
    Accessible.description: I18n.t("在当前输入框使用 Windows 听写")
    Accessible.pressed: active
    ToolTip.text: active ? I18n.t("返回键盘输入") : I18n.t("语音输入")
    ToolTip.visible: hovered && !active
    StudioTokens { id: look }

    function begin() {
        if (!inputTarget) return
        inputTarget.forceActiveFocus()
        requesting = true
        if (!Backend.openSystemDictation(inputTarget)) requesting = false
    }
    function finish() {
        var wasActive = active
        requesting = false
        expanded = false
        if (wasActive && inputTarget) {
            inputTarget.forceActiveFocus()
            Backend.endSystemDictation(inputTarget)
        }
    }
    onClicked: active ? finish() : begin()
    onVisibleChanged: if (!visible && active) finish()
    Component.onDestruction: if (active) Backend.endSystemDictation(inputTarget)
    Connections {
        target: Backend
        function onSystemDictationResult(editor, opened) {
            if (editor !== root.inputTarget || !root.requesting) return
            root.expanded = opened
            root.requesting = false
        }
    }
    Shortcut { sequence: "Escape"; enabled: root.active && root.visible; onActivated: root.finish() }
    Behavior on implicitWidth { enabled: root.motionEnabled; NumberAnimation { duration: root.active ? 220 : 160; easing.type: Easing.OutCubic } }

    background: Rectangle {
        radius: 8
        color: root.active || root.down ? look.tint : root.hovered ? look.inset : look.surface
        border.color: root.active ? look.accent : look.stroke
        Behavior on color { enabled: root.motionEnabled; ColorAnimation { duration: 120 } }
    }
    contentItem: Item {
        Icon { id: microphone; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; name: "ic_fluent_mic_20_regular"; size: 20; color: root.active ? look.accent : look.ink }
        Text { anchors.left: microphone.right; anchors.leftMargin: 9; anchors.verticalCenter: parent.verticalCenter; text: root.idleText; opacity: root.active ? 0 : 1; color: look.ink; font.pixelSize: 13; Behavior on opacity { enabled: root.motionEnabled; NumberAnimation { duration: 110 } } }
        Item {
            id: wave
            objectName: "inlineDictationWave"
            anchors.left: microphone.right
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            width: 40; height: 24
            opacity: root.expanded ? 1 : 0
            // Activity indicator; Windows owns audio and recognition. These
            // bars deliberately do not claim to display microphone levels.
            Behavior on opacity { enabled: root.motionEnabled; NumberAnimation { duration: 140 } }
            Repeater {
                model: 5
                Rectangle {
                    required property int index
                    objectName: "inlineWaveBar_" + index
                    property real amplitude: 0.35
                    width: 3; height: 24; radius: 1.5
                    x: index * 7
                    anchors.verticalCenter: parent.verticalCenter
                    color: look.accent
                    transform: Scale { origin.x: 1.5; origin.y: 12; yScale: root.motionEnabled ? amplitude : 0.3 + (2 - Math.abs(2 - index)) * 0.16 }
                    SequentialAnimation on amplitude {
                        running: root.expanded && root.visible && root.motionEnabled
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.3 + (index % 4) * 0.18; duration: 320 + index * 35; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.18 + ((index + 2) % 3) * 0.12; duration: 380 + index * 25; easing.type: Easing.InOutSine }
                    }
                }
            }
        }
        Icon { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; name: "ic_fluent_dismiss_20_regular"; size: 16; color: look.ink; opacity: root.active ? 1 : 0 }
    }
}
