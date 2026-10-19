import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "GroupsWorkspace"
    title: I18n.t("任务流")
    wrapperWidth: 1040
    horizontalPadding: 32
    contentSpacing: 18
    LayoutTokens { id: ui }
    readonly property bool compactLayout: width - horizontalPadding * 2 < ui.compactBreakpoint
    property var groups: []
    property string query: ""
    property bool returnToFocus: false
    property double pendingDeleteId: -1
    property string pendingDeleteName: ""
    property var visibleGroups: groups.filter(function(item) { return !query.trim().length || String(item.name || "").toLowerCase().indexOf(query.trim().toLowerCase()) >= 0 })
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function reload() { try { groups = JSON.parse(Backend.groupsJson) } catch (error) { groups = [] } }
    function openEditor(id) { Backend.setActiveGroupId(id); var router = nav(); if (router) router.push(Qt.resolvedUrl("GroupEditorPage.qml"), {groupId: id}) }
    function openPrep(id) { Backend.setActiveGroupId(id); var router = nav(); if (router) router.push(Qt.resolvedUrl("GroupPrepWorkspace.qml"), {groupId: id}) }
    function requestDelete(item) {
        pendingDeleteId = Number(item.id)
        pendingDeleteName = String(item.name || I18n.t("未命名任务流"))
        deleteDialog.open()
    }
    Component.onCompleted: reload()
    Connections { target: Backend; function onGroupsChanged() { page.reload() } }

    extraHeaderItems: JourneyButton {
        objectName: "returnToFocus"
        visible: page.returnToFocus
        text: I18n.t("返回专注")
        flat: true
        icon.name: "ic_fluent_arrow_left_20_regular"
        onClicked: { var router = page.nav(); if (router) router.pop() }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 12
        Text { Layout.fillWidth: true; text: I18n.t("将重复工作整理成可以随时启动的步骤"); typography: Typography.Body; color: ui.mutedText; wrapMode: Text.Wrap }
        RowLayout { Layout.fillWidth: true; spacing: 12
            TextField { Layout.fillWidth: true; placeholderText: I18n.t("搜索任务流"); onTextChanged: page.query = text }
            Button { text: I18n.t("流程图"); icon.name: "ic_fluent_flow_20_regular"; onClicked: Backend.openTaskRelations("") }
            Button { text: I18n.t("新建"); highlighted: true; icon.name: "ic_fluent_add_20_regular"; onClicked: page.openEditor(-1) }
        }
    }
    RowLayout { Layout.fillWidth: true
                Layout.topMargin: 6
                Text { Layout.fillWidth: true
                text: I18n.t("所有任务流")
                typography: Typography.BodyStrong }
                Text { text: page.visibleGroups.length + I18n.t(" 个")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4
        Repeater {
            model: page.visibleGroups
            delegate: Frame {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: page.compactLayout ? 118 : 90
                leftPadding: 16
                rightPadding: 16
                topPadding: 12
                bottomPadding: 12
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8
                    RowLayout { Layout.fillWidth: true; spacing: 12
                    Rectangle { width: 38
                height: 38
                radius: 6
                color: Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.12)
                Icon { anchors.centerIn: parent; name: "ic_fluent_flow_20_regular"; size: 21
                color: Theme.currentTheme.colors.primaryColor } }
                    ColumnLayout { Layout.fillWidth: true
                spacing: 2
                Text { Layout.fillWidth: true
                text: String(modelData.name || I18n.t("未命名任务流"))
                typography: Typography.BodyStrong
                elide: Text.ElideRight }
                Text { Layout.fillWidth: true
                text: String(modelData.description || I18n.t("暂无描述"))
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                elide: Text.ElideRight } }
                    Text { visible: !page.compactLayout; text: (modelData.steps || []).length + I18n.t(" 步 · ") + (modelData.steps || []).reduce(function(sum, step) { return sum + Number(step.duration || step.time || 0) }, 0) + I18n.t(" 分钟")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                    Item { Layout.fillWidth: page.compactLayout; visible: page.compactLayout }
                    TaskRelationsButton { nodeKey: "group:" + modelData.id }
                    Button { flat: true
                text: I18n.t("编辑")
                icon.name: "ic_fluent_edit_20_regular"; onClicked: page.openEditor(Number(modelData.id)) }
                    Button { text: I18n.t("准备启动")
                highlighted: true
                icon.name: "ic_fluent_play_20_regular"; onClicked: page.openPrep(Number(modelData.id)) }
                    ToolButton { icon.name: "ic_fluent_delete_20_regular"
                ToolTip.text: I18n.t("删除")
                ToolTip.visible: hovered; onClicked: page.requestDelete(modelData) }
                    }
                    Text { visible: page.compactLayout; Layout.fillWidth: true; text: (modelData.steps || []).length + I18n.t(" 步 · ") + (modelData.steps || []).reduce(function(sum, step) { return sum + Number(step.duration || step.time || 0) }, 0) + I18n.t(" 分钟"); typography: Typography.Caption; color: ui.mutedText }
                }
            }
        }
    }
    Item { Layout.fillWidth: true
                Layout.preferredHeight: 180
                visible: page.visibleGroups.length === 0
                ColumnLayout { anchors.centerIn: parent
                spacing: 6
                Icon { Layout.alignment: Qt.AlignHCenter; name: "ic_fluent_flow_20_regular"; size: 38
                color: Theme.currentTheme.colors.textSecondaryColor }
                Text { Layout.alignment: Qt.AlignHCenter
                text: I18n.t("没有任务流")
                typography: Typography.BodyStrong }
                Text { Layout.alignment: Qt.AlignHCenter
                text: I18n.t("创建一个可重复使用的专注流程")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } } }

    DeleteConfirmDialog {
        id: deleteDialog
        itemType: I18n.t("任务流")
        itemName: page.pendingDeleteName
        onDeleteConfirmed: {
            if (page.pendingDeleteId >= 0)
                Backend.deleteGroup(page.pendingDeleteId)
            page.pendingDeleteId = -1
            page.pendingDeleteName = ""
        }
    }
}

