import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "应用与数据"
    wrapperWidth: 820
    horizontalPadding: 36
    contentSpacing: 12
    property bool loading: true
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { loading = true; duration.value = Number(Backend.getSetting("focusDuration", 25)); autoStart.checked = Boolean(Backend.getSetting("autoStart", false)); loading = false }
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
    Text { text: "专注"
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        ColumnLayout { anchors.fill: parent
                spacing: 12
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "默认专注时长"
                typography: Typography.BodyStrong }
                Slider { id: duration
                Layout.preferredWidth: 280
                from: 5
                to: 120
                stepSize: 5
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("focusDuration", Math.round(value)) }
                Text { text: Math.round(duration.value) + " 分钟"
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "应用拦截"
                typography: Typography.BodyStrong }
                Button { text: "选择允许的应用"
                icon.name: "ic_fluent_shield_checkmark_20_regular"
                onClicked: { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("FocusGuardApps.qml")) } } }
        }
    }
    Text { text: "应用"
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        RowLayout { anchors.fill: parent
                Text { Layout.fillWidth: true
                text: "开机自动启动"
                typography: Typography.BodyStrong }
                Switch { id: autoStart
                onClicked: if (!page.loading) Backend.setSetting("autoStart", checked) } }
    }
    Text { text: "数据"
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        RowLayout { anchors.fill: parent
                ColumnLayout { Layout.fillWidth: true
                spacing: 2
                Text { text: "FlowTodo 数据目录"
                typography: Typography.BodyStrong }
                Text { Layout.fillWidth: true
                text: Backend.dataPath
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                elide: Text.ElideMiddle } }
                Button { text: "更改"
                icon.name: "ic_fluent_folder_open_20_regular"
                onClicked: Backend.chooseDataDirectory() } }
    }
}


