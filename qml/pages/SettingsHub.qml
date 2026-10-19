import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("系统设置")
    wrapperWidth: 960
    horizontalPadding: 32
    contentSpacing: 16
    LayoutTokens { id: ui }
    readonly property bool compactLayout: width - horizontalPadding * 2 < ui.compactBreakpoint
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function open(name) { var router = nav(); if (router) router.push(Qt.resolvedUrl(name)) }

    Text { Layout.fillWidth: true
                text: I18n.t("把外观、专注环境和服务配置分开管理。")
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
    GridLayout {
        Layout.fillWidth: true
        Layout.topMargin: 8
        columns: page.compactLayout ? 1 : 2
        columnSpacing: ui.cardGap
        rowSpacing: ui.cardGap
        Repeater {
            model: [
                {title: I18n.t("应用外观"), detail: I18n.t("明暗模式、窗口材质和纯色主题"), icon: "ic_fluent_paint_brush_20_regular", page: "AppAppearanceSettings.qml"},
                {title: I18n.t("灵动岛"), detail: I18n.t("主题、透明度、缩放和显示位置"), icon: "ic_fluent_timer_20_regular", page: "IslandSettings.qml"},
                {title: I18n.t("桌面小组件"), detail: I18n.t("透明度、窗口层级、锁定和尺寸"), icon: "ic_fluent_apps_list_detail_20_regular", page: "WidgetSettings.qml"},
                {title: I18n.t("桌面便签"), detail: I18n.t("纸片、折叠胶囊和边缘叠放"), icon: "ic_fluent_note_20_regular", page: "NoteSettings.qml"},
                {title: I18n.t("AI 服务与偏好"), detail: I18n.t("服务连接、语音输入和适合你的专注方式"), icon: "ic_fluent_cloud_20_regular", page: "AiSettings.qml"},
                {title: I18n.t("应用与数据"), detail: I18n.t("默认专注时长、开机启动和数据目录"), icon: "ic_fluent_settings_20_regular", page: "AppSettings.qml"},
                {title: I18n.t("应用拦截"), detail: I18n.t("选择专注期间仍允许使用的 Windows 应用"), icon: "ic_fluent_shield_checkmark_20_regular", page: "FocusGuardApps.qml"}
            ]
            delegate: Frame {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 98
                leftPadding: 18
                rightPadding: 16
                topPadding: 16
                bottomPadding: 16
                RowLayout {
                    anchors.fill: parent
                    spacing: 12
                    Rectangle { width: 40
                height: 40
                radius: 7
                color: Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.12)
                Icon { anchors.centerIn: parent
                name: modelData.icon
                size: 21
                color: Theme.currentTheme.colors.primaryColor } }
                    ColumnLayout { Layout.fillWidth: true
                spacing: 2
                Text { text: modelData.title
                typography: Typography.BodyStrong }
                Text { Layout.fillWidth: true
                text: modelData.detail
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                elide: Text.ElideRight } }
                    Icon { name: "ic_fluent_chevron_right_20_regular"
                size: 18
                color: Theme.currentTheme.colors.textSecondaryColor }
                }
                MouseArea { anchors.fill: parent
                onClicked: page.open(modelData.page) }
            }
        }
    }
}
