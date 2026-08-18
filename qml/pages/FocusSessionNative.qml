import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "专注进行中"
    wrapperWidth: 760
    horizontalPadding: 34
    property string mode: "single"
    property string titleText: "专注会话"
    property var session: ({})
    property int remaining: 0
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function reload() {
        try {
            session = JSON.parse(Backend.focusSessionJson)
            remaining = Number(session.remaining !== undefined && session.remaining !== null ? session.remaining : (session.remainingSeconds || session.taskSeconds || session.totalSeconds || 0))
            if (session.title) titleText = session.title
        } catch (error) { session = ({}) }
    }
    function formatSeconds(value) { var total = Math.max(0, Number(value) || 0); var mins = Math.floor(total / 60); var secs = total % 60; return (mins < 10 ? "0" : "") + mins + ":" + (secs < 10 ? "0" : "") + secs }
    Component.onCompleted: reload()
    Connections { target: Backend; function onFocusSessionChanged() { page.reload() } }
    Timer { interval: 1000; running: page.visible && page.remaining > 0 && page.session.event !== "cancelled" && page.session.event !== "completed"; repeat: true; onTriggered: page.remaining = Math.max(0, page.remaining - 1) }
    Frame {
        Layout.fillWidth: true
        Layout.preferredHeight: 350
        leftPadding: 34
        rightPadding: 34
        topPadding: 30
        bottomPadding: 30
        ColumnLayout {
            anchors.fill: parent
            spacing: 14
            Icon { Layout.alignment: Qt.AlignHCenter; name: "ic_fluent_timer_20_regular"; size: 42; color: Theme.currentTheme.colors.primaryColor }
            Text { Layout.alignment: Qt.AlignHCenter; text: page.titleText; typography: Typography.Title }
            Text { Layout.alignment: Qt.AlignHCenter; text: page.session.totalTasks ? "阶段 " + (Number(page.session.index || 0) + 1) + " / " + page.session.totalTasks + "  ·  " + (page.session.type === "break" ? "休息中" : "专注中") : (page.mode === "group" ? "任务流专注" : page.mode === "project" ? "项目专注" : "单任务专注"); typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor }
            Text { Layout.alignment: Qt.AlignHCenter; text: page.formatSeconds(page.remaining); font.pixelSize: 56; font.weight: Font.Medium }
            Text { Layout.alignment: Qt.AlignHCenter; text: page.session.event === "cancelled" ? "本次专注已取消" : page.session.event === "completed" ? "本次专注已完成" : "桌面灵动岛与此处倒计时保持同步"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 10
                Button { text: "取消专注"; icon.name: "ic_fluent_stop_20_regular"; onClicked: { Backend.cancelFocus(); var router = page.nav(); if (router) router.pop() } }
                Button { text: "返回任务"; onClicked: { var router = page.nav(); if (router) router.pop() } }
            }
        }
    }
}
