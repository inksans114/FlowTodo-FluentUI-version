import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "项目启动准备"
    wrapperWidth: 880
    horizontalPadding: 34
    property double projectId: Backend.activeProjectId
    property var project: ({})
    property string goal: ""
    property real estimatedHours: 2
    property bool docsReady: true
    property bool shieldEnabled: false
    property bool whiteNoiseEnabled: false
    property bool pageReady: false
    ListModel { id: milestoneModel }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        var projects = []
        try { projects = JSON.parse(Backend.projectsJson) } catch (error) {}
        project = projects.find(function(item) { return Number(item.id) === projectId }) || {name: "项目", milestones: []}
        goal = project.desc || ""
        milestoneModel.clear()
        ;(project.milestones || []).forEach(function(item, index) { milestoneModel.append({title: item.title || item.name || ("里程碑 " + (index + 1)), done: Boolean(item.done), selected: !item.done}) })
        if (!milestoneModel.count) milestoneModel.append({title: "暂无里程碑", done: false, selected: true})
    }
    function start() {
        var targets = []
        for (var i = 0; i < milestoneModel.count; i++) { var item = milestoneModel.get(i); if (item.selected) targets.push(item.title) }
        if (!targets.length) return
        if (Backend.startProjectById(projectId, JSON.stringify({estimatedHours: estimatedHours, targetMilestones: targets, goal: goal, docsReady: docsReady, shieldEnabled: shieldEnabled, whiteNoiseEnabled: whiteNoiseEnabled, guardWhitelist: Backend.getSetting("focusGuardWhitelist", [])}))) {
            var router = nav(); if (router) router.push(Qt.resolvedUrl("FocusSessionNative.qml"), {mode: "project", titleText: project.name || "项目专注"})
        }
    }
    Component.onCompleted: { pageReady = true; load() }
    onProjectIdChanged: if (pageReady) load()
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: "返回项目"
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { text: "返回项目"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }
    SettingCard {
        Layout.fillWidth: true
        title: project.name || "项目"
        description: "选择本次专注要推进的里程碑"
        icon.name: "ic_fluent_board_20_regular"
        ColumnLayout {
            Layout.fillWidth: true
            TextField { Layout.fillWidth: true
                text: page.goal
                placeholderText: "本次专注目标"
                onTextChanged: page.goal = text }
            Repeater {
                model: milestoneModel
                delegate: CheckBox { Layout.fillWidth: true
                text: model.title + (model.done ? "（已完成）" : "")
                checked: model.selected
                onClicked: milestoneModel.setProperty(index, "selected", checked) }
            }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "启动前检查"
        description: "这些选项会随本次项目专注一起保存"
        icon.name: "ic_fluent_shield_checkmark_20_regular"
        ColumnLayout { Layout.fillWidth: true
                spacing: 4
            CheckBox { text: "项目资料已就绪"
                checked: page.docsReady
                onClicked: page.docsReady = checked }
            RowLayout { Layout.fillWidth: true
                CheckBox { Layout.fillWidth: true
                text: "启用沉浸拦截模式"
                checked: page.shieldEnabled
                onClicked: page.shieldEnabled = checked }
                Button { text: "应用允许列表"
                icon.name: "ic_fluent_shield_checkmark_20_regular"
                onClicked: { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("FocusGuardApps.qml"), {returnLabel: "返回专注准备"}) } }
            }
            CheckBox { text: "启动白噪音"
                checked: page.whiteNoiseEnabled
                onClicked: page.whiteNoiseEnabled = checked }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "本次专注时长"
        description: "总时长会平均分配到选中的里程碑"
        icon.name: "ic_fluent_timer_20_regular"
        RowLayout {
            Layout.fillWidth: true
            Slider { Layout.fillWidth: true
                from: 0.5
                to: 12
                stepSize: 0.5
                value: page.estimatedHours
                onMoved: page.estimatedHours = value }
            Text { text: page.estimatedHours.toFixed(1) + " 小时"
                typography: Typography.Caption }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Button { text: "返回"
                onClicked: { var router = page.nav(); if (router) router.pop() } }
        Button { text: "开始项目专注"
                highlighted: true
                icon.name: "ic_fluent_play_20_regular"
                onClicked: page.start() }
    }
}

