import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "应用外观"
    wrapperWidth: 760
    horizontalPadding: 36
    contentSpacing: 12
    property bool loading: true
    property string accent: "#0f6cbd"
    property var palette: ["#0f6cbd", "#0078d4", "#107c10", "#d83b01", "#b146c2", "#8764b8", "#00b7c3", "#e74856"]
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { loading = true; mode.currentIndex = ["auto", "light", "dark"].indexOf(String(Backend.getSetting("theme", "auto"))); if (mode.currentIndex < 0) mode.currentIndex = 0; backdrop.currentIndex = ["none", "mica", "acrylic"].indexOf(String(Backend.getSetting("nativeBackdrop", "none"))); if (backdrop.currentIndex < 0) backdrop.currentIndex = 0; accent = String(Backend.getSetting("nativeAccent", "#0f6cbd")); loading = false }
    function setAccent(color) { accent = color; Theme.setThemeColor(color); if (!loading) Backend.setSetting("nativeAccent", color) }
    function setMode(index) { Theme.setTheme(index === 0 ? Theme.mode.Auto : index === 1 ? Theme.mode.Light : Theme.mode.Dark); if (!loading) Backend.setSetting("theme", ["auto", "light", "dark"][index]) }
    function setBackdrop(index) { Theme.setBackdropEffect(["none", "mica", "acrylic"][index]); if (!loading) Backend.setSetting("nativeBackdrop", ["none", "mica", "acrylic"][index]) }
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
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "明暗模式"
                typography: Typography.BodyStrong }
                ComboBox { id: mode
                Layout.preferredWidth: 160
                model: ["跟随系统", "浅色", "深色"]
                onActivated: page.setMode(currentIndex) } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "窗口材质"
                typography: Typography.BodyStrong }
                ComboBox { id: backdrop
                Layout.preferredWidth: 160
                model: ["实色", "Mica", "Acrylic"]
                onActivated: page.setBackdrop(currentIndex) } }
            Text { text: "主题色"
                typography: Typography.BodyStrong }
            Flow { Layout.fillWidth: true
                spacing: 12
                Repeater { model: page.palette
                delegate: Button { required property string modelData
                width: 40
                height: 40
                implicitWidth: 40
                implicitHeight: 40
                flat: true
                padding: 0
                ToolTip.visible: hovered
                ToolTip.text: modelData
                onClicked: page.setAccent(modelData)
                background: Item {}
                contentItem: Item {
                    implicitWidth: 40
                    implicitHeight: 40
                    Rectangle {
                        anchors.centerIn: parent
                        width: 30
                        height: width
                        radius: width / 2
                        color: modelData
                        border.width: page.accent.toLowerCase() === modelData.toLowerCase() ? 3 : 1
                        border.color: page.accent.toLowerCase() === modelData.toLowerCase()
                            ? Theme.currentTheme.colors.textColor
                            : Qt.alpha("#000000", 0.18)
                    }
                } } }
                DropDownColorPicker {
                    id: customPicker
                    width: 142
                    height: 42
                    implicitWidth: 142
                    implicitHeight: 42
                    color: page.accent
                    text: "自定义"
                    textVisible: true
                    hexText: false
                    moreVisible: true
                    colorSliderVisible: true
                    colorChannelInputVisible: true
                    hexInputVisible: true
                    alphaEnabled: false
                    alphaSliderVisible: false
                    alphaInputVisible: false
                    ringMode: false
                    ToolTip.visible: hovered
                    ToolTip.text: "自定义主题色"
                    onColorChanged: {
                        var nextColor = color.toString()
                        if (!page.loading && nextColor.toLowerCase() !== page.accent.toLowerCase())
                            page.setAccent(nextColor)
                    }
                }
                TextField { Layout.preferredWidth: 120
                text: page.accent
                placeholderText: "#0f6cbd"
                onEditingFinished: if (/^#[0-9a-fA-F]{6}$/.test(text.trim())) page.setAccent(text.trim()) }
            }
        }
    }
}

