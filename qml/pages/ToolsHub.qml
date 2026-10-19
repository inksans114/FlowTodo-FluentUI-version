import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("工具")
    wrapperWidth: 860
    horizontalPadding: 32
    contentSpacing: 16
    function open(name) {
        var item = page
        while (item && item.objectName !== "MainNavigationView") item = item.parent
        if (item) item.push(Qt.resolvedUrl(name))
    }
    Text { Layout.fillWidth: true; text: I18n.t("需要时再打开，日常先把眼前的一件事做好。"); typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap }
    Repeater {
        model: [
            {title: I18n.t("桌面小组件"), detail: I18n.t("在桌面查看和处理待办"), icon: "ic_fluent_apps_list_detail_20_regular", page: "WidgetHub.qml"},
            {title: I18n.t("桌面便签"), detail: I18n.t("随手记录，放在桌面上"), icon: "ic_fluent_note_20_regular", page: "NoteHub.qml"}
        ]
        delegate: Frame {
            required property var modelData
            Layout.fillWidth: true
            padding: 20
            contentItem: RowLayout {
                spacing: 16
                Icon { name: modelData.icon; size: 24; color: Theme.currentTheme.colors.primaryColor }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: modelData.title; typography: Typography.BodyStrong }
                    Text { Layout.fillWidth: true; text: modelData.detail; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap }
                }
                JourneyButton { text: I18n.t("打开"); onClicked: page.open(modelData.page) }
            }
        }
    }
}
