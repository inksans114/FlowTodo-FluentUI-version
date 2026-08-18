import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "AI 规划助手"
    wrapperWidth: 920
    horizontalPadding: 34
    property var aiState: ({messages: [], latestPlan: null})
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { try { aiState = JSON.parse(Backend.aiStateJson) } catch (error) { aiState = {messages: []} } }
    Component.onCompleted: load()
    Connections { target: Backend; function onAiStateChanged() { page.load() } }
    SettingCard {
        Layout.fillWidth: true
        title: "描述你的目标"
        description: "AI 会生成任务、任务流和项目结构，可在确认后导入"
        icon.name: "ic_fluent_sparkle_20_regular"
        ColumnLayout {
            Layout.fillWidth: true
            TextArea { id: prompt; Layout.fillWidth: true; Layout.preferredHeight: 120; placeholderText: "例如：我想在 30 天内完成一个 Python 项目，每天投入 1 小时" }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "生成短期计划"; icon.name: "ic_fluent_sparkle_20_regular"; onClicked: Backend.requestAi(prompt.text, false) }
                Button { text: "生成长期计划"; highlighted: true; icon.name: "ic_fluent_calendar_ltr_20_regular"; onClicked: Backend.requestAi(prompt.text, true) }
            }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "最近消息"
        description: "AI 对话和生成结果保存在本地"
        icon.name: "ic_fluent_chat_20_regular"
        ColumnLayout {
            Layout.fillWidth: true
            Repeater {
                model: page.aiState.messages || []
                delegate: Frame {
                    Layout.fillWidth: true
                    leftPadding: 14
                    rightPadding: 14
                    topPadding: 10
                    bottomPadding: 10
                    Text { width: parent.width; text: String(modelData.content || ""); wrapMode: Text.Wrap }
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Button { text: "清空消息"; onClicked: Backend.clear_ai_messages() }
        Item { Layout.fillWidth: true }
        Button { text: "导入最新计划"; highlighted: true; enabled: Boolean(page.aiState.latestPlan); onClicked: Backend.apply_ai_plan_json(JSON.stringify(page.aiState.latestPlan)) }
    }
}
