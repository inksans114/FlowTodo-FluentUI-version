import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import RinUI
import "../i18n"

ToolButton {
    id: control
    property string helpText: ""
    objectName: "inlineHelp"
    icon.name: "ic_fluent_question_circle_20_regular"
    Accessible.name: I18n.t("使用说明")
    onClicked: explanation.open()
    Basic.ToolTip {
        parent: control
        visible: control.hovered && !explanation.visible
        delay: 500
        timeout: 10000
        width: 300
        contentItem: Text { text: control.helpText; wrapMode: Text.Wrap; typography: Typography.Caption }
        background: Rectangle { color: Theme.currentTheme.colors.backgroundAcrylicColor; radius: 8; border.color: Theme.currentTheme.colors.controlBorderColor }
    }
    Popup {
        id: explanation
        objectName: "inlineHelpPopup"
        x: control.width - width
        y: control.height + 6
        width: 300
        padding: 16
        transformOrigin: Item.TopRight
        enter: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Backend.systemMotionEnabled ? 160 : 0 }
                NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: Backend.systemMotionEnabled ? 180 : 0; easing.type: Easing.OutCubic }
            }
        }
        exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Backend.systemMotionEnabled ? 100 : 0 } }
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        contentItem: Text { text: control.helpText; wrapMode: Text.Wrap; typography: Typography.Body }
        background: Rectangle { color: Theme.currentTheme.colors.backgroundAcrylicColor; radius: Theme.currentTheme.appearance.cardRadius; border.color: Theme.currentTheme.colors.controlBorderColor }
    }
}
