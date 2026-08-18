import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "账户统计"
    wrapperWidth: 1000
    horizontalPadding: 36
    contentSpacing: 12
    property var stats: ({tasks: {}, groups: {}, projects: {}, focus: {}})
    property var achievements: []
    function reload() { try { stats = JSON.parse(Backend.statsJson) } catch (error) { stats = {tasks: {}, groups: {}, projects: {}, focus: {}} }; try { achievements = JSON.parse(Backend.achievementsJson) } catch (error) { achievements = [] } }
    Component.onCompleted: reload()
    Connections {
        target: Backend
        function onStatsChanged() { page.reload() }
        function onAchievementsChanged() { page.reload() }
    }

    RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "本地记录你的完成情况、专注时长和里程碑进度"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
                Text { text: "数据仅保存在当前数据目录"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
    GridLayout {
        Layout.fillWidth: true
                columns: width > 760 ? 4 : 2
                columnSpacing: 8
                rowSpacing: 8
        MetricCard { label: "累计专注"
                value: String((page.stats.focus || {}).totalMinutes || 0) + " 分钟"; iconName: "ic_fluent_timer_20_regular"; accent: "#0f6cbd" }
        MetricCard { label: "今日专注"
                value: String((page.stats.focus || {}).todayMinutes || 0) + " 分钟"; iconName: "ic_fluent_weather_sunny_20_regular"; accent: "#b146c2" }
        MetricCard { label: "专注次数"
                value: String((page.stats.focus || {}).totalSessions || 0); iconName: "ic_fluent_history_20_regular"; accent: "#8764b8" }
        MetricCard { label: "完成任务"
                value: String((page.stats.tasks || {}).done || 0); iconName: "ic_fluent_checkmark_circle_20_regular"; accent: "#0f7b0f" }
    }
    RowLayout {
        Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 12
        Frame {
            Layout.preferredWidth: 310
                Layout.preferredHeight: 330
                leftPadding: 16
                rightPadding: 16
                topPadding: 14
                bottomPadding: 14
            ColumnLayout { anchors.fill: parent
                spacing: 10
                Text { text: "工作概览"
                typography: Typography.Subtitle }
                Repeater { model: [
                    {label: "任务", value: String((page.stats.tasks || {}).done || 0) + " / " + String((page.stats.tasks || {}).total || 0), icon: "ic_fluent_clipboard_task_list_ltr_20_regular"},
                    {label: "任务流", value: String((page.stats.groups || {}).total || 0), icon: "ic_fluent_flow_20_regular"},
                    {label: "项目", value: String((page.stats.projects || {}).total || 0), icon: "ic_fluent_board_20_regular"},
                    {label: "完成里程碑", value: String((page.stats.projects || {}).doneMilestones || 0) + " / " + String((page.stats.projects || {}).totalMilestones || 0), icon: "ic_fluent_flag_20_regular"}
                ]; delegate: RowLayout { required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                Icon { name: modelData.icon; size: 20
                color: Theme.currentTheme.colors.primaryColor }
                Text { Layout.fillWidth: true
                text: modelData.label
                typography: Typography.Body }
                Text { text: modelData.value
                typography: Typography.BodyStrong } } }
                Item { Layout.fillHeight: true }
            }
        }
        Frame {
            Layout.fillWidth: true
                Layout.preferredHeight: 330
                leftPadding: 16
                rightPadding: 16
                topPadding: 14
                bottomPadding: 14
            ColumnLayout { anchors.fill: parent
                spacing: 6
                RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "成就"
                typography: Typography.Subtitle }
                Text { text: page.achievements.filter(function(item) { return item.unlocked }).length + " / " + page.achievements.length
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
                ScrollView { Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                    ColumnLayout { width: parent.width
                spacing: 4
                        Repeater { model: page.achievements; delegate: Frame {
                            required property var modelData
                            Layout.fillWidth: true
                Layout.preferredHeight: 70
                leftPadding: 10
                rightPadding: 10
                topPadding: 8
                bottomPadding: 8
                            RowLayout { anchors.fill: parent
                spacing: 10
                                Rectangle { width: 34
                height: 34
                radius: 6
                color: modelData.unlocked ? Qt.alpha("#0f7b0f", 0.14) : Qt.alpha(Theme.currentTheme.colors.textSecondaryColor, 0.1)
                Icon { anchors.centerIn: parent; name: modelData.unlocked ? "ic_fluent_trophy_20_regular" : "ic_fluent_lock_closed_20_regular"; size: 18
                color: modelData.unlocked ? "#0f7b0f" : Theme.currentTheme.colors.textSecondaryColor } }
                                ColumnLayout { Layout.fillWidth: true
                spacing: 2
                RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: String(modelData.title || "成就")
                typography: Typography.BodyStrong }
                Text { text: modelData.unlocked ? "已解锁" : String(modelData.current || 0) + "/" + String(modelData.target || 1)
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
                ProgressBar { Layout.fillWidth: true
                from: 0
                to: 100
                value: Number(modelData.progress || 0) } }
                            }
                        } }
                    }
                }
            }
        }
    }
}

