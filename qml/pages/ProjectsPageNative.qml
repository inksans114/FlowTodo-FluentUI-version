import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "项目"
    wrapperWidth: 1040
    horizontalPadding: 34
    property var projects: []
    property string query: ""
    property double pendingDeleteId: -1
    property string pendingDeleteName: ""
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function reload() { try { projects = JSON.parse(Backend.projectsJson) } catch (error) { projects = [] } }
    function openEditor(id) { var router = nav(); if (router) router.push(Qt.resolvedUrl("ProjectEditorNative.qml"), {projectId: id}) }
    function openPrep(id) { var router = nav(); if (router) router.push(Qt.resolvedUrl("ProjectPrepNative.qml"), {projectId: id}) }
    function requestDelete(item) { pendingDeleteId = Number(item.id); pendingDeleteName = String(item.name || "未命名项目"); deleteDialog.open() }
    property var filteredProjects: projects.filter(function(project) { var q = query.trim().toLowerCase(); return !q.length || String(project.name || "").toLowerCase().indexOf(q) >= 0 })
    Component.onCompleted: reload()
    Connections { target: Backend; function onProjectsChanged() { page.reload() } }
    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: "用里程碑推进长期目标，专注时会同步项目进度"; typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor }
        TextField { Layout.preferredWidth: 220; placeholderText: "搜索项目"; onTextChanged: page.query = text }
        Button { text: "新建项目"; highlighted: true; icon.name: "ic_fluent_add_20_regular"; onClicked: page.openEditor(-1) }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: width > 760 ? 2 : 1
        columnSpacing: 14
        rowSpacing: 14
        Repeater {
            model: page.filteredProjects
            delegate: Frame {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 214
                leftPadding: 20
                rightPadding: 18
                topPadding: 18
                bottomPadding: 16
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Icon { name: "ic_fluent_board_20_regular"; size: 24; color: Theme.currentTheme.colors.primaryColor }
                        Text { Layout.fillWidth: true; text: String(modelData.name || "未命名项目"); typography: Typography.Subtitle }
                        ToolButton { icon.name: "ic_fluent_delete_20_regular"; onClicked: page.requestDelete(modelData) }
                    }
                    Text { Layout.fillWidth: true; text: String(modelData.desc || modelData.description || "暂无描述"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap; maximumLineCount: 2 }
                    ProgressBar { Layout.fillWidth: true; from: 0; to: 1; value: Number(modelData.progress || 0) }
                    Text { text: Math.round(Number(modelData.progress || 0) * 100) + "% · " + (modelData.milestones || []).filter(function(item) { return item.done }).length + "/" + (modelData.milestones || []).length + " 个里程碑"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        Layout.fillWidth: true
                        Button { Layout.fillWidth: true; text: "编辑"; icon.name: "ic_fluent_edit_20_regular"; onClicked: page.openEditor(Number(modelData.id)) }
                        Button { Layout.fillWidth: true; text: "启动准备"; highlighted: true; icon.name: "ic_fluent_play_20_regular"; onClicked: page.openPrep(Number(modelData.id)) }
                    }
                }
            }
        }
    }
    Frame {
        Layout.fillWidth: true
        Layout.preferredHeight: 150
        visible: page.filteredProjects.length === 0
        ColumnLayout {
            anchors.centerIn: parent
            spacing: 8
            Icon { Layout.alignment: Qt.AlignHCenter; name: "ic_fluent_board_20_regular"; size: 34; color: Theme.currentTheme.colors.textSecondaryColor }
            Text { Layout.alignment: Qt.AlignHCenter; text: "还没有项目"; typography: Typography.BodyStrong }
            Text { Layout.alignment: Qt.AlignHCenter; text: "创建项目并拆分里程碑"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
    DeleteConfirmDialog {
        id: deleteDialog
        itemType: "项目"
        itemName: page.pendingDeleteName
        onDeleteConfirmed: {
            if (page.pendingDeleteId >= 0) Backend.deleteProject(page.pendingDeleteId)
            page.pendingDeleteId = -1
            page.pendingDeleteName = ""
        }
    }
}
