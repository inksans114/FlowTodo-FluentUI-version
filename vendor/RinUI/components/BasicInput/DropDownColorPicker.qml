import QtQuick 2.15
import QtQuick.Controls.Basic 2.15
import QtQuick.Layouts 2.15
import Qt5Compat.GraphicalEffects
import "../../themes"
import "../../components"

Button {
    id: root
    // 属性 alias，用法同 ColorPicker
    property alias color: picker.color

    property alias hue: picker.hue
    property alias saturation: picker.saturation
    property alias value: picker.value
    property alias alpha: picker.alpha

    property alias ringMode: picker.ringMode
    property alias collapsed: picker.collapsed

    property alias moreVisible: picker.moreVisible
    property alias colorSliderVisible: picker.colorSliderVisible
    property alias colorChannelInputVisible: picker.colorChannelInputVisible
    property alias hexInputVisible: picker.hexInputVisible
    property alias alphaSliderVisible: picker.alphaSliderVisible
    property alias alphaInputVisible: picker.alphaInputVisible
    property alias alphaEnabled: picker.alphaEnabled
    // 位置
    property alias position: flyout.position

    // UI
    property bool textVisible: false
    property bool hexText: false
    readonly property int checkerboardCellSize: 4

    text: hexText ? picker.color.toString().toUpperCase() : picker.colorName

    implicitWidth: Math.max(row.implicitWidth + 20, 48)
    contentItem: Item {
        clip: true
        anchors.fill: parent

        Row {
            id: row
            spacing: 8
            anchors.centerIn: parent
            // Rectangle {
            //     width: 32
            //     height: 22
            //     radius: Theme.currentTheme.appearance.smallRadius
            // }
            Item {
                id: preview
                width: 42
                height: 28

                Canvas {
                    anchors.fill: parent
                    property int cellSize: checkerboardCellSize // 固定格子大小

                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)

                        var rows = Math.ceil(height / cellSize)
                        var cols = Math.ceil(width / cellSize)

                        for (var i = 0; i < rows; i++) {
                            for (var j = 0; j < cols; j++) {
                                ctx.fillStyle = ((i + j) % 2 === 0)
                                    ? Qt.rgba(1, 1, 1, 0)
                                    : Qt.rgba(0.5, 0.5, 0.5, 0.25)
                                ctx.fillRect(j * cellSize, i * cellSize, cellSize, cellSize)
                            }
                        }
                    }
                }
                Rectangle {
                    anchors.fill: parent; color: picker.color; radius: Theme.currentTheme.appearance.buttonRadius
                }
                Rectangle {
                    anchors.fill: parent; color: "transparent"; border.width: 2; border.color: Colors.proxy.dividerBorderColor; radius: Theme.currentTheme.appearance.buttonRadius
                }
                layer.enabled: true
                layer.effect: OpacityMask { maskSource: Rectangle { width: preview.width; height: preview.height; radius: Theme.currentTheme.appearance.smallRadius } }

                opacity: enabled ? 1 : 0.5
            }

            Text {
                id: text
                visible: textVisible
                typography: Typography.Body
                text: root.text
                color: highlighted ? flat ? Theme.currentTheme.colors.textAccentColor :
                    Theme.currentTheme.colors.textOnAccentColor : Theme.currentTheme.colors.textColor
            }
            // 后缀图标
            IconWidget {
                id: suffixIcon
                size: 12
                height: parent.height
                icon: "ic_fluent_chevron_down_20_regular"
                color: Theme.currentTheme.colors.textSecondaryColor
            }
        }
    }

    Flyout {
        id: flyout
        position: Position.None
        ColorPicker {
            id: picker
        }
    }

    Connections {
        target: picker
        function onCollapsedChanged() {
            if (flyout.visible)
                Qt.callLater(function() { flyout.autoPosition() })
        }
    }

    onClicked: {
        flyout.position = Position.None
        flyout.autoPosition()
        flyout.open()
    }
}
