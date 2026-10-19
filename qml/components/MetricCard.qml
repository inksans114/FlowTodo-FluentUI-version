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
    Layout.preferredWidth: 0
    Layout.minimumWidth: 0
    Layout.preferredHeight: 112
    Layout.minimumHeight: 112
    leftPadding: 20
    rightPadding: 20
    topPadding: 18
    bottomPadding: 18

    contentItem: RowLayout {
        spacing: 16
        Rectangle {
            Layout.preferredWidth: 44
            Layout.preferredHeight: 44
            radius: 12
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
            Layout.preferredWidth: 0
            Layout.minimumWidth: 0
            spacing: 2
            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.value
                typography: Typography.Subtitle
                color: Theme.currentTheme.colors.textColor
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.label
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                elide: Text.ElideRight
            }
        }
    }
}
