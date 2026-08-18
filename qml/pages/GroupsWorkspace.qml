import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "任务流"
    wrapperWidth: 980
    horizontalPadding: 36
    contentSpacing: 12
    property var groups: []
    property string query: ""
    property double pendingDeleteId: -1
    property string pendingDeleteName: ""
    property var visibleGroups: groups.filter(function(item) { return !query.trim().length || String(item.name || "").toLowerCase().indexOf(query.trim().toLowerCase()) >= 0 })
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function reload() { try { groups = JSON.parse(Backend.groupsJson) } catch (error) { groups = [] } }
    function openEditor(id) { Backend.setActiveGroupId(id); var router = nav(); if (router) router.push(Qt.resolvedUrl("GroupEditorPage.qml"), {groupId: id}) }
    function openPrep(id) { Backend.setActiveGroupId(id); var router = nav(); if (router) router.push(Qt.resolvedUrl("GroupPrepWorkspace.qml"), {groupId: id}) }
    function requestDelete(item) {
        pendingDeleteId = Number(item.id)
        pendingDeleteName = String(item.name || "未命名任务流")
        deleteDialog.open()
    }
    Component.onCompleted: reload()
    Connections { target: Backend; function onGroupsChanged() { page.reload() } }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Text { Layout.fillWidth: true
                text: "将重复工作整理成可以随时启动的步骤"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
        TextField { Layout.preferredWidth: 220; placeholderText: "搜索任务流"; onTextChanged: page.query = text }
        Button { text: "新建"
                highlighted: true
                icon.name: "ic_fluent_add_20_regular"; onClicked: page.openEditor(-1) }
    }
    RowLayout { Layout.fillWidth: true
                Layout.topMargin: 6
                Text { Layout.fillWidth: true
                text: "所有任务流"
                typography: Typography.BodyStrong }
                Text { text: page.visibleGroups.length + " 个"
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
                Layout.preferredHeight: 82
                leftPadding: 14
                rightPadding: 8
                topPadding: 10
                bottomPadding: 10
                RowLayout {
                    anchors.fill: parent
                    spacing: 12
                    Rectangle { width: 38
                height: 38
                radius: 6
                color: Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.12)
                Icon { anchors.centerIn: parent; name: "ic_fluent_flow_20_regular"; size: 21
                color: Theme.currentTheme.colors.primaryColor } }
                    ColumnLayout { Layout.fillWidth: true
                spacing: 2
                Text { Layout.fillWidth: true
                text: String(modelData.name || "未命名任务流")
                typography: Typography.BodyStrong
                elide: Text.ElideRight }
                Text { Layout.fillWidth: true
                text: String(modelData.description || "暂无描述")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                elide: Text.ElideRight } }
                    Text { text: (modelData.steps || []).length + " 步 · " + (modelData.steps || []).reduce(function(sum, step) { return sum + Number(step.duration || step.time || 0) }, 0) + " 分钟"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                    Button { flat: true
                text: "编辑"
                icon.name: "ic_fluent_edit_20_regular"; onClicked: page.openEditor(Number(modelData.id)) }
                    Button { text: "准备启动"
                highlighted: true
                icon.name: "ic_fluent_play_20_regular"; onClicked: page.openPrep(Number(modelData.id)) }
                    ToolButton { icon.name: "ic_fluent_delete_20_regular"
                ToolTip.text: "删除"
                ToolTip.visible: hovered; onClicked: page.requestDelete(modelData) }
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
                text: "没有任务流"
                typography: Typography.BodyStrong }
                Text { Layout.alignment: Qt.AlignHCenter
                text: "创建一个可重复使用的专注流程"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } } }

    DeleteConfirmDialog {
        id: deleteDialog
        itemType: "任务流"
        itemName: page.pendingDeleteName
        onDeleteConfirmed: {
            if (page.pendingDeleteId >= 0)
                Backend.deleteGroup(page.pendingDeleteId)
            page.pendingDeleteId = -1
            page.pendingDeleteName = ""
        }
    }
}

