import QtQuick
import RinUI

// Local, resolution-independent illustrations of the four island styles.
Rectangle {
    id: root
    property string themeId: "material"
    readonly property color accent: themeId === "default" ? "#4d92b4" : themeId === "win10" ? "#0078d4" : themeId === "cw1" ? "#666979" : "#7054b8"
    color: themeId === "default" ? "#e6f3f7" : themeId === "win10" ? "#e8eef5" : themeId === "cw1" ? "#eaebee" : "#eee5f7"
    radius: 8
    Rectangle {
        anchors.centerIn: parent
        width: parent.width - 24
        height: 74
        radius: root.themeId === "win10" ? 4 : root.themeId === "cw1" ? 12 : 22
        color: root.themeId === "material" ? "#fbf5ff" : "#fafcfd"
        border.color: Qt.alpha(root.accent, 0.2)
        Rectangle {
            x: 12; y: 14; width: 24; height: 24
            radius: root.themeId === "win10" ? 4 : 12
            color: Qt.alpha(root.accent, 0.13)
            IconWidget { anchors.centerIn: parent; icon: "ic_fluent_timer_20_regular"; size: 16; color: root.accent }
        }
        Text { x: 44; y: 10; height: 14; text: "专注中"; font.pixelSize: 10; lineHeightMode: Text.ProportionalHeight; lineHeight: 1; color: root.accent }
        Text { x: 44; y: 27; height: 24; text: "24:38"; font.pixelSize: 18; lineHeightMode: Text.ProportionalHeight; lineHeight: 1; font.weight: Font.DemiBold; color: "#252735" }
        Rectangle { x: parent.width - 28; y: 23; width: 16; height: 16; radius: root.themeId === "win10" ? 2 : 8; color: root.accent
            Text { anchors.centerIn: parent; height: 14; verticalAlignment: Text.AlignVCenter; lineHeightMode: Text.ProportionalHeight; lineHeight: 1; text: "Ⅱ"; font.pixelSize: 10; color: "white" }
        }
        Rectangle { x: 12; y: 56; width: parent.width - 24; height: 3; radius: 2; color: Qt.alpha(root.accent, 0.15)
            Rectangle { width: parent.width * 0.62; height: parent.height; radius: 2; color: root.accent }
        }
    }
}
