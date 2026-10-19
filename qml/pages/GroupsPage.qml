import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("任务流")
    wrapperWidth: 1040
    horizontalPadding: 34
    property var groups: []
    property string query: ""
    property double pendingDeleteId: -1
    property string pendingDeleteName: ""

    function nav() {
        var item = page
        while (item) {
            if (item.objectName === "MainNavigationView") return item
            item = item.parent
        }
        return null
    }
    function reload() {
        try { groups = JSON.parse(Backend.groupsJson) } catch (error) { groups = [] }
    }
    function openEditor(id) {
        var router = nav()
        if (router) router.push(Qt.resolvedUrl("GroupEditorPage.qml"), {groupId: id})
    }
    function openPrep(id) {
        var router = nav()
        if (router) router.push(Qt.resolvedUrl("GroupPrepPage.qml"), {groupId: id})
    }
    function requestDelete(item) {
        pendingDeleteId = Number(item.id)
        pendingDeleteName = String(item.name || I18n.t("未命名任务流"))
        deleteDialog.open()
    }
    property var filteredGroups: groups.filter(function(group) {
        var q = query.trim().toLowerCase()
        return !q.length || String(group.name || "").toLowerCase().indexOf(q) >= 0
    })

    Component.onCompleted: reload()
    Connections { target: Backend; function onGroupsChanged() { page.reload() } }

    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: I18n.t("把重复的专注步骤整理成一键启动流程"); typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor }
        TextField { Layout.preferredWidth: 220; placeholderText: I18n.t("搜索任务流"); onTextChanged: page.query = text }
        Button { text: I18n.t("新建任务流"); highlighted: true; icon.name: "ic_fluent_add_20_regular"; onClicked: page.openEditor(-1) }
    }

    GridLayout {
        Layout.fillWidth: true
        columns: width > 760 ? 2 : 1
        columnSpacing: 14
        rowSpacing: 14
        Repeater {
            model: page.filteredGroups
            delegate: Frame {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 196
                leftPadding: 20; rightPadding: 18; topPadding: 18; bottomPadding: 16
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Icon { name: "ic_fluent_flow_20_regular"; size: 24; color: Theme.currentTheme.colors.primaryColor }
                        Text { Layout.fillWidth: true; text: String(modelData.name || I18n.t("未命名任务流")); typography: Typography.Subtitle }
                        ToolButton { icon.name: "ic_fluent_delete_20_regular"; ToolTip.text: I18n.t("删除任务流"); ToolTip.visible: hovered; onClicked: page.requestDelete(modelData) }
                    }
                    Text { Layout.fillWidth: true; text: String(modelData.description || I18n.t("暂无描述")); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap; maximumLineCount: 2 }
                    Text {
                        Layout.fillWidth: true
                        text: (modelData.steps || []).length + I18n.t(" 个步骤 · 约 ") + (modelData.steps || []).reduce(function(total, step) { return total + Number(step.duration || step.time || 0) }, 0) + I18n.t(" 分钟")
                        typography: Typography.Body
                    }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        Layout.fillWidth: true
                        Button { Layout.fillWidth: true; text: I18n.t("编辑"); icon.name: "ic_fluent_edit_20_regular"; onClicked: page.openEditor(Number(modelData.id)) }
                        Button { Layout.fillWidth: true; text: I18n.t("启动准备"); highlighted: true; icon.name: "ic_fluent_play_20_regular"; onClicked: page.openPrep(Number(modelData.id)) }
                    }
                }
            }
        }
    }

    Frame {
        Layout.fillWidth: true; Layout.preferredHeight: 150; visible: page.filteredGroups.length === 0
        ColumnLayout { anchors.centerIn: parent; spacing: 8
            Icon { Layout.alignment: Qt.AlignHCenter; name: "ic_fluent_flow_20_regular"; size: 34; color: Theme.currentTheme.colors.textSecondaryColor }
            Text { Layout.alignment: Qt.AlignHCenter; text: page.groups.length ? I18n.t("没有匹配的任务流") : I18n.t("还没有任务流"); typography: Typography.BodyStrong }
            Text { Layout.alignment: Qt.AlignHCenter; text: I18n.t("创建一个流程，把常用步骤组合起来"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }

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
