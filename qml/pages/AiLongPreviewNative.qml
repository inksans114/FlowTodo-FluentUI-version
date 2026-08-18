import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "长期计划预览"
    wrapperWidth: 980
    horizontalPadding: 36
    contentSpacing: 14

    property string planJson: ""
    property var plan: ({})
    readonly property var longPlan: plan.longPlan || ({})
    readonly property var cycles: longPlan.cycles || []
    readonly property var currentCycle: cycles.length > 0 ? cycles[0] : null
    readonly property bool hasPlan: Boolean(plan && (plan.title || plan.longPlan))

    function navigationView() {
        var item = page
        while (item) {
            if (item.objectName === "MainNavigationView")
                return item
            item = item.parent
        }
        return null
    }
    function isPlan(candidate) {
        return Boolean(candidate && (candidate.title || candidate.longPlan || candidate.mode))
    }
    function load() {
        var selected = null
        if (planJson && planJson.trim().length > 0) {
            try {
                var passedPlan = JSON.parse(planJson)
                if (isPlan(passedPlan))
                    selected = passedPlan
            } catch (error) {}
        }
        if (!selected) {
            try {
                var aiState = JSON.parse(Backend.aiStateJson || "{}")
                if (isPlan(aiState.latestPlan))
                    selected = aiState.latestPlan
            } catch (error) {}
        }
        if (!selected) {
            try {
                var activeState = JSON.parse(Backend.longPlanJson || "{}")
                if (isPlan(activeState.plan))
                    selected = activeState.plan
            } catch (error) {}
        }
        plan = selected || ({})
    }
    function returnToWorkspace() {
        var router = navigationView()
        if (router)
            router.pop()
    }
    Component.onCompleted: load()
    Connections {
        target: Backend
        function onAiStateChanged() { if (!page.planJson) page.load() }
        function onLongPlanChanged() { if (!page.planJson) page.load() }
    }

    RowLayout {
        Layout.fillWidth: true
        ToolButton {
            icon.name: "ic_fluent_arrow_left_20_regular"
            ToolTip.text: "返回 AI 规划"
            ToolTip.visible: hovered
            onClicked: page.returnToWorkspace()
        }
        Text { text: "返回 AI 规划"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        Item { Layout.fillWidth: true }
    }

    Frame {
        Layout.fillWidth: true
        leftPadding: 20; rightPadding: 20; topPadding: 18; bottomPadding: 18
        ColumnLayout {
            anchors.fill: parent
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                Icon { name: "ic_fluent_calendar_ltr_24_regular"; size: 24; color: Theme.currentTheme.colors.primaryColor }
                Text {
                    Layout.fillWidth: true
                    text: page.hasPlan ? String(page.plan.title || "长期计划") : "还没有可预览的长期计划"
                    typography: Typography.Subtitle
                    wrapMode: Text.Wrap
                }
                Text {
                    visible: page.hasPlan
                    text: String(page.longPlan.durationText || "未指定周期")
                    typography: Typography.BodyStrong
                    color: Theme.currentTheme.colors.primaryColor
                }
            }
            Text {
                Layout.fillWidth: true
                text: page.hasPlan ? String(page.plan.summary || page.longPlan.goal || "") : "请返回 AI 规划页生成长期计划。"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.fillWidth: true
                visible: page.hasPlan
                spacing: 24
                Text { text: "周期  " + String(page.longPlan.totalCycles || page.cycles.length || 0); typography: Typography.BodyStrong }
                Text { text: "每周期  " + String(page.longPlan.cycleLengthDays || 0) + " 天"; typography: Typography.BodyStrong }
                Text { text: "当前已生成  " + String(page.currentCycle ? (page.currentCycle.days || []).length : 0) + " 天"; typography: Typography.BodyStrong }
                Item { Layout.fillWidth: true }
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        visible: page.hasPlan
        leftPadding: 20; rightPadding: 20; topPadding: 16; bottomPadding: 16
        ColumnLayout {
            anchors.fill: parent
            spacing: 8
            Text { text: "计划目标"; typography: Typography.Subtitle }
            Text {
                Layout.fillWidth: true
                text: String(page.longPlan.goal || page.plan.description || "未提供目标说明")
                typography: Typography.Body
                wrapMode: Text.Wrap
            }
        }
    }

    Text {
        Layout.fillWidth: true
        visible: page.hasPlan && (page.longPlan.roadmap || []).length > 0
        text: "完整路线图"
        typography: Typography.Subtitle
    }
    ColumnLayout {
        Layout.fillWidth: true
        visible: page.hasPlan && (page.longPlan.roadmap || []).length > 0
        spacing: 8
        Repeater {
            model: page.longPlan.roadmap || []
            delegate: Frame {
                Layout.fillWidth: true
                leftPadding: 16; rightPadding: 16; topPadding: 12; bottomPadding: 12
                RowLayout {
                    anchors.fill: parent
                    spacing: 12
                    Text { text: String(index + 1); typography: Typography.BodyStrong; color: Theme.currentTheme.colors.primaryColor }
                    Text {
                        Layout.fillWidth: true
                        text: typeof modelData === "string" ? modelData : String(modelData.title || modelData.name || "")
                        typography: Typography.Body
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        visible: Boolean(page.currentCycle)
        leftPadding: 20; rightPadding: 20; topPadding: 16; bottomPadding: 16
        ColumnLayout {
            anchors.fill: parent
            spacing: 8
            Text { text: "当前周期"; typography: Typography.Caption; color: Theme.currentTheme.colors.primaryColor }
            Text {
                Layout.fillWidth: true
                text: page.currentCycle ? String(page.currentCycle.title || "第 1 周期") : ""
                typography: Typography.Subtitle
                wrapMode: Text.Wrap
            }
            Text {
                Layout.fillWidth: true
                text: page.currentCycle ? String(page.currentCycle.goal || "") : ""
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap
            }
        }
    }

    Text { Layout.fillWidth: true; visible: Boolean(page.currentCycle); text: "每日任务"; typography: Typography.Subtitle }
    ColumnLayout {
        Layout.fillWidth: true
        visible: Boolean(page.currentCycle)
        spacing: 10
        Repeater {
            model: page.currentCycle ? (page.currentCycle.days || []) : []
            delegate: Frame {
                Layout.fillWidth: true
                leftPadding: 18; rightPadding: 18; topPadding: 14; bottomPadding: 14
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "第 " + String(modelData.day || (index + 1)) + " 天"
                            typography: Typography.BodyStrong
                            color: Theme.currentTheme.colors.primaryColor
                        }
                        Text {
                            Layout.fillWidth: true
                            text: String(modelData.focus || "")
                            typography: Typography.BodyStrong
                            wrapMode: Text.Wrap
                        }
                        Text {
                            text: String((modelData.tasks || []).length) + " 项"
                            typography: Typography.Caption
                            color: Theme.currentTheme.colors.textSecondaryColor
                        }
                    }
                    Repeater {
                        model: modelData.tasks || []
                        delegate: RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Icon { name: "ic_fluent_circle_12_regular"; size: 12; color: Theme.currentTheme.colors.textSecondaryColor }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    Layout.fillWidth: true
                                    text: String(modelData.title || "未命名任务")
                                    typography: Typography.Body
                                    wrapMode: Text.Wrap
                                }
                                Text {
                                    Layout.fillWidth: true
                                    visible: Boolean(modelData.meta)
                                    text: String(modelData.meta || "")
                                    typography: Typography.Caption
                                    color: Theme.currentTheme.colors.textSecondaryColor
                                    wrapMode: Text.Wrap
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        visible: Boolean(page.currentCycle && page.currentCycle.reviewPrompt)
        leftPadding: 20; rightPadding: 20; topPadding: 16; bottomPadding: 16
        ColumnLayout {
            anchors.fill: parent
            spacing: 8
            Text { text: "周期复盘"; typography: Typography.Subtitle }
            Text {
                Layout.fillWidth: true
                text: page.currentCycle ? String(page.currentCycle.reviewPrompt || "") : ""
                typography: Typography.Body
                wrapMode: Text.Wrap
            }
            Text {
                Layout.fillWidth: true
                visible: Boolean(page.longPlan.nextCycleInstruction)
                text: String(page.longPlan.nextCycleInstruction || "")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        visible: page.hasPlan
        leftPadding: 20; rightPadding: 20; topPadding: 16; bottomPadding: 16
        ColumnLayout {
            anchors.fill: parent
            spacing: 8
            Text { text: "导入内容"; typography: Typography.Subtitle }
            RowLayout {
                Layout.fillWidth: true
                Text { text: String((page.plan.tasks || []).length) + " 个独立任务"; typography: Typography.Body }
                Text { text: String((page.plan.groups || []).length) + " 个任务流"; typography: Typography.Body }
                Text { text: String((page.plan.projects || []).length) + " 个项目"; typography: Typography.Body }
                Item { Layout.fillWidth: true }
            }
            Repeater {
                model: page.plan.projects || []
                delegate: Text {
                    Layout.fillWidth: true
                    text: "项目：" + String(modelData.name || modelData.title || "未命名项目")
                    typography: Typography.Caption
                    color: Theme.currentTheme.colors.textSecondaryColor
                    wrapMode: Text.Wrap
                }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        visible: page.hasPlan
        Button {
            text: "放弃计划"
            icon.name: "ic_fluent_delete_20_regular"
            onClicked: { Backend.abandonLongPlan(); page.returnToWorkspace() }
        }
        Item { Layout.fillWidth: true }
        Button {
            text: "开启当前长期计划"
            highlighted: true
            icon.name: "ic_fluent_play_20_regular"
            enabled: Boolean(page.plan.longPlan)
            onClicked: { Backend.startLongPlan(JSON.stringify(page.plan)); page.returnToWorkspace() }
        }
    }
}
