import QtQuick
import RinUI
QtObject {
    property bool customAllowed: true
    readonly property var personalization: { Backend.accountJson; try { return JSON.parse(Backend.appearanceJson) } catch(e) { return ({}) } }
    readonly property bool personalized: customAllowed && personalization.active
    readonly property var palette: personalized ? personalization[dark ? "dark" : "light"] : ({})
    readonly property bool dark: Theme.currentTheme.isDark
    readonly property color surface: palette.surface || (dark ? "#292b30" : "#ffffff")
    readonly property color inset: palette.control || (dark ? "#222429" : "#f5f7fa")
    readonly property color list: palette.list || surface
    readonly property color stroke: dark ? "#41444c" : "#e2e7ef"
    readonly property color ink: palette.ink || (dark ? "#f3f4f6" : "#202a3d")
    readonly property color muted: palette.muted || (dark ? "#b7bfcc" : "#58657a")
    readonly property color accent: palette.accent || Theme.currentTheme.colors.primaryColor
    readonly property color tint: dark ? "#303948" : "#eef3fc"
    readonly property int radius: 18
}
