import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("详细规划")
    wrapperWidth: 1040
    horizontalPadding: 32
    contentSpacing: 18
    extraHeaderItems: [Button { flat: true; text: I18n.t("已保存方案"); icon.name: "ic_fluent_folder_20_regular"; onClicked: { var router = nav(); if (router) router.push(Qt.resolvedUrl("AiSavedPlans.qml")) } }]
    LayoutTokens { id: ui }
    readonly property bool compactLayout: width - horizontalPadding * 2 < 820
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
                text: I18n.t("把一个模糊目标整理成任务、任务流与项目")
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
        Button { flat: true
                text: I18n.t("清空对话")
                icon.name: "ic_fluent_delete_20_regular"; onClicked: Backend.clearAiMessages() }
    }

    GridLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        columns: page.compactLayout ? 1 : 2
        columnSpacing: ui.cardGap
        rowSpacing: ui.cardGap
        Frame {
            Layout.fillWidth: true
            Layout.preferredHeight: 550
            leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
            contentItem: ColumnLayout {
                spacing: 10
                RowLayout { Layout.fillWidth: true
                Icon { name: "ic_fluent_sparkle_20_regular"; size: 22
                color: Theme.currentTheme.colors.primaryColor }
                Text { Layout.fillWidth: true
                text: I18n.t("规划工作区")
                typography: Typography.Subtitle } }
                Text { Layout.fillWidth: true
                text: I18n.t("描述目标、期限、每天可投入时间，以及你希望最终得到什么。")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap }
                TextArea { id: prompt
                Layout.fillWidth: true
                Layout.fillHeight: true; placeholderText: I18n.t("例如：30 天内完成一个 PySide6 桌面应用，每天投入 1 小时；需要拆分学习、开发和测试阶段。")
                wrapMode: TextArea.Wrap }
                VoiceCapture { Layout.fillWidth: true; inputTarget: prompt; onRecognized: function(text) { prompt.text += (prompt.text.trim().length ? "\n" : "") + text } }
                RowLayout {
                    Layout.fillWidth: true
                    visible: Backend.aiRequestRunning
                    spacing: 8
                    BusyIndicator { running: Backend.aiRequestRunning; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                    Text {
                        Layout.fillWidth: true
                        text: page.requestedLongPlan ? I18n.t("正在生成长期计划并整理周期数据…") : I18n.t("正在生成计划…")
                        typography: Typography.Caption
                        color: Theme.currentTheme.colors.primaryColor
                    }
                }
                RowLayout { Layout.fillWidth: true
                    Text { Layout.fillWidth: true
                text: String(Backend.getSetting("aiMode", "API"))
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                    Button { text: I18n.t("短期计划")
                icon.name: "ic_fluent_flash_20_regular"
                enabled: prompt.text.trim().length > 0 && !Backend.aiRequestRunning; onClicked: page.generate(false) }
                    Button { text: I18n.t("长期计划")
                highlighted: true
                icon.name: "ic_fluent_calendar_ltr_20_regular"
                enabled: prompt.text.trim().length > 0 && !Backend.aiRequestRunning; onClicked: page.generate(true) }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: page.compactLayout
            Layout.preferredWidth: page.compactLayout ? 0 : 320
            Layout.alignment: Qt.AlignTop
            spacing: ui.cardGap
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
                text: I18n.t("最新计划")
                typography: Typography.BodyStrong }
                Icon { name: page.plan ? "ic_fluent_checkmark_circle_20_regular" : "ic_fluent_info_20_regular"; size: 18
                color: page.plan ? "#0f7b0f" : Theme.currentTheme.colors.textSecondaryColor } }
                    Text { Layout.fillWidth: true
                text: page.plan ? String(page.plan.title || page.plan.name || I18n.t("已生成计划")) : I18n.t("生成后可在这里检查并导入")
                typography: Typography.Body
                wrapMode: Text.Wrap }
                    Text { Layout.fillWidth: true
                text: page.plan ? ((page.plan.tasks || []).length + I18n.t(" 个任务  ·  ") + (page.plan.groups || []).length + I18n.t(" 个任务流  ·  ") + (page.plan.projects || []).length + I18n.t(" 个项目")) : I18n.t("当前没有待导入内容")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap }
                    Item { Layout.fillHeight: true }
                    Button { Layout.fillWidth: true
                objectName: "detailedPlanImportButton"
                text: I18n.t("导入待办、任务流与日程")
                highlighted: true
                enabled: Boolean(page.plan) && !Backend.aiRequestRunning
                icon.name: "ic_fluent_arrow_import_20_regular"; onClicked: Backend.applyAiPlan(JSON.stringify(page.plan)) }
                    Button { Layout.fillWidth: true
                visible: Boolean(page.plan) && (page.plan.mode === "long" || Boolean(page.plan.longPlan))
                text: I18n.t("预览长期计划")
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
                    Text { text: I18n.t("最近对话")
                typography: Typography.BodyStrong }
                    ScrollView { Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                        ColumnLayout { width: parent.width
                spacing: 5
                            Repeater { model: (page.aiState.messages || []).slice(-4); delegate: Text { Layout.fillWidth: true
                text: (modelData.role === "assistant" ? "AI：" : I18n.t("你：")) + String(modelData.content || "")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight } }
                        }
                    }
                    Text { visible: !(page.aiState.messages || []).length
                text: I18n.t("还没有对话记录")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                }
            }
        }
    }
}

