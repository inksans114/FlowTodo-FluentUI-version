import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "项目"
    wrapperWidth: 980
    horizontalPadding: 36
    contentSpacing: 12
    property var projects: []
    property string query: ""
    property double pendingDeleteId: -1
    property string pendingDeleteName: ""
    property var visibleProjects: projects.filter(function(item) { var q = query.trim().toLowerCase(); return !q.length || (String(item.name || "") + " " + String(item.desc || item.description || "")).toLowerCase().indexOf(q) >= 0 })
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function reload() { try { projects = JSON.parse(Backend.projectsJson) } catch (error) { projects = [] } }
    function openEditor(id) { Backend.setActiveProjectId(id); var router = nav(); if (router) router.push(Qt.resolvedUrl("ProjectEditorNative.qml"), {projectId: id}) }
    function openPrep(id) { Backend.setActiveProjectId(id); var router = nav(); if (router) router.push(Qt.resolvedUrl("ProjectPrepNative.qml"), {projectId: id}) }
    function requestDelete(item) {
        pendingDeleteId = Number(item.id)
        pendingDeleteName = String(item.name || "未命名项目")
        deleteDialog.open()
    }
    Component.onCompleted: reload()
    Connections { target: Backend; function onProjectsChanged() { page.reload() } }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Text { Layout.fillWidth: true
                text: "用里程碑管理长期目标，并从准备页启动一次攻坚"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
        TextField { Layout.preferredWidth: 230; placeholderText: "搜索项目"; onTextChanged: page.query = text }
        Button { text: "新建项目"
                highlighted: true
                icon.name: "ic_fluent_add_20_regular"; onClicked: page.openEditor(-1) }
    }
    RowLayout { Layout.fillWidth: true
                Layout.topMargin: 4
                Text { Layout.fillWidth: true
                text: "所有项目"
                typography: Typography.BodyStrong }
                Text { text: page.visibleProjects.length + " 个"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4
        Repeater {
            model: page.visibleProjects
            delegate: Frame {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 92
                leftPadding: 14
                rightPadding: 8
                topPadding: 10
                bottomPadding: 10
                RowLayout {
                    anchors.fill: parent
                    spacing: 12
                    Rectangle { width: 40
                height: 40
                radius: 6
                color: Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.12)
                Icon { anchors.centerIn: parent; name: "ic_fluent_board_20_regular"; size: 22
                color: Theme.currentTheme.colors.primaryColor } }
                    ColumnLayout {
                        Layout.fillWidth: true
                spacing: 3
                        Text { Layout.fillWidth: true
                text: String(modelData.name || "未命名项目")
                typography: Typography.BodyStrong
                elide: Text.ElideRight }
                        Text { Layout.fillWidth: true
                text: String(modelData.desc || modelData.description || "暂无描述")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                elide: Text.ElideRight }
                        ProgressBar { Layout.fillWidth: true
                Layout.maximumWidth: 360
                from: 0
                to: 1
                value: Number(modelData.progress || 0) }
                    }
                    Text { text: Math.round(Number(modelData.progress || 0) * 100) + "%  ·  " + (modelData.milestones || []).length + " 个里程碑"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                    Button { flat: true
                text: "编辑"
                icon.name: "ic_fluent_edit_20_regular"; onClicked: page.openEditor(Number(modelData.id)) }
                    Button { text: "启动准备"
                highlighted: true
                icon.name: "ic_fluent_play_20_regular"; onClicked: page.openPrep(Number(modelData.id)) }
                    ToolButton { icon.name: "ic_fluent_delete_20_regular"
                ToolTip.text: "删除"
                ToolTip.visible: hovered; onClicked: page.requestDelete(modelData) }
                }
            }
        }
    }
    Item {
        Layout.fillWidth: true
                Layout.preferredHeight: 180
                visible: page.visibleProjects.length === 0
        ColumnLayout { anchors.centerIn: parent
                spacing: 6
            Icon { Layout.alignment: Qt.AlignHCenter; name: "ic_fluent_board_20_regular"; size: 38
                color: Theme.currentTheme.colors.textSecondaryColor }
            Text { Layout.alignment: Qt.AlignHCenter
                text: page.projects.length ? "没有匹配的项目" : "还没有项目"
                typography: Typography.BodyStrong }
            Text { Layout.alignment: Qt.AlignHCenter
                text: "创建项目并拆分可以逐步完成的里程碑"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }

    DeleteConfirmDialog {
        id: deleteDialog
        itemType: "项目"
        itemName: page.pendingDeleteName
        onDeleteConfirmed: {
            if (page.pendingDeleteId >= 0)
                Backend.deleteProject(page.pendingDeleteId)
            page.pendingDeleteId = -1
            page.pendingDeleteName = ""
        }
    }
}

