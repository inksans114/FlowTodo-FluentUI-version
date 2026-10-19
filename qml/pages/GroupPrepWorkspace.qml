import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "GroupPrepWorkspace"
    title: I18n.t("任务流启动准备")
    wrapperWidth: 860
    horizontalPadding: 36
    contentSpacing: 10
    property double groupId: Backend.activeGroupId
    property var group: ({})
    property bool includeBreaks: true
    property int breakMinutes: Number(Backend.getSetting("breakDuration", 5))
    property bool shieldEnabled: false
    property bool whiteNoiseEnabled: false
    property bool immersiveEnabled: false
    property bool pageReady: false
    ListModel { id: stepModel }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        var groups = []
        try { groups = JSON.parse(Backend.groupsJson) } catch (error) { groups = [] }
        group = groups.find(function(item) { return Number(item.id) === groupId }) || ({name: I18n.t("任务流"), steps: []})
        stepModel.clear()
        var steps = JSON.parse(Backend.getGroupSteps(groupId))
        for (var i = 0; i < steps.length; i++) { var step = steps[i]; stepModel.append({title: step.title, duration: Number(step.time || 25), type: step.type || "focus", relationId: step.relationId}) }
    }
    function totalMinutes() { var total = 0; for (var i = 0; i < stepModel.count; i++) { total += Number(stepModel.get(i).duration || 0); if (includeBreaks && i + 1 < stepModel.count && stepModel.get(i).type !== "break" && stepModel.get(i + 1).type !== "break") total += breakMinutes } return total }
    function start() {
        var tasks = []
        for (var i = 0; i < stepModel.count; i++) { var step = stepModel.get(i); tasks.push({title: step.title, time: step.duration, type: step.type, relationId: step.relationId}) }
        var options = {includeBreaks: includeBreaks, breakMinutes: breakMinutes, shieldEnabled: shieldEnabled, whiteNoiseEnabled: whiteNoiseEnabled, guardWhitelist: Backend.getSetting("focusGuardWhitelist", [])}
        if (Backend.startPreparedGroup(groupId, JSON.stringify(tasks), JSON.stringify(options)) && page.immersiveEnabled) {
            Backend.enterFocusStudio(String(Backend.getSetting("focusScene", "tree")))
        }
    }
    Component.onCompleted: { pageReady = true; load() }
    onGroupIdChanged: if (pageReady) load()
    Connections { target: Backend; function onGroupsChanged() { page.load() } function onTasksChanged() { page.load() } }
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: I18n.t("返回任务流")
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { text: I18n.t("返回任务流")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true }
                TaskRelationsButton { nodeKey: "group:" + page.groupId } }
    RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: String(page.group.name || I18n.t("任务流"))
                typography: Typography.Subtitle }
                Text { text: page.totalMinutes() + I18n.t(" 分钟")
                typography: Typography.BodyStrong } }
    Text { Layout.fillWidth: true
                text: String(page.group.description || I18n.t("确认执行队列后开始专注。"))
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
    Text { Layout.fillWidth: true
                visible: ((page.group.launchApps || page.group.applications || []).length || 0) > 0
                text: {
                    var apps = page.group.launchApps || page.group.applications || []
                    var names = []
                    for (var i = 0; i < apps.length; i++) {
                        var value = typeof apps[i] === "string" ? apps[i] : (apps[i].path || "")
                        if (String(value).length) names.push(String(value).split("/").pop().split("\\").pop())
                    }
                    return I18n.t("启动时自动打开：") + names.join("、")
                }
                typography: Typography.Caption
                color: Theme.currentTheme.colors.primaryColor
                elide: Text.ElideMiddle }
    Text { text: I18n.t("执行队列")
                typography: Typography.BodyStrong }
    ColumnLayout { Layout.fillWidth: true
                spacing: 4
        Repeater { model: stepModel
                delegate: Frame {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            leftPadding: 10
            rightPadding: 10
            RowLayout { anchors.fill: parent
                ToolButton { icon.name: "ic_fluent_chevron_up_20_regular"
                enabled: index > 0
                onClicked: stepModel.move(index, index - 1, 1) }
                ToolButton { icon.name: "ic_fluent_chevron_down_20_regular"
                enabled: index < stepModel.count - 1
                onClicked: stepModel.move(index, index + 1, 1) }
                Text { Layout.fillWidth: true
                text: (index + 1) + ". " + String(model.title)
                typography: Typography.BodyStrong
                elide: Text.ElideRight }
                Text { text: Number(model.duration) + I18n.t(" 分钟")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
        } }
    }
    Text { Layout.topMargin: 6
                text: I18n.t("专注环境")
                typography: Typography.BodyStrong }
    Frame { Layout.fillWidth: true
                leftPadding: 16
                rightPadding: 16
                topPadding: 10
                bottomPadding: 10
        ColumnLayout { anchors.fill: parent
                spacing: 4
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("开始后进入沉浸场景"); typography: Typography.Body }
                Switch { objectName: "groupImmersiveToggle"; checked: page.immersiveEnabled; onClicked: page.immersiveEnabled = checked; Accessible.name: I18n.t("开始后进入沉浸场景") }
            }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("步骤之间加入休息")
                typography: Typography.Body }
                Switch { checked: page.includeBreaks
                onClicked: page.includeBreaks = checked }
                SpinBox { from: 1
                to: 60
                value: page.breakMinutes
                enabled: page.includeBreaks
                onValueModified: page.breakMinutes = value }
                Text { text: I18n.t("分钟")
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("沉浸拦截模式")
                typography: Typography.Body }
                Switch { checked: page.shieldEnabled
                onClicked: page.shieldEnabled = checked }
                Button { text: I18n.t("应用允许列表")
                icon.name: "ic_fluent_shield_checkmark_20_regular"
                onClicked: { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("FocusGuardApps.qml"), {returnLabel: I18n.t("返回专注准备")}) } } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("白噪音")
                typography: Typography.Body }
                Switch { checked: page.whiteNoiseEnabled
                onClicked: page.whiteNoiseEnabled = checked } }
        }
    }
    RowLayout { Layout.fillWidth: true
                Layout.topMargin: 8
                Text { Layout.fillWidth: true
                text: I18n.t("总计 ") + page.totalMinutes() + I18n.t(" 分钟")
                typography: Typography.BodyStrong }
                Button { text: I18n.t("返回")
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Button { text: I18n.t("开始任务流")
                enabled: stepModel.count > 0 && !JSON.parse(Backend.focusSessionJson || "{}").running
                highlighted: true
                icon.name: "ic_fluent_play_20_regular"
                onClicked: page.start() } }
}


