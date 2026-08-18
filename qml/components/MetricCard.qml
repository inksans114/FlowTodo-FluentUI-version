import QtQuick
import QtQuick.Layouts
import RinUI

Frame {
    id: root
    property string label: ""
    property string value: "0"
    property string iconName: "ic_fluent_info_20_regular"
    property color accent: Theme.currentTheme.colors.primaryColor

    Layout.fillWidth: true
    Layout.preferredHeight: 104
    leftPadding: 18
    rightPadding: 18
    topPadding: 16
    bottomPadding: 16

    RowLayout {
        anchors.fill: parent
        spacing: 14
        Rectangle {
            width: 42
            height: 42
            radius: 8
            color: Qt.alpha(root.accent, 0.14)
            IconWidget {
                anchors.centerIn: parent
                icon: root.iconName
                size: 22
                color: root.accent
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Text {
                text: root.value
                typography: Typography.Subtitle
                color: Theme.currentTheme.colors.textColor
            }
            Text {
                text: root.label
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
            }
        }
    }
}
