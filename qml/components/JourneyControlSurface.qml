import QtQuick
import RinUI

// Draw native rounded surfaces directly; keep controls readable with software
// rendering and avoid a shader mask on simple rectangles at fractional DPI.
Rectangle {
    id: surface
    property var control
    property bool inputControl: false
    StudioTokens { id: customLook }
    readonly property bool accent: !inputControl && Boolean(control.highlighted)
    readonly property bool subtle: !inputControl && Boolean(control.flat)
    radius: Theme.currentTheme.appearance.buttonRadius
    color: accent ? Theme.currentTheme.colors.primaryColor
        : subtle ? (control.hovered ? Theme.currentTheme.colors.subtleSecondaryColor : "transparent")
        : inputControl && control.activeFocus ? Theme.currentTheme.colors.controlInputActiveColor
        : customLook.personalized ? customLook.inset : control.hovered ? Theme.currentTheme.colors.controlSecondaryColor : Theme.currentTheme.colors.controlColor
    border.width: subtle ? 0 : 1
    border.color: accent ? Theme.currentTheme.colors.primaryColor : Theme.currentTheme.colors.controlBorderColor
    opacity: control.enabled ? 1 : 0.5
    Rectangle {
        visible: surface.inputControl
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 1
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(0, parent.width - 2)
        height: surface.control.activeFocus ? 2 : 1
        radius: 1
        color: surface.control.activeFocus ? Theme.currentTheme.colors.primaryColor : Theme.currentTheme.colors.textControlBorderColor
    }
}
