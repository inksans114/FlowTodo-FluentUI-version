import QtQuick
import QtQuick.Controls.Basic as Basic
import RinUI

Basic.SpinBox {
    id: control
    editable: true
    implicitWidth: 140
    implicitHeight: 34
    leftPadding: 36
    rightPadding: 36
    up.indicator: Rectangle {
        x: control.width - width
        width: 32; height: control.height; radius: 4
        color: control.up.pressed ? Theme.currentTheme.colors.controlSecondaryColor : Theme.currentTheme.colors.controlColor
        border.color: Theme.currentTheme.colors.controlBorderColor
        Text { anchors.centerIn: parent; text: "+"; typography: Typography.BodyStrong }
    }
    down.indicator: Rectangle {
        width: 32; height: control.height; radius: 4
        color: control.down.pressed ? Theme.currentTheme.colors.controlSecondaryColor : Theme.currentTheme.colors.controlColor
        border.color: Theme.currentTheme.colors.controlBorderColor
        Text { anchors.centerIn: parent; text: "−"; typography: Typography.BodyStrong }
    }
    background: JourneyControlSurface { control: parent; inputControl: true }
    contentItem: TextInput {
        z: 2
        text: control.textFromValue(control.value, control.locale)
        font.pixelSize: Theme.currentTheme.typography.bodySize
        color: Theme.currentTheme.colors.textColor
        selectionColor: Theme.currentTheme.colors.primaryColor
        selectedTextColor: Theme.currentTheme.colors.textOnAccentColor
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Qt.AlignVCenter
        validator: control.validator
        inputMethodHints: Qt.ImhDigitsOnly
        readOnly: !control.editable
        selectByMouse: true
    }
}
