import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "账户统计"
    wrapperWidth: 920
    horizontalPadding: 34
    property var stats: ({})
    property var achievements: ({})
    function load() {
        try { stats = JSON.parse(Backend.statsJson) } catch (error) { stats = {} }
        try { achievements = JSON.parse(Backend.achievementsJson) } catch (error) { achievements = {} }
    }
    Component.onCompleted: load()
    Connections {
        target: Backend
        function onStatsChanged() { page.load() }
        function onAchievementsChanged() { page.load() }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: width > 720 ? 3 : 1
        columnSpacing: 12
        Repeater {
            model: [
                {label: "累计专注", value: Math.round(Number(page.stats.totalFocusSeconds || 0) / 60) + " 分钟", icon: "ic_fluent_timer_20_regular"},
                {label: "专注次数", value: String(page.stats.totalFocusSessions || 0), icon: "ic_fluent_history_20_regular"},
                {label: "完成任务", value: String(page.stats.completedTasks || 0), icon: "ic_fluent_checkmark_circle_20_regular"}
            ]
            delegate: MetricCard {
                required property var modelData
                Layout.fillWidth: true
                label: modelData.label
                value: modelData.value
                iconName: modelData.icon
                accent: Theme.currentTheme.colors.primaryColor
            }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "成就"
        description: "记录你的专注和整理进度"
        icon.name: "ic_fluent_trophy_20_regular"
        ColumnLayout {
            Layout.fillWidth: true
            Repeater {
                model: Object.values(page.achievements || {})
                delegate: Frame {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 54
                    RowLayout {
                        anchors.fill: parent
                        Text { Layout.fillWidth: true; text: String(modelData.title || modelData.name || "成就"); typography: Typography.Body }
                        Text { text: modelData.unlocked ? "已解锁" : String(modelData.current || 0) + "/" + String(modelData.target || 1); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                    }
                }
            }
        }
    }
}
