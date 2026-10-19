import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("项目")
    wrapperWidth: 1040
    horizontalPadding: 32
    contentSpacing: 18
    LayoutTokens { id: ui }
    readonly property bool compactLayout: width - horizontalPadding * 2 < ui.compactBreakpoint
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
        pendingDeleteName = String(item.name || I18n.t("未命名项目"))
        deleteDialog.open()
    }
    Component.onCompleted: reload()
    Connections { target: Backend; function onProjectsChanged() { page.reload() } }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 12
        Text { Layout.fillWidth: true; text: I18n.t("用里程碑管理长期目标，并从准备页启动一次攻坚"); typography: Typography.Body; color: ui.mutedText; wrapMode: Text.Wrap }
        RowLayout { Layout.fillWidth: true; spacing: 12
            TextField { Layout.fillWidth: true; placeholderText: I18n.t("搜索项目"); onTextChanged: page.query = text }
            Button { text: I18n.t("新建项目"); highlighted: true; icon.name: "ic_fluent_add_20_regular"; onClicked: page.openEditor(-1) }
        }
    }
    RowLayout { Layout.fillWidth: true
                Layout.topMargin: 4
                Text { Layout.fillWidth: true
                text: I18n.t("所有项目")
                typography: Typography.BodyStrong }
                Text { text: page.visibleProjects.length + I18n.t(" 个")
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
                Layout.preferredHeight: page.compactLayout ? 132 : 100
                leftPadding: 16
                rightPadding: 16
                topPadding: 12
                bottomPadding: 12
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8
                    RowLayout { Layout.fillWidth: true; spacing: 12
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
                text: String(modelData.name || I18n.t("未命名项目"))
                typography: Typography.BodyStrong
                elide: Text.ElideRight }
                        Text { Layout.fillWidth: true
                text: String(modelData.desc || modelData.description || I18n.t("暂无描述"))
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                elide: Text.ElideRight }
                        ProgressBar { Layout.fillWidth: true
                Layout.maximumWidth: 360
                from: 0
                to: 1
                value: Number(modelData.progress || 0) }
                    }
                    Text { visible: !page.compactLayout; text: Math.round(Number(modelData.progress || 0) * 100) + "%  ·  " + (modelData.milestones || []).length + I18n.t(" 个里程碑")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                    Item { Layout.fillWidth: page.compactLayout; visible: page.compactLayout }
                    Button { flat: true
                text: I18n.t("编辑")
                icon.name: "ic_fluent_edit_20_regular"; onClicked: page.openEditor(Number(modelData.id)) }
                    Button { text: I18n.t("启动准备")
                highlighted: true
                icon.name: "ic_fluent_play_20_regular"; onClicked: page.openPrep(Number(modelData.id)) }
                    ToolButton { icon.name: "ic_fluent_delete_20_regular"
                ToolTip.text: I18n.t("删除")
                ToolTip.visible: hovered; onClicked: page.requestDelete(modelData) }
                    }
                    Text { visible: page.compactLayout; Layout.fillWidth: true; text: Math.round(Number(modelData.progress || 0) * 100) + "%  ·  " + (modelData.milestones || []).length + I18n.t(" 个里程碑"); typography: Typography.Caption; color: ui.mutedText }
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
                text: page.projects.length ? I18n.t("没有匹配的项目") : I18n.t("还没有项目")
                typography: Typography.BodyStrong }
            Text { Layout.alignment: Qt.AlignHCenter
                text: I18n.t("创建项目并拆分可以逐步完成的里程碑")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }

    DeleteConfirmDialog {
        id: deleteDialog
        itemType: I18n.t("项目")
        itemName: page.pendingDeleteName
        onDeleteConfirmed: {
            if (page.pendingDeleteId >= 0)
                Backend.deleteProject(page.pendingDeleteId)
            page.pendingDeleteId = -1
            page.pendingDeleteName = ""
        }
    }
}

