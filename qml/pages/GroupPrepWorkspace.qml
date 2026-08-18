import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "任务流启动准备"
    wrapperWidth: 860
    horizontalPadding: 36
    contentSpacing: 10
    property double groupId: Backend.activeGroupId
    property var group: ({})
    property bool includeBreaks: true
    property int breakMinutes: 5
    property bool shieldEnabled: false
    property bool whiteNoiseEnabled: false
    property bool pageReady: false
    ListModel { id: stepModel }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        var groups = []
        try { groups = JSON.parse(Backend.groupsJson) } catch (error) { groups = [] }
        group = groups.find(function(item) { return Number(item.id) === groupId }) || ({name: "任务流", steps: []})
        stepModel.clear()
        for (var i = 0; i < (group.steps || []).length; i++) { var step = group.steps[i]; stepModel.append({title: step.name || step.title || "步骤", duration: Number(step.duration || step.time || 25), type: step.type || "focus"}) }
    }
    function totalMinutes() { var total = 0; for (var i = 0; i < stepModel.count; i++) total += Number(stepModel.get(i).duration || 0); if (includeBreaks) total += Math.max(0, stepModel.count - 1) * breakMinutes; return total }
    function start() {
        var tasks = []
        for (var i = 0; i < stepModel.count; i++) { var step = stepModel.get(i); tasks.push({title: step.title, time: step.duration, type: step.type}) }
        var options = {includeBreaks: includeBreaks, breakMinutes: breakMinutes, shieldEnabled: shieldEnabled, whiteNoiseEnabled: whiteNoiseEnabled, guardWhitelist: Backend.getSetting("focusGuardWhitelist", [])}
        if (Backend.startPreparedGroup(groupId, JSON.stringify(tasks), JSON.stringify(options))) { var router = nav(); if (router) router.push(Qt.resolvedUrl("FocusSessionNative.qml"), {mode: "group", titleText: group.name || "任务流专注"}) }
    }
    Component.onCompleted: { pageReady = true; load() }
    onGroupIdChanged: if (pageReady) load()
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: "返回任务流"
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { text: "返回任务流"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }
    RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: String(page.group.name || "任务流")
                typography: Typography.Subtitle }
                Text { text: page.totalMinutes() + " 分钟"
                typography: Typography.BodyStrong } }
    Text { Layout.fillWidth: true
                text: String(page.group.description || "确认执行队列后开始专注。")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
    Text { text: "执行队列"
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
                Text { text: Number(model.duration) + " 分钟"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
        } }
    }
    Text { Layout.topMargin: 6
                text: "专注环境"
                typography: Typography.BodyStrong }
    Frame { Layout.fillWidth: true
                leftPadding: 16
                rightPadding: 16
                topPadding: 10
                bottomPadding: 10
        ColumnLayout { anchors.fill: parent
                spacing: 4
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "步骤之间加入休息"
                typography: Typography.Body }
                Switch { checked: page.includeBreaks
                onClicked: page.includeBreaks = checked }
                SpinBox { from: 1
                to: 60
                value: page.breakMinutes
                enabled: page.includeBreaks
                onValueModified: page.breakMinutes = value }
                Text { text: "分钟"
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "沉浸拦截模式"
                typography: Typography.Body }
                Switch { checked: page.shieldEnabled
                onClicked: page.shieldEnabled = checked }
                Button { text: "应用允许列表"
                icon.name: "ic_fluent_shield_checkmark_20_regular"
                onClicked: { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("FocusGuardApps.qml"), {returnLabel: "返回专注准备"}) } } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: "白噪音"
                typography: Typography.Body }
                Switch { checked: page.whiteNoiseEnabled
                onClicked: page.whiteNoiseEnabled = checked } }
        }
    }
    RowLayout { Layout.fillWidth: true
                Layout.topMargin: 8
                Text { Layout.fillWidth: true
                text: "总计 " + page.totalMinutes() + " 分钟"
                typography: Typography.BodyStrong }
                Button { text: "返回"
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Button { text: "开始任务流"
                highlighted: true
                icon.name: "ic_fluent_play_20_regular"
                onClicked: page.start() } }
}


