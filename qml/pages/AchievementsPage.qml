import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "成就"
    wrapperWidth: 760
    horizontalPadding: 36
    contentSpacing: 8
    property var achievements: []
    function reload() { try { achievements = JSON.parse(Backend.achievementsJson) } catch (error) { achievements = [] } }
    Component.onCompleted: reload()
    Connections { target: Backend; function onAchievementsChanged() { page.reload() } }
    RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "完成任务、创建流程和坚持专注都会留下记录。"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
                Text { text: page.achievements.filter(function(item) { return item.unlocked }).length + " / " + page.achievements.length
                typography: Typography.BodyStrong } }
    ColumnLayout { Layout.fillWidth: true
                spacing: 5
        Repeater { model: page.achievements
                delegate: Frame {
            required property var modelData
            Layout.fillWidth: true
            Layout.preferredHeight: 82
            leftPadding: 14
            rightPadding: 14
            topPadding: 12
            bottomPadding: 12
            RowLayout { anchors.fill: parent
                spacing: 12
                Rectangle { width: 42
                height: 42
                radius: 7
                color: modelData.unlocked ? Qt.alpha("#107c10", 0.14) : Qt.alpha(Theme.currentTheme.colors.textSecondaryColor, 0.10)
                Icon { anchors.centerIn: parent
                name: modelData.unlocked ? "ic_fluent_trophy_20_regular" : "ic_fluent_lock_closed_20_regular"
                size: 21
                color: modelData.unlocked ? "#107c10" : Theme.currentTheme.colors.textSecondaryColor } }
                ColumnLayout { Layout.fillWidth: true
                spacing: 3
                RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: String(modelData.title)
                typography: Typography.BodyStrong }
                Text { text: modelData.unlocked ? "已解锁" : String(modelData.current) + " / " + String(modelData.target)
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
                Text { Layout.fillWidth: true
                text: String(modelData.description || "")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                ProgressBar { Layout.fillWidth: true
                from: 0
                to: 100
                value: Number(modelData.progress || 0) } }
            }
        } }
    }
}

