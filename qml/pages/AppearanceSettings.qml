import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import RinUI
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("外观与灵动岛")
    wrapperWidth: 920
    horizontalPadding: 36
    contentSpacing: 12
    property bool loading: true
    property string accent: "#0f6cbd"
    property var palette: ["#0f6cbd", "#0078d4", "#107c10", "#d83b01", "#b146c2", "#8764b8", "#ca5010", "#00b7c3", "#e74856"]
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        loading = true
        mode.currentIndex = ["auto", "light", "dark"].indexOf(String(Backend.getSetting("theme", "auto")))
        if (mode.currentIndex < 0) mode.currentIndex = 0
        backdrop.currentIndex = ["none", "mica", "acrylic"].indexOf(String(Backend.getSetting("nativeBackdrop", "none")))
        if (backdrop.currentIndex < 0) backdrop.currentIndex = 0
        accent = String(Backend.getSetting("nativeAccent", "#0f6cbd"))
        islandOpacity.value = Number(Backend.getSetting("islandOpacity", 1))
        islandScale.value = Number(Backend.getSetting("islandScale", 1))
        islandAnchor.currentIndex = ["top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right"].indexOf(String(Backend.getSetting("islandAnchor", "top_center")))
        if (islandAnchor.currentIndex < 0) islandAnchor.currentIndex = 1
        loading = false
    }
    function setAccent(color) {
        accent = color
        Theme.setThemeColor(color)
        if (!loading) Backend.setSetting("nativeAccent", color)
    }
    function setMode(index) {
        var value = ["auto", "light", "dark"][index]
        Theme.setTheme(index === 0 ? Theme.mode.Auto : index === 1 ? Theme.mode.Light : Theme.mode.Dark)
        if (!loading) Backend.setSetting("theme", value)
    }
    function setBackdrop(index) {
        var value = ["none", "mica", "acrylic"][index]
        Theme.setBackdropEffect(value)
        if (!loading) Backend.setSetting("nativeBackdrop", value)
    }
    Component.onCompleted: load()

    RowLayout {
        Layout.fillWidth: true
        ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"; ToolTip.text: I18n.t("返回系统设置"); ToolTip.visible: hovered; onClicked: { var router = page.nav(); if (router) router.pop() } }
        Text { text: I18n.t("返回系统设置"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        Item { Layout.fillWidth: true }
    }
    Text { text: I18n.t("应用外观")
                typography: Typography.Subtitle }
    Frame {
        Layout.fillWidth: true
        leftPadding: 18
        rightPadding: 18
        topPadding: 16
        bottomPadding: 16
        ColumnLayout {
            anchors.fill: parent
            spacing: 12
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("明暗模式")
                typography: Typography.BodyStrong }
                ComboBox { id: mode
                Layout.preferredWidth: 160
                model: [I18n.t("跟随系统"), I18n.t("浅色"), I18n.t("深色")]
                onActivated: page.setMode(currentIndex) } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("窗口材质")
                typography: Typography.BodyStrong }
                ComboBox { id: backdrop
                Layout.preferredWidth: 160
                model: [I18n.t("实色"), "Mica", "Acrylic"]
                onActivated: page.setBackdrop(currentIndex) } }
            Text { text: I18n.t("主题色")
                typography: Typography.BodyStrong }
            Flow {
                Layout.fillWidth: true
                spacing: 12
                Repeater {
                    model: page.palette
                    delegate: Button {
                        required property string modelData
                        width: 42
                        height: 42
                        flat: true
                        ToolTip.visible: hovered
                        ToolTip.text: modelData
                        onClicked: page.setAccent(modelData)
                        contentItem: Rectangle { anchors.centerIn: parent
                width: 30
                height: 30
                radius: 15
                color: modelData
                border.width: page.accent === modelData ? 3 : 1
                border.color: page.accent === modelData ? Theme.currentTheme.colors.textColor : Qt.alpha("#000000", 0.18) }
                    }
                }
                DropDownColorPicker { width: 100
                height: 42
                text: I18n.t("自定义")
                icon.name: "ic_fluent_color_20_regular"
                onClicked: colorDialog.open() }
                TextField { Layout.preferredWidth: 112
                text: page.accent
                placeholderText: "#0f6cbd"
                onEditingFinished: { if (/^#[0-9a-fA-F]{6}$/.test(text.trim())) page.setAccent(text.trim()) } }
            }
        }
    }
    Text { text: I18n.t("灵动岛")
                typography: Typography.Subtitle }
    Frame {
        Layout.fillWidth: true
        leftPadding: 18
        rightPadding: 18
        topPadding: 16
        bottomPadding: 16
        ColumnLayout {
            anchors.fill: parent
            spacing: 10
            Text { Layout.fillWidth: true
                text: I18n.t("灵动岛使用系统明暗模式；主题色与应用一致。")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("透明度")
                typography: Typography.BodyStrong }
                Slider { id: islandOpacity
                Layout.preferredWidth: 290
                from: 0.35
                to: 1
                stepSize: 0.05
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("islandOpacity", value) }
                Text { text: Math.round(islandOpacity.value * 100) + "%"
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("组件缩放")
                typography: Typography.BodyStrong }
                Slider { id: islandScale
                Layout.preferredWidth: 290
                from: 0.75
                to: 1.35
                stepSize: 0.05
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("islandScale", value) }
                Text { text: Math.round(islandScale.value * 100) + "%"
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("启动位置")
                typography: Typography.BodyStrong }
                ComboBox { id: islandAnchor
                Layout.preferredWidth: 180
                model: [I18n.t("左上"), I18n.t("顶部中央"), I18n.t("右上"), I18n.t("左下"), I18n.t("底部中央"), I18n.t("右下")]
                onActivated: if (!page.loading) Backend.setSetting("islandAnchor", ["top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right"][currentIndex]) } }
        }
    }
    ColorDialog { id: colorDialog
                title: I18n.t("选择主题色")
                selectedColor: page.accent
                onAccepted: page.setAccent(selectedColor.toString()) }
}

