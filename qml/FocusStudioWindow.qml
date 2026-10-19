import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic as Basic

Window {
    id: studio
    objectName: "focusStudioWindow"
    title: "FlowTodo · 专注"
    width: 1280
    height: 800
    color: "#102822"
    flags: Qt.Window | Qt.FramelessWindowHint
    visible: false
    onClosing: function(event) { event.accepted = false; Backend.exitFocusStudio() }
    Shortcut { sequence: "Escape"; context: Qt.WindowShortcut; enabled: studio.visible; onActivated: Backend.exitFocusStudio() }
    Shortcut { sequence: "F11"; context: Qt.WindowShortcut; enabled: studio.visible; onActivated: studio.visibility === Window.FullScreen ? studio.showNormal() : studio.showFullScreen() }
    // Keeps the timer and exit controls accessible if WebEngine is unavailable.
    Column {
        anchors.centerIn: parent
        spacing: 22
        visible: true
        property var state: JSON.parse(Backend.focusStudioStateJson)
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: parent.state.goal; color: "#eff4ec"; font.pixelSize: 26 }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: String(Math.floor(Number(parent.state.remaining) / 60)).padStart(2, "0") + ":" + String(Number(parent.state.remaining) % 60).padStart(2, "0")
            color: "#eff4ec"; font.pixelSize: 84; font.weight: Font.Light
        }
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: Backend.focusWebAvailable ? "场景正在载入；计时保持运行" : "安静专注 · Esc 返回"; color: "#c0cfc0" }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter; spacing: 16
            Basic.Button { text: "暂停 / 继续"; onClicked: Backend.focusStudioAction(parent.parent.state.status === "paused" ? "resume" : "pause", "") }
            Basic.Button { text: "完成本轮"; onClicked: Backend.endStepFocus() }
            Basic.Button { text: "返回应用"; onClicked: Backend.exitFocusStudio() }
        }
    }
}
