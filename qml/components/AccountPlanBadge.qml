import QtQuick
import QtQuick.Layouts
import RinUI
Rectangle {
    id: badge
    property string plan: "free"
    readonly property string normalized: plan.toLowerCase()
    readonly property bool dark: Theme.currentTheme.isDark
    readonly property color foreground: normalized === "standard" ? (dark ? "#ffd98a" : "#80530c") : normalized === "lite" ? (dark ? "#a9cdff" : "#1858a5") : (dark ? "#c0c8d4" : "#58657a")
    implicitWidth: content.implicitWidth + 20; implicitHeight: 28; radius: 14
    color: normalized === "standard" ? (dark ? "#453824" : "#fff3d9") : normalized === "lite" ? (dark ? "#253e5c" : "#eaf3ff") : (dark ? "#343840" : "#f0f3f7")
    border.color: Qt.alpha(foreground,0.24)
    Accessible.name: "账号类型 " + label.text
    Row { id: content; anchors.centerIn: parent; spacing: 5; height: 20
        Icon { anchors.verticalCenter: parent.verticalCenter; visible: badge.normalized !== "free"; name: badge.normalized === "standard" ? "ic_fluent_star_20_regular" : "ic_fluent_sparkle_20_regular"; size: 13; color: badge.foreground }
        Text { id: label; height: parent.height; verticalAlignment: Text.AlignVCenter; lineHeightMode: Text.ProportionalHeight; lineHeight: 1; text: badge.normalized === "standard" ? "Standard" : badge.normalized === "lite" ? "Lite" : "Free"; font.pixelSize: 11; font.weight: Font.DemiBold; color: badge.foreground }
    }
}
