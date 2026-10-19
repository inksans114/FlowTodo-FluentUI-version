import QtQuick
import RinUI

QtObject {
    readonly property int pageWidth: 1040
    readonly property int pagePadding: 32
    readonly property int sectionGap: 20
    readonly property int cardGap: 12
    readonly property int cardPadding: 20
    readonly property int cardRadius: Theme.currentTheme.appearance.cardRadius
    readonly property int compactBreakpoint: 780
    readonly property int wideBreakpoint: 1000
    readonly property color mutedText: Theme.currentTheme.colors.textSecondaryColor
    readonly property color accent: Theme.currentTheme.colors.primaryColor
}
