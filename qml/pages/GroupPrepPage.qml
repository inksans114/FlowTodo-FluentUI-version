import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "任务流启动准备"
    wrapperWidth: 880
    horizontalPadding: 34
    property int groupId: -1
    property var group: ({})
    property bool includeBreaks: true
    property int breakMinutes: 5
    property bool shieldEnabled: false
    property bool whiteNoiseEnabled: false
    property bool docsReady: true
    property string wallpaperTitle: ""
    ListModel { id: prepSteps }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        var groups = []; try { groups = JSON.parse(Backend.groupsJson) } catch (error) {}
        group = groups.find(function(item) { return Number(item.id) === groupId }) || ({name: "任务流", steps: []})
        prepSteps.clear()
        ;(group.steps || []).forEach(function(step) { prepSteps.append({title: step.name || step.title || "步骤", duration: Number(step.duration || step.time || 25), type: step.type || "focus"}) })
    }
    function start() {
        var options = {includeBreaks: includeBreaks, breakMinutes: breakMinutes, shieldEnabled: shieldEnabled, whiteNoiseEnabled: whiteNoiseEnabled, docsReady: docsReady, wallpaperTitle: wallpaperTitle}
        var tasks = []
        for (var i = 0; i < prepSteps.count; i++) {
            var step = prepSteps.get(i)
            tasks.push({title: step.title, time: step.duration, type: step.type})
        }
        if (Backend.startPreparedGroup(groupId, JSON.stringify(tasks), JSON.stringify(options))) {
            var router = nav(); if (router) router.push(Qt.resolvedUrl("FocusSessionNative.qml"), {mode: "group", titleText: group.name || "任务流专注"})
        }
    }
    Component.onCompleted: load()
    SettingCard { Layout.fillWidth: true; title: group.name || "任务流"; description: group.description || "准备步骤后开始专注"; icon.name: "ic_fluent_flow_20_regular"
        ColumnLayout { Layout.fillWidth: true; spacing: 6
            Repeater { model: prepSteps; delegate: Frame { Layout.fillWidth: true; Layout.preferredHeight: 48; leftPadding: 10; rightPadding: 14
                RowLayout { anchors.fill: parent
                    ToolButton { icon.name: "ic_fluent_chevron_up_20_regular"; enabled: index > 0; onClicked: prepSteps.move(index, index - 1, 1) }
                    ToolButton { icon.name: "ic_fluent_chevron_down_20_regular"; enabled: index < prepSteps.count - 1; onClicked: prepSteps.move(index, index + 1, 1) }
                    Text { Layout.fillWidth: true; text: (index + 1) + ".  " + String(model.title || "步骤"); typography: Typography.Body }
                    Text { text: Number(model.duration || 25) + " 分钟"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                }
            } }
        }
    }
    SettingCard { Layout.fillWidth: true; title: "启动选项"; description: "在开始前确认休息、拦截和声音环境"; icon.name: "ic_fluent_settings_20_regular"
        RowLayout { Layout.fillWidth: true
            Switch { id: breaks; checked: page.includeBreaks; onClicked: page.includeBreaks = checked }
            Text { text: "步骤之间加入休息"; typography: Typography.Body; Layout.fillWidth: true }
            SpinBox { from: 1; to: 60; value: page.breakMinutes; enabled: page.includeBreaks; onValueModified: page.breakMinutes = value }
            Text { text: "分钟"; typography: Typography.Caption }
        }
        RowLayout { Layout.fillWidth: true
            Switch { checked: page.shieldEnabled; onClicked: page.shieldEnabled = checked }
            Text { Layout.fillWidth: true; text: "沉浸拦截模式"; typography: Typography.Body }
            Text { text: page.shieldEnabled ? "已启用" : "关闭"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        }
        RowLayout { Layout.fillWidth: true
            Switch { checked: page.whiteNoiseEnabled; onClicked: page.whiteNoiseEnabled = checked }
            Text { Layout.fillWidth: true; text: "白噪音"; typography: Typography.Body }
            Text { text: page.whiteNoiseEnabled ? "启动时播放" : "不播放"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        }
        RowLayout { Layout.fillWidth: true
            CheckBox { checked: page.docsReady; onClicked: page.docsReady = checked }
            Text { Layout.fillWidth: true; text: "我已准备好本次步骤所需资料"; typography: Typography.Body }
        }
    }
    RowLayout { Layout.fillWidth: true; Item { Layout.fillWidth: true }
        Button { text: "返回"; onClicked: { var router = page.nav(); if (router) router.pop() } }
        Button { text: "开始任务流"; highlighted: true; icon.name: "ic_fluent_play_20_regular"; onClicked: page.start() }
    }
}
