import QtQuick
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    objectName: "AboutPage"
    title: ""
    wrapperWidth: 980
    horizontalPadding: 36
    contentSpacing: 20
    RowLayout {
        Layout.fillWidth: true
        SettingsBack {}
        Text { text: "/  " + I18n.t("关于 FlowTodo"); font.pixelSize: 12; color: Theme.currentTheme.colors.textSecondaryColor }
        Item { Layout.fillWidth: true }
    }
    UpdatePanel { Layout.fillWidth: true; aboutMode: true }
}
