import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "账户统计"
    wrapperWidth: 920
    horizontalPadding: 36
    contentSpacing: 12
    property var stats: ({tasks: {}, groups: {}, projects: {}, focus: {}})
    property var achievements: []
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function reload() { try { stats = JSON.parse(Backend.statsJson) } catch (error) { stats = {tasks: {}, groups: {}, projects: {}, focus: {}} }; try { achievements = JSON.parse(Backend.achievementsJson) } catch (error) { achievements = [] } }
    Component.onCompleted: reload()
    Connections {
        target: Backend
        function onStatsChanged() { page.reload() }
        function onAchievementsChanged() { page.reload() }
    }
    RowLayout { Layout.fillWidth: true
        Text { Layout.fillWidth: true
                text: "专注、完成与项目推进都保存在本地。"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
        Button { text: "查看成就"
                icon.name: "ic_fluent_trophy_20_regular"
                onClicked: { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("AchievementsPage.qml")) } }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: width > 760 ? 4 : 2
        columnSpacing: 8
        rowSpacing: 8
        MetricCard { label: "累计专注"
                value: String((page.stats.focus || {}).totalMinutes || 0) + " 分钟"
                iconName: "ic_fluent_timer_20_regular"
                accent: "#0f6cbd" }
        MetricCard { label: "今日专注"
                value: String((page.stats.focus || {}).todayMinutes || 0) + " 分钟"
                iconName: "ic_fluent_weather_sunny_20_regular"
                accent: "#107c10" }
        MetricCard { label: "专注次数"
                value: String((page.stats.focus || {}).totalSessions || 0)
                iconName: "ic_fluent_history_20_regular"
                accent: "#8764b8" }
        MetricCard { label: "完成任务"
                value: String((page.stats.tasks || {}).done || 0)
                iconName: "ic_fluent_checkmark_circle_20_regular"
                accent: "#d83b01" }
    }
    Text { text: "工作概览"
                typography: Typography.Subtitle }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4
        Repeater {
            model: [
                {label: "任务完成", value: String((page.stats.tasks || {}).done || 0) + " / " + String((page.stats.tasks || {}).total || 0), icon: "ic_fluent_clipboard_task_list_ltr_20_regular"},
                {label: "已创建任务流", value: String((page.stats.groups || {}).total || 0), icon: "ic_fluent_flow_20_regular"},
                {label: "项目里程碑", value: String((page.stats.projects || {}).doneMilestones || 0) + " / " + String((page.stats.projects || {}).totalMilestones || 0), icon: "ic_fluent_flag_20_regular"},
                {label: "已完成项目", value: String((page.stats.projects || {}).completedProjects || 0), icon: "ic_fluent_board_20_regular"}
            ]
            delegate: Frame { required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 58
                leftPadding: 14
                rightPadding: 14
                RowLayout { anchors.fill: parent
                Icon { name: modelData.icon
                size: 20
                color: Theme.currentTheme.colors.primaryColor }
                Text { Layout.fillWidth: true
                text: modelData.label
                typography: Typography.Body }
                Text { text: modelData.value
                typography: Typography.BodyStrong } } }
        }
    }
}

