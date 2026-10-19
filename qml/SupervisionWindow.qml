import QtQuick
import QtQuick.Window
import "components"

Window {
    id: window
    objectName: "supervisionWindow"
    title: "FlowTodo · 监督模式"
    visible: false
    property bool compact: false
    width: 430; height: 420
    minimumWidth: compact ? 390 : 800
    minimumHeight: compact ? 400 : 600
    color: "#13251f"
    flags: compact ? Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint : Qt.Window
    function updateCompactHeight() {
        if (!compact || !visible) return
        var alert = Boolean(JSON.parse(Backend.supervision.stateJson).alert)
        height = Math.min(screen.height - 32, panel.showCalibration ? (alert ? 800 : 650) : alert ? 580 : 420)
        y = Math.max(screen.virtualY + 16, Math.min(y, screen.virtualY + screen.height - height - 16))
    }
    function present(view) {
        hide()
        compact = view === "compact"
        if (compact) {
            showNormal()
            width = 430; height = JSON.parse(Backend.supervision.stateJson).alert ? 580 : 420
            updateCompactHeight()
            x = screen.virtualX + screen.width - width - 24
            y = screen.virtualY + Math.max(24, (screen.height - height) / 2)
        } else showFullScreen()
        raise(); requestActivate()
    }
    SupervisionPanel { id: panel; anchors.fill: parent; compact: window.compact; hostWindow: window; onShowCalibrationChanged: window.updateCompactHeight() }
    Connections {
        target: Backend.supervision
        function onChanged() {
            window.updateCompactHeight()
        }
    }
    Shortcut { sequence: "Escape"; onActivated: { if (!window.compact) Backend.presentSupervision("compact"); else Backend.stopSupervision() } }
    Shortcut { sequence: "F11"; onActivated: Backend.presentSupervision(window.compact ? "full" : "compact") }
    onClosing: function(close) { close.accepted = false; Backend.stopSupervision() }
}
