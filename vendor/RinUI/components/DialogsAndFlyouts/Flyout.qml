import QtQuick 2.15
import QtQuick.Controls.Basic 2.15
import QtQuick.Layouts 2.15
import Qt5Compat.GraphicalEffects
import "../../themes"
import "../../components"

Popup {
    id: flyout
    property alias text: flyoutText.text  // 弹出文本内容
    property alias buttonBox: buttonLayout.data  // 按钮列表
    default property alias content: customContent.data  // 弹出内容

    position: Position.Top

    padding: 16

    contentItem: ColumnLayout {
        spacing: 0

        ColumnLayout {
            id: customContent
            spacing: 8
            Layout.fillWidth: true

            Text {
                id: flyoutText
                Layout.fillWidth: true
                typography: Typography.Body
                visible: text.length > 0
            }
        }

        Item {
            height: 16
            visible: buttonLayout.children.length > 0
        }

        RowLayout {
            Layout.fillWidth: true
            id: buttonLayout
            spacing: 8
        }
    }

    // 动画 / Animation //
    enter: Transition {
        ParallelAnimation {
            NumberAnimation {
                target: flyout
                property: "opacity"
                from: 0
                to: 1
                duration: Utils.appearanceSpeed
                easing.type: Easing.OutQuint
            }
            NumberAnimation {
                target: flyout
                property: "y"
                from: posY + (position === Position.Top ? 15 : position === Position.Bottom ? -15 : 0)
                to: posY
                duration: Utils.animationSpeedMiddle * 1.25
                easing.type: Easing.OutQuint
            }
            NumberAnimation {
                target: flyout
                property: "x"
                from: posX + (position === Position.Left ? 15 : position === Position.Right ? -15 : 0)
                to: posX
                duration: Utils.animationSpeedMiddle * 1.25
                easing.type: Easing.OutQuint
            }
        }
    }
    exit: Transition {
        ParallelAnimation {
            NumberAnimation {
                target: flyout
                property: "opacity"
                from: 1
                to: 0
                duration: Utils.animationSpeed
                easing.type: Easing.OutQuint
            }
        }
    }
}
