import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "应用与数据"
    wrapperWidth: 820
    horizontalPadding: 36
    contentSpacing: 12
    property bool loading: true
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { loading = true; duration.value = Number(Backend.getSetting("focusDuration", 25)); breakDuration.value = Number(Backend.getSetting("breakDuration", 5)); autoStart.checked = Boolean(Backend.getSetting("autoStart", false)); closeBehavior.currentIndex = String(Backend.getSetting("closeBehavior", "tray")) === "exit" ? 1 : 0; loading = false }
    function resetAllData() { Backend.clearAllUserData() }
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
                text: "默认休息时长"
                typography: Typography.BodyStrong }
                Slider { id: breakDuration
                Layout.preferredWidth: 280
                from: 1
                to: 60
                stepSize: 1
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("breakDuration", Math.round(value)) }
                Text { text: Math.round(breakDuration.value) + " 分钟"
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
    Text { text: "窗口关闭"
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        RowLayout { anchors.fill: parent
                ColumnLayout { Layout.fillWidth: true
                spacing: 2
                Text { text: "关闭主窗口时"
                typography: Typography.BodyStrong }
                Text { text: "选择隐藏到系统托盘，或直接退出应用"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
                ComboBox { id: closeBehavior
                Layout.preferredWidth: 190
                model: ["最小化到系统托盘", "直接关闭应用"]
                onActivated: function(index) { if (!page.loading) Backend.setSetting("closeBehavior", index === 1 ? "exit" : "tray") } }
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
        ColumnLayout { anchors.fill: parent
                spacing: 16
                RowLayout { Layout.fillWidth: true
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
                Rectangle { Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    Layout.minimumHeight: 1
                    color: Theme.currentTheme.colors.dividerColor }
                RowLayout { Layout.fillWidth: true
                    ColumnLayout { Layout.fillWidth: true
                        spacing: 2
                        Text { text: "恢复出厂设置"
                            typography: Typography.BodyStrong }
                        Text { Layout.fillWidth: true
                            text: "清除所有本地数据与设置，恢复应用初始状态"
                            typography: Typography.Caption
                            color: Theme.currentTheme.colors.textSecondaryColor
                            wrapMode: Text.Wrap } }
                    Button { text: "清除所有数据"
                        icon.name: "ic_fluent_delete_20_regular"
                        onClicked: resetDialog.open() } }
        }
    }

    FactoryResetDialog { id: resetDialog
        onResetConfirmed: page.resetAllData() }
}


