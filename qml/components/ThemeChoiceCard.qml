import QtQuick
import RinUI

Item {
    id: root
    property string title: ""
    property string themeId: "material"
    property url preview
    property bool selected: false
    signal chosen(string themeId)

    width: 190
    height: 132

    Rectangle {
        anchors.fill: parent
        radius: 8
        clip: true
        color: Theme.currentTheme.colors.controlColor
        border.width: root.selected ? 3 : 1
        border.color: root.selected
            ? Theme.currentTheme.colors.primaryColor
            : Theme.currentTheme.colors.cardBorderColor

        Image {
            anchors.fill: parent
            anchors.margins: root.selected ? 3 : 1
            source: root.preview
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: true
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 42
            color: "#b0000000"
            Text {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                text: root.title
                typography: Typography.BodyStrong
                color: "white"
                elide: Text.ElideRight
            }
        }
    }

    HoverHandler { id: hover }
    TapHandler { onTapped: root.chosen(root.themeId) }
    scale: hover.hovered ? 1.015 : 1
    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
}
