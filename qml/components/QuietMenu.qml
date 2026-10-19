import QtQuick
import QtQuick.Controls.Basic as Basic
import RinUI

Basic.Menu {
    width: 200
    x: parent ? parent.width - width : 0
    y: parent ? parent.height + 6 : 0
    padding: 6
    delegate: MenuItem {}
    background: Rectangle {
        radius: Theme.currentTheme.appearance.windowRadius
        color: Theme.currentTheme.colors.backgroundAcrylicColor
        border.color: Theme.currentTheme.colors.flyoutBorderColor
    }
}
