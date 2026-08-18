import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "小组件设置"
    wrapperWidth: 820
    horizontalPadding: 36
    contentSpacing: 12

    property bool loading: true

    function navigationView() {
        var item = page
        while (item) {
            if (item.objectName === "MainNavigationView")
                return item
            item = item.parent
        }
        return null
    }
    function load() {
        loading = true
        widgetOpacity.value = Number(Backend.getSetting("desktopWidgetOpacity", 0.96))
        autoShow.checked = Boolean(Backend.getSetting("desktopWidgetAutoShow", false))
        widgetLayer.currentIndex = ["top", "normal", "bottom"].indexOf(String(Backend.getSetting("desktopWidgetLayer", "top")))
        if (widgetLayer.currentIndex < 0)
            widgetLayer.currentIndex = 0
        widgetLocked.checked = Boolean(Backend.getSetting("desktopWidgetLocked", false))
        widgetWidth.value = Number(Backend.getSetting("desktopWidgetWidth", 400))
        widgetHeight.value = Number(Backend.getSetting("desktopWidgetHeight", 570))
        loading = false
    }
    function goBack() {
        var router = navigationView()
        if (router)
            router.pop()
    }

    Component.onCompleted: load()
    Connections {
        target: Backend
        function onSettingsChanged() {
            if (!widgetOpacity.pressed && !widgetWidth.pressed && !widgetHeight.pressed)
                page.load()
        }
    }

    RowLayout {
        Layout.fillWidth: true
        ToolButton {
            icon.name: "ic_fluent_arrow_left_20_regular"
            ToolTip.text: "返回系统设置"
            ToolTip.visible: hovered
            onClicked: page.goBack()
        }
        Text { text: "返回系统设置"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        Item { Layout.fillWidth: true }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "小组件透明度"
        description: Math.round(widgetOpacity.value * 100) + "%"
        icon.name: "ic_fluent_transparency_square_20_regular"
        RowLayout {
            Layout.preferredWidth: 300
            Slider {
                id: widgetOpacity
                Layout.fillWidth: true
                from: 0.35
                to: 1
                stepSize: 0.05
                onPressedChanged: {
                    if (!pressed && !page.loading)
                        Backend.setSetting("desktopWidgetOpacity", value)
                }
            }
            Text {
                Layout.preferredWidth: 52
                horizontalAlignment: Text.AlignRight
                text: Math.round(widgetOpacity.value * 100) + "%"
                typography: Typography.Caption
            }
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "随应用启动"
        description: "启动 FlowTodo 时自动显示"
        icon.name: "ic_fluent_pin_20_regular"
        Switch {
            id: autoShow
            onClicked: if (!page.loading) Backend.setSetting("desktopWidgetAutoShow", checked)
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "窗口层级"
        description: ["始终显示在其他窗口上方", "按普通窗口层级显示", "始终显示在其他窗口下方"][widgetLayer.currentIndex]
        icon.name: "ic_fluent_layer_20_regular"
        Segmented {
            id: widgetLayer
            Layout.preferredWidth: 300
            currentIndex: 0
            onCurrentIndexChanged: {
                if (!page.loading && currentIndex >= 0)
                    Backend.setSetting("desktopWidgetLayer", ["top", "normal", "bottom"][currentIndex])
            }
            SegmentedItem { text: "置顶"; icon.name: "ic_fluent_arrow_up_20_regular" }
            SegmentedItem { text: "普通"; icon.name: "ic_fluent_window_20_regular" }
            SegmentedItem { text: "置底"; icon.name: "ic_fluent_arrow_down_20_regular" }
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "固定位置"
        description: widgetLocked.checked ? "已禁止拖动小组件" : "可以拖动小组件"
        icon.name: "ic_fluent_lock_closed_20_regular"
        Switch {
            id: widgetLocked
            onClicked: if (!page.loading) Backend.setSetting("desktopWidgetLocked", checked)
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "小组件尺寸"
        description: Math.round(widgetWidth.value) + " × " + Math.round(widgetHeight.value)
        icon.name: "ic_fluent_resize_20_regular"
        ColumnLayout {
            Layout.preferredWidth: 330
            spacing: 6
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.preferredWidth: 32; text: "宽度"; typography: Typography.Caption }
                Slider {
                    id: widgetWidth
                    Layout.fillWidth: true
                    from: 320
                    to: 720
                    stepSize: 20
                    onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("desktopWidgetWidth", Math.round(value))
                }
                Text { Layout.preferredWidth: 54; horizontalAlignment: Text.AlignRight; text: Math.round(widgetWidth.value) + " px"; typography: Typography.Caption }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.preferredWidth: 32; text: "高度"; typography: Typography.Caption }
                Slider {
                    id: widgetHeight
                    Layout.fillWidth: true
                    from: 360
                    to: 900
                    stepSize: 30
                    onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("desktopWidgetHeight", Math.round(value))
                }
                Text { Layout.preferredWidth: 54; horizontalAlignment: Text.AlignRight; text: Math.round(widgetHeight.value) + " px"; typography: Typography.Caption }
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        leftPadding: 18
        rightPadding: 18
        topPadding: 14
        bottomPadding: 14
        RowLayout {
            anchors.fill: parent
            spacing: 8
            Icon { name: "ic_fluent_apps_list_detail_20_regular"; size: 22; color: Theme.currentTheme.colors.primaryColor }
            Text { Layout.fillWidth: true; text: "窗口"; typography: Typography.BodyStrong }
            Button {
                text: "隐藏"
                icon.name: "ic_fluent_dismiss_20_regular"
                onClicked: Backend.hideDesktopWidget()
            }
            Button {
                text: "打开"
                highlighted: true
                icon.name: "ic_fluent_open_20_regular"
                onClicked: Backend.showDesktopWidget()
            }
        }
    }
}
