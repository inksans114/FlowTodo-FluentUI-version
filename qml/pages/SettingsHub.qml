import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "系统设置"
    wrapperWidth: 880
    horizontalPadding: 36
    contentSpacing: 8
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function open(name) { var router = nav(); if (router) router.push(Qt.resolvedUrl(name)) }

    Text { Layout.fillWidth: true
                text: "把外观、专注环境和服务配置分开管理。"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
    ColumnLayout {
        Layout.fillWidth: true
        Layout.topMargin: 10
        spacing: 4
        Repeater {
            model: [
                {title: "应用外观", detail: "明暗模式、窗口材质和纯色主题", icon: "ic_fluent_paint_brush_20_regular", page: "AppAppearanceSettings.qml"},
                {title: "灵动岛", detail: "主题、透明度、缩放和显示位置", icon: "ic_fluent_timer_20_regular", page: "IslandSettings.qml"},
                {title: "桌面小组件", detail: "透明度、窗口层级、锁定和尺寸", icon: "ic_fluent_apps_list_detail_20_regular", page: "WidgetSettings.qml"},
                {title: "AI 服务", detail: "OpenAI 兼容接口、模型、密钥和生成参数", icon: "ic_fluent_cloud_20_regular", page: "AiSettings.qml"},
                {title: "应用与数据", detail: "默认专注时长、开机启动和数据目录", icon: "ic_fluent_settings_20_regular", page: "AppSettings.qml"},
                {title: "应用拦截", detail: "选择专注期间仍允许使用的 Windows 应用", icon: "ic_fluent_shield_checkmark_20_regular", page: "FocusGuardApps.qml"}
            ]
            delegate: Frame {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 82
                leftPadding: 14
                rightPadding: 12
                topPadding: 12
                bottomPadding: 12
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

