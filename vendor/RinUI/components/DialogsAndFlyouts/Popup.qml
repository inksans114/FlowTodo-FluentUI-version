import QtQuick 2.15
import QtQuick.Controls.Basic 2.15
import QtQuick.Layouts 2.15
import QtQuick.Window 2.15
import Qt5Compat.GraphicalEffects
import "../../themes"
import "../../components"

Popup {
    id: popup
    property int position: Position.None
    property Item anchorItem: parent
    property real posX: {
        if (typeof x === "number" && x !== 0 && position=== Position.None)
            return x
        switch (position) {
            case Position.Top:
            case Position.Bottom:
                return (anchorItem ? (anchorItem.width - popup.width) / 2 : 0)
            case Position.Left:
                return -(popup.width + 5)
            case Position.Right:
                return (anchorItem ? anchorItem.width + 5 : 0)
            default:
                return (anchorItem ? (anchorItem.width - popup.width) / 2 : 0)
        }
    }

    property real posY: {
        if (typeof y === "number" && y !== 0 && position=== Position.None)
            return y
        switch (position) {
            case Position.Top:
                return -(popup.height + 5)
            case Position.Bottom:
                return (anchorItem ? anchorItem.height + 5 : 0)
            case Position.Left:
            case Position.Center:
            case Position.Right:
                return (anchorItem ? (anchorItem.height - popup.height) / 2 : 0)
            default:
                return -(popup.height + 5)
        }
    }

    onVisibleChanged: {  // 自动调整位置
        if (visible) {
            console.log("visible changed")
            Qt.callLater(function() {
                if (
                    (position === Position.None || position === undefined) &&
                    (popup.x === 0 || popup.x === undefined) &&
                    (popup.y === 0 || popup.y === undefined)
                ) {
                    console.log("auto position")
                    popup.autoPosition()
                }
            })
        }
    }

    function autoPosition() {
        if (!anchorItem) return

        var btnGlobal = anchorItem.mapToGlobal(0, 0)
        var btnTop = btnGlobal.y
        var btnBottom = btnTop + anchorItem.height
        var btnLeft = btnGlobal.x
        var owningWindow = anchorItem.Window.window
        var boundsLeft = owningWindow ? owningWindow.x : 0
        var boundsTop = owningWindow ? owningWindow.y : 0
        var boundsRight = owningWindow ? owningWindow.x + owningWindow.width
            : (Qt.application.primaryScreen ? Qt.application.primaryScreen.width : 1920)
        var boundsBottom = owningWindow ? owningWindow.y + owningWindow.height
            : (Qt.application.primaryScreen ? Qt.application.primaryScreen.height : 1080)
        var margin = 12
        var gap = 5
        var popupH = Math.max(popup.implicitHeight, popup.height)
        var popupW = Math.max(popup.implicitWidth, popup.width)
        var belowY = btnBottom + gap
        var aboveY = btnTop - popupH - gap
        var minY = boundsTop + margin
        var maxY = Math.max(minY, boundsBottom - popupH - margin)
        var desiredY = belowY + popupH <= boundsBottom - margin
            ? belowY
            : (aboveY >= minY ? aboveY : Math.max(minY, Math.min(belowY, maxY)))
        var centeredX = btnLeft + (anchorItem.width - popupW) / 2
        var minX = boundsLeft + margin
        var maxX = Math.max(minX, boundsRight - popupW - margin)
        var desiredX = Math.max(minX, Math.min(centeredX, maxX))

        popup.position = Position.None
        popup.x = desiredX - btnLeft
        popup.y = desiredY - btnTop
    }


    Overlay.modal: Rectangle {
        color: Theme.currentTheme.colors.backgroundSmokeColor
    }

    background: Rectangle {
        id: background
        anchors.fill: parent
        y: -6

        radius: Theme.currentTheme.appearance.windowRadius
        color: Theme.currentTheme.colors.backgroundAcrylicColor
        border.color: Theme.currentTheme.colors.flyoutBorderColor

        Behavior on color {
            ColorAnimation {
                duration: Utils.appearanceSpeed
                easing.type: Easing.OutQuart
            }
        }

        layer.enabled: true
        layer.effect: Shadow {
            style: "flyout"
            source: background
        }
    }

    // 动画 / Animation //
    enter: Transition {
        ParallelAnimation {
            NumberAnimation {
                target: popup
                property: "opacity"
                from: 0
                to: 1
                duration: Utils.appearanceSpeed
                easing.type: Easing.OutQuint
            }
            NumberAnimation {
                target: popup
                property: "y"
                from: posY + (position !== Position.Center
                    ? (position === Position.Top ? 15 : position === Position.Bottom ? -15 : 0) : 0)
                to: posY
                duration: Utils.animationSpeedMiddle * 1.25
                easing.type: Easing.OutQuint
            }
            NumberAnimation {
                target: popup
                property: "x"
                from: posX + (position !== Position.Center
                    ? (position === Position.Left ? 15 : position === Position.Right ? -15 : 0) : 0)
                to: posX
                duration: Utils.animationSpeedMiddle * 1.25
                easing.type: Easing.OutQuint
            }
        }
    }
    exit: Transition {
        ParallelAnimation {
            NumberAnimation {
                target: popup
                property: "opacity"
                from: 1
                to: 0
                duration: Utils.animationSpeed
                easing.type: Easing.OutQuint
            }
        }
    }
}
