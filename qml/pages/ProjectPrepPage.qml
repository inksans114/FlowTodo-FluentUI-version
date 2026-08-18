import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "项目启动准备"
    wrapperWidth: 880
    horizontalPadding: 34
    property int projectId: -1
    property var project: ({})
    property string goal: ""
    property real estimatedHours: 2
    ListModel { id: milestoneModel }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { var projects = []; try { projects = JSON.parse(Backend.projectsJson) } catch (error) {}; project = projects.find(function(item) { return Number(item.id) === projectId }) || ({name: "项目", milestones: []}); goal = project.desc || ""; milestoneModel.clear(); (project.milestones || []).forEach(function(item, index) { milestoneModel.append({title: item.title || item.name || ("里程碑 " + (index + 1)), done: Boolean(item.done), selected: !item.done}) }); if (!milestoneModel.count) milestoneModel.append({title: "暂无里程碑", done: false, selected: true}) }
    function start() { var targets = []; var indexes = []; for (var i = 0; i < milestoneModel.count; i++) { var item = milestoneModel.get(i); if (item.selected) { targets.push(item.title); indexes.push(i) } }; if (!targets.length) return; var options = {estimatedHours: estimatedHours}; Backend.startProjectById(projectId, JSON.stringify(options)); var router = nav(); if (router) router.push(Qt.resolvedUrl("FocusSessionPage.qml"), {mode: "project", titleText: project.name || "项目专注"}) }
    Component.onCompleted: load()
    SettingCard { Layout.fillWidth: true; title: project.name || "项目"; description: "选择本次专注要推进的里程碑"; icon.name: "ic_fluent_board_20_regular"; ColumnLayout { Layout.fillWidth: true; TextField { Layout.fillWidth: true; text: page.goal; placeholderText: "本次专注目标"; onTextChanged: page.goal = text }; Repeater { model: milestoneModel; delegate: CheckBox { Layout.fillWidth: true; text: model.title + (model.done ? "（已完成）" : ""); checked: model.selected; onClicked: milestoneModel.setProperty(index, "selected", checked) } } } }
    SettingCard { Layout.fillWidth: true; title: "本次专注时长"; description: "总时长会平均分配到选中的里程碑"; icon.name: "ic_fluent_timer_20_regular"; RowLayout { Layout.fillWidth: true; Slider { Layout.fillWidth: true; from: 0.5; to: 12; stepSize: 0.5; value: page.estimatedHours; onMoved: page.estimatedHours = value }; Text { text: page.estimatedHours.toFixed(1) + " 小时"; typography: Typography.Caption } } }
    RowLayout { Layout.fillWidth: true; Item { Layout.fillWidth: true }; Button { text: "返回"; onClicked: { var router = page.nav(); if (router) router.pop() } }; Button { text: "开始项目专注"; highlighted: true; icon.name: "ic_fluent_play_20_regular"; onClicked: page.start() } }
}
