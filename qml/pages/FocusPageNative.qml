import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "专注模式"
    wrapperWidth: 900
    horizontalPadding: 34
    property var tasks: []
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { try { tasks = JSON.parse(Backend.tasksJson).filter(function(item) { return !item.done }) } catch (error) { tasks = [] } }
    Component.onCompleted: load()
    Connections { target: Backend; function onTasksChanged() { page.load() } }
    SettingCard {
        Layout.fillWidth: true
        title: "快速开始专注"
        description: "选择一个未完成任务，灵动岛会自动进入展开模式"
        icon.name: "ic_fluent_timer_20_regular"
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: page.tasks
                delegate: Frame {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 62
                    leftPadding: 14
                    rightPadding: 14
                    RowLayout {
                        anchors.fill: parent
                        Text { Layout.fillWidth: true; text: String(modelData.title || "任务"); typography: Typography.BodyStrong }
                        Text { text: String(modelData.meta || "今天"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                        Button { text: "开始"; highlighted: true; icon.name: "ic_fluent_play_20_regular"; onClicked: { Backend.startTask(Number(modelData.id)); var router = page.nav(); if (router) router.push(Qt.resolvedUrl("FocusSessionNative.qml"), {mode: "single", titleText: modelData.title}) } }
                    }
                }
            }
        }
    }
    SettingCard { Layout.fillWidth: true; title: "专注说明"; description: "专注会话由原版业务后端和原生灵动岛共同管理。主窗口会在会话开始后自动最小化，结束或取消后恢复。"; icon.name: "ic_fluent_info_20_regular" }
}
