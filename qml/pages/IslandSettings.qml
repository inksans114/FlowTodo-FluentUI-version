import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "灵动岛"
    wrapperWidth: 760
    horizontalPadding: 36
    contentSpacing: 12
    property bool loading: true
    property string selectedTheme: "material"
    property var islandThemes: [
        { id: "default", label: "默认" },
        { id: "cw1", label: "远古版" },
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
                ToolTip.text: "返回系统设置"
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { text: "返回系统设置"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        ColumnLayout { anchors.fill: parent
                spacing: 14
            Text { text: "灵动岛主题"; typography: Typography.BodyStrong }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                Repeater {
                    model: page.islandThemes
                    delegate: Button {
                        required property var modelData
                        width: 158
                        height: 112
                        flat: true
                        padding: 0
                        ToolTip.visible: hovered
                        ToolTip.text: modelData.label
                        onClicked: page.selectTheme(modelData.id)
                        background: Rectangle {
                            radius: 8
                            color: "transparent"
                            border.width: page.selectedTheme === modelData.id ? 3 : 1
                            border.color: page.selectedTheme === modelData.id
                                ? Theme.currentTheme.colors.primaryColor
                                : Theme.currentTheme.colors.cardBorderColor
                        }
                        contentItem: Rectangle {
                            anchors.fill: parent
                            anchors.margins: page.selectedTheme === modelData.id ? 3 : 1
                            radius: 6
                            clip: true
                            Image {
                                anchors.fill: parent
                                source: Backend.themePreviewUrl(modelData.id)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                            }
                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 38
                                color: "#88000000"
                            }
                            Text {
                                anchors.left: parent.left
                                anchors.leftMargin: 10
                                anchors.right: parent.right
                                anchors.rightMargin: 8
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 9
                                text: modelData.label
                                color: "white"
                                typography: Typography.BodyStrong
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "透明度"
                typography: Typography.BodyStrong }
                Slider { id: opacityControl
                Layout.preferredWidth: 300
                from: 0.35
                to: 1
                stepSize: 0.05
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("islandOpacity", value) }
                Text { text: Math.round(opacityControl.value * 100) + "%"
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "组件缩放"
                typography: Typography.BodyStrong }
                Slider { id: scaleControl
                Layout.preferredWidth: 300
                from: 0.75
                to: 1.35
                stepSize: 0.05
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("islandScale", value) }
                Text { text: Math.round(scaleControl.value * 100) + "%"
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "启动位置"
                typography: Typography.BodyStrong }
                ComboBox { id: anchor
                Layout.preferredWidth: 180
                model: ["左上", "顶部中央", "右上", "左下", "底部中央", "右下"]
                onActivated: if (!page.loading) Backend.setSetting("islandAnchor", ["top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right"][currentIndex]) } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "光影效果"
                typography: Typography.BodyStrong }
                Switch { id: lighting
                onClicked: if (!page.loading) Backend.setSetting("islandLightingEffect", checked) } }
        }
    }
}

