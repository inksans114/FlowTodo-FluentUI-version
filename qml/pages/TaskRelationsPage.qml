import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

Page {
    id: page
    objectName: "taskRelationsPage"
    property string focusNodeKey: ""
    property bool showListConnect: false
    property var graphData: ({nodes: [], edges: [], collections: []})
    readonly property var selectedNode: graphData.nodes.find(function(n) { return n.key === canvas.selectedKey }) || ({})
    readonly property var nodeChoices: graphData.nodes.map(function(n) { return {label: n.title + " · " + n.collectionTitle, key: n.key} })
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { graphData = JSON.parse(Backend.taskRelationsJson) }
    function openEditor() {
        var n = selectedNode, router = nav()
        if (!router || !n.key) return
        if (n.kind === "task") router.push(Qt.resolvedUrl("TaskEditorPage.qml"), {taskId: Number(n.itemId)})
        else if (n.kind === "group" || n.kind === "step") router.push(Qt.resolvedUrl("GroupEditorPage.qml"), {groupId: Number(n.itemId)})
        else router.push(Qt.resolvedUrl("ProjectEditorNative.qml"), {projectId: Number(n.itemId)})
    }
    Component.onCompleted: { load(); canvas.selectedKey = focusNodeKey; locate.restart() }
    onFocusNodeKeyChanged: { canvas.selectedKey = focusNodeKey; locate.restart() }
    Timer { id: locate; interval: 120; onTriggered: canvas.centerOn(page.focusNodeKey) }
    Connections { target: Backend; function onTaskRelationsChanged() { page.load() } }
    background: Rectangle { color: Theme.currentTheme.colors.backgroundColor }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 12
        RowLayout {
            Layout.fillWidth: true
            ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"; ToolTip.text: I18n.t("返回"); ToolTip.visible: hovered; onClicked: { var r = page.nav(); if (r) r.pop() } }
            Text { Layout.fillWidth: true; text: I18n.t("任务流程图"); typography: Typography.Title }
            InlineHelp { helpText: I18n.t("步骤顺序自动生成竖向箭头，可在编辑任务流中调整。\n拖动任务右侧圆点可添加关联。\n接着做：结束后提示下一项。\n一起完成：确认时可同时完成。\n循环、交叉和重复嵌套会被阻止。") }
            ToolButton {
                id: graphMore
                objectName: "relationGraphMore"
                icon.name: "ic_fluent_more_horizontal_20_regular"
                Accessible.name: I18n.t("更多")
                ToolTip.text: I18n.t("更多"); ToolTip.visible: hovered
                onClicked: graphMenu.open()
                QuietMenu {
                    id: graphMenu
                    parent: graphMore
                    MenuItem { objectName: "relationListAction"; text: I18n.t("用列表连接"); checkable: true; checked: page.showListConnect; onTriggered: page.showListConnect = !page.showListConnect }
                    MenuItem { text: I18n.t("整理布局"); onTriggered: Backend.resetRelationLayout() }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            TextField { Layout.fillWidth: true; placeholderText: I18n.t("查找任务"); onTextChanged: canvas.query = text; Accessible.name: I18n.t("查找任务或集合") }
            ComboBox { id: relationType; Layout.preferredWidth: 132; model: [I18n.t("接着做 →"), I18n.t("一起完成 ↔")]; onActivated: canvas.linkType = currentIndex === 0 ? "next" : "together"; Accessible.name: I18n.t("连线类型") }
            ToolButton { icon.name: "ic_fluent_dismiss_20_regular"; visible: canvas.pendingSource.length > 0; ToolTip.text: I18n.t("取消连线"); ToolTip.visible: hovered; Accessible.name: I18n.t("取消连线"); onClicked: canvas.pendingSource = "" }
            ToolButton { visible: canvas.selectedEdge.length > 0; icon.name: "ic_fluent_delete_20_regular"; ToolTip.text: I18n.t("删除连线"); ToolTip.visible: hovered; Accessible.name: I18n.t("删除连线"); onClicked: Backend.disconnectTaskRelation(canvas.selectedEdge) }
        }
        Frame {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 200
            padding: 0
            contentItem: TaskGraphCanvas {
                id: canvas
                graphData: page.graphData
                onConnectRequested: function(sourceKey, targetKey, kind) { Backend.connectTaskRelation(sourceKey, targetKey, kind) }
                onMoveRequested: function(key, x, y) { Backend.moveRelationNode(key, x, y) }
                onCollectionMoveRequested: function(key, x, y) { if (!Backend.moveRelationCollection(key, x, y)) page.load() }
                onDeleteRequested: function(edgeId) { Backend.disconnectTaskRelation(edgeId) }
            }
        }
        RowLayout {
            visible: Boolean(page.selectedNode.key)
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true; spacing: 3
                Text { Layout.fillWidth: true; text: page.selectedNode.title || I18n.t("选择一个任务查看或启动"); typography: Typography.BodyStrong; elide: Text.ElideRight }
            }
            ToolButton { icon.name: "ic_fluent_edit_20_regular"; ToolTip.text: I18n.t("编辑"); ToolTip.visible: hovered; Accessible.name: I18n.t("编辑"); onClicked: page.openEditor() }
            JourneyButton { text: page.selectedNode.done ? I18n.t("重新打开") : I18n.t("完成"); enabled: Boolean(page.selectedNode.key); onClicked: { if (page.selectedNode.done) Backend.reopenRelationNode(page.selectedNode.key); else Backend.requestRelationCompletion(page.selectedNode.key) } }
            JourneyButton { text: I18n.t("开始"); highlighted: true; icon.name: "ic_fluent_play_20_regular"; enabled: Boolean(page.selectedNode.key) && !page.selectedNode.done && !page.selectedNode.isBreak; onClicked: Backend.prepareFlowNode(page.selectedNode.key) }
        }
        RowLayout {
            objectName: "relationListConnect"
            visible: page.showListConnect
            Layout.fillWidth: true; spacing: 8
            ComboBox { id: sourceChoice; Layout.fillWidth: true; Layout.minimumWidth: 0; model: page.nodeChoices; textRole: "label"; Accessible.name: I18n.t("起点任务") }
            Text { text: relationType.currentIndex === 0 ? "→" : "↔" }
            ComboBox { id: targetChoice; Layout.fillWidth: true; Layout.minimumWidth: 0; model: page.nodeChoices; textRole: "label"; currentIndex: page.nodeChoices.length > 1 ? 1 : 0; Accessible.name: I18n.t("目标任务") }
            JourneyButton { text: I18n.t("连接"); enabled: page.nodeChoices.length > 1; onClicked: Backend.connectTaskRelation(page.nodeChoices[sourceChoice.currentIndex].key, page.nodeChoices[targetChoice.currentIndex].key, canvas.linkType) }
        }
    }
}
