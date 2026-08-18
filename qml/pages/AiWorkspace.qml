import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "AI 规划"
    wrapperWidth: 1040
    horizontalPadding: 36
    contentSpacing: 12
    property var aiState: ({messages: [], latestPlan: null})
    property var plan: aiState.latestPlan || null
    property bool requestedLongPlan: false
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function reload() { try { aiState = JSON.parse(Backend.aiStateJson) } catch (error) { aiState = {messages: [], latestPlan: null} } }
    function generate(longMode) {
        if (!prompt.text.trim().length || Backend.aiRequestRunning)
            return
        requestedLongPlan = longMode
        Backend.requestAi(prompt.text.trim(), longMode)
    }
    function openLongPlan() {
        var router = nav()
        if (router && page.plan)
            router.push(Qt.resolvedUrl("AiLongPreviewNative.qml"), { planJson: JSON.stringify(page.plan) })
    }
    Component.onCompleted: reload()
    Connections {
        target: Backend
        function onAiStateChanged() { page.reload() }
        function onAiRequestFinished(ok, message) {
            page.reload()
            if (ok && page.requestedLongPlan)
                latestPlanPulse.restart()
        }
    }
    SequentialAnimation {
        id: latestPlanPulse
        NumberAnimation { target: latestPlanFrame; property: "opacity"; to: 0.55; duration: 100 }
        NumberAnimation { target: latestPlanFrame; property: "opacity"; to: 1.0; duration: 180 }
    }

    RowLayout { Layout.fillWidth: true
        Text { Layout.fillWidth: true
                text: "把一个模糊目标整理成任务、任务流与项目"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
        Button { flat: true
                text: "清空对话"
                icon.name: "ic_fluent_delete_20_regular"; onClicked: Backend.clearAiMessages() }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        spacing: 12
        Frame {
            Layout.fillWidth: true
            Layout.preferredHeight: 430
            leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
            ColumnLayout {
                anchors.fill: parent
                spacing: 10
                RowLayout { Layout.fillWidth: true
                Icon { name: "ic_fluent_sparkle_20_regular"; size: 22
                color: Theme.currentTheme.colors.primaryColor }
                Text { Layout.fillWidth: true
                text: "规划工作区"
                typography: Typography.Subtitle } }
                Text { Layout.fillWidth: true
                text: "描述目标、期限、每天可投入时间，以及你希望最终得到什么。"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap }
                TextArea { id: prompt
                Layout.fillWidth: true
                Layout.fillHeight: true; placeholderText: "例如：30 天内完成一个 PySide6 桌面应用，每天投入 1 小时；需要拆分学习、开发和测试阶段。"
                wrapMode: TextArea.Wrap }
                RowLayout {
                    Layout.fillWidth: true
                    visible: Backend.aiRequestRunning
                    spacing: 8
                    BusyIndicator { running: Backend.aiRequestRunning; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                    Text {
                        Layout.fillWidth: true
                        text: page.requestedLongPlan ? "正在生成长期计划并整理周期数据…" : "正在生成计划…"
                        typography: Typography.Caption
                        color: Theme.currentTheme.colors.primaryColor
                    }
                }
                RowLayout { Layout.fillWidth: true
                    Text { Layout.fillWidth: true
                text: String(Backend.getSetting("aiMode", "API"))
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                    Button { text: "短期计划"
                icon.name: "ic_fluent_flash_20_regular"
                enabled: prompt.text.trim().length > 0 && !Backend.aiRequestRunning; onClicked: page.generate(false) }
                    Button { text: "长期计划"
                highlighted: true
                icon.name: "ic_fluent_calendar_ltr_20_regular"
                enabled: prompt.text.trim().length > 0 && !Backend.aiRequestRunning; onClicked: page.generate(true) }
                }
            }
        }
        ColumnLayout {
            Layout.preferredWidth: 320
            Layout.alignment: Qt.AlignTop
            spacing: 8
            Frame {
                id: latestPlanFrame
                Layout.fillWidth: true
                Layout.preferredHeight: 206
                leftPadding: 16
                rightPadding: 16
                topPadding: 14
                bottomPadding: 14
                ColumnLayout { anchors.fill: parent
                spacing: 8
                    RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "最新计划"
                typography: Typography.BodyStrong }
                Icon { name: page.plan ? "ic_fluent_checkmark_circle_20_regular" : "ic_fluent_info_20_regular"; size: 18
                color: page.plan ? "#0f7b0f" : Theme.currentTheme.colors.textSecondaryColor } }
                    Text { Layout.fillWidth: true
                text: page.plan ? String(page.plan.title || page.plan.name || "已生成计划") : "生成后可在这里检查并导入"
                typography: Typography.Body
                wrapMode: Text.Wrap }
                    Text { Layout.fillWidth: true
                text: page.plan ? ((page.plan.tasks || []).length + " 个任务  ·  " + (page.plan.groups || []).length + " 个任务流  ·  " + (page.plan.projects || []).length + " 个项目") : "当前没有待导入内容"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap }
                    Item { Layout.fillHeight: true }
                    Button { Layout.fillWidth: true
                text: "导入计划"
                highlighted: true
                enabled: Boolean(page.plan)
                icon.name: "ic_fluent_arrow_import_20_regular"; onClicked: Backend.applyAiPlan(JSON.stringify(page.plan)) }
                    Button { Layout.fillWidth: true
                visible: Boolean(page.plan) && (page.plan.mode === "long" || Boolean(page.plan.longPlan))
                text: "预览长期计划"
                icon.name: "ic_fluent_calendar_ltr_20_regular"; onClicked: page.openLongPlan() }
                }
            }
            Frame {
                Layout.fillWidth: true
                Layout.preferredHeight: 216
                leftPadding: 16
                rightPadding: 16
                topPadding: 14
                bottomPadding: 14
                ColumnLayout { anchors.fill: parent
                spacing: 6
                    Text { text: "最近对话"
                typography: Typography.BodyStrong }
                    ScrollView { Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                        ColumnLayout { width: parent.width
                spacing: 5
                            Repeater { model: (page.aiState.messages || []).slice(-4); delegate: Text { Layout.fillWidth: true
                text: (modelData.role === "assistant" ? "AI：" : "你：") + String(modelData.content || "")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight } }
                        }
                    }
                    Text { visible: !(page.aiState.messages || []).length
                text: "还没有对话记录"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                }
            }
        }
    }
}

