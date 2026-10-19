import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"
import "../components"

FluentPage {
    id: page
    title: I18n.t("灵动岛")
    wrapperWidth: 760
    horizontalPadding: 36
    contentSpacing: 12
    property bool loading: true
    property string selectedTheme: "material"
    property var islandThemes: [
        { id: "default", label: I18n.t("默认") },
        { id: "cw1", label: I18n.t("远古版") },
        { id: "win10", label: "Windows 10 Fluent2" },
        { id: "material", label: "Material You MD3" }
    ]
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { loading = true; selectedTheme = String(Backend.getSetting("islandTheme", "material")); opacityControl.value = Number(Backend.getSetting("islandOpacity", 1)); scaleControl.value = Number(Backend.getSetting("islandScale", 1)); anchor.currentIndex = ["top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right"].indexOf(String(Backend.getSetting("islandAnchor", "top_center"))); if (anchor.currentIndex < 0) anchor.currentIndex = 1; lighting.checked = Boolean(Backend.getSetting("islandLightingEffect", true)); loading = false }
    function selectTheme(themeId) {
        selectedTheme = themeId
        if (!loading) Backend.setSetting("islandTheme", themeId)
    }
    Component.onCompleted: load()
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: I18n.t("返回系统设置")
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { text: I18n.t("返回系统设置")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        contentItem: ColumnLayout {
                spacing: 14
            Text { text: I18n.t("灵动岛主题"); typography: Typography.BodyStrong }
            GridLayout {
                Layout.fillWidth: true
                columns: width >= 700 ? 4 : width >= 340 ? 2 : 1
                uniformCellWidths: true
                columnSpacing: 12
                rowSpacing: 12
                Repeater {
                    model: page.islandThemes
                    delegate: Button {
                        required property var modelData
                        objectName: "themePreview_" + modelData.id
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: 158
                        padding: 6
                        onClicked: page.selectTheme(modelData.id)
                        background: Rectangle {
                            radius: Theme.currentTheme.appearance.cardRadius
                            color: Theme.currentTheme.colors.cardColor
                            border.width: page.selectedTheme === modelData.id ? 2 : 1
                            Behavior on color { ColorAnimation { duration: Backend.systemMotionEnabled ? 140 : 0 } }
                            Behavior on border.color { ColorAnimation { duration: Backend.systemMotionEnabled ? 140 : 0 } }
                            border.color: page.selectedTheme === modelData.id ? Theme.currentTheme.colors.primaryColor : Theme.currentTheme.colors.cardBorderColor
                        }
                        contentItem: ColumnLayout {
                            spacing: 8
                            IslandThemePreview { Layout.fillWidth: true; Layout.preferredHeight: 96; themeId: modelData.id }
                            Text {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 34
                                text: modelData.label
                                typography: Typography.Caption
                                color: Theme.currentTheme.colors.textColor
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }
            }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("透明度")
                typography: Typography.BodyStrong }
                Slider { id: opacityControl
                Layout.preferredWidth: Math.min(300,page.width * 0.42)
                from: 0.35
                to: 1
                stepSize: 0.05
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("islandOpacity", value) }
                Text { Layout.preferredWidth: 46; horizontalAlignment: Text.AlignRight; text: Math.round(opacityControl.value * 100) + "%"
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("组件缩放")
                typography: Typography.BodyStrong }
                Slider { id: scaleControl
                Layout.preferredWidth: Math.min(300,page.width * 0.42)
                from: 0.75
                to: 1.35
                stepSize: 0.05
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("islandScale", value) }
                Text { Layout.preferredWidth: 46; horizontalAlignment: Text.AlignRight; text: Math.round(scaleControl.value * 100) + "%"
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("启动位置")
                typography: Typography.BodyStrong }
                ComboBox { id: anchor
                Layout.preferredWidth: 180
                model: [I18n.t("左上"), I18n.t("顶部中央"), I18n.t("右上"), I18n.t("左下"), I18n.t("底部中央"), I18n.t("右下")]
                onActivated: if (!page.loading) Backend.setSetting("islandAnchor", ["top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right"][currentIndex]) } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("光影效果")
                typography: Typography.BodyStrong }
                Switch { id: lighting
                onClicked: if (!page.loading) Backend.setSetting("islandLightingEffect", checked) } }
        }
    }
}

