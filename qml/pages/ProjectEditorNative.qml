import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    title: projectId < 0 ? I18n.t("新建项目") : I18n.t("编辑项目")
    wrapperWidth: 860
    horizontalPadding: 34
    property double projectId: Backend.activeProjectId
    property var sourceProject: ({})
    property bool pageReady: false
    ListModel { id: milestoneModel }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        JSON.parse(Backend.taskRelationsJson)
        var projects = []
        try { projects = JSON.parse(Backend.projectsJson) } catch (error) {}
        sourceProject = projects.find(function(item) { return Number(item.id) === projectId }) || {name: "", desc: "", milestones: []}
        nameField.text = sourceProject.name || ""
        descField.text = sourceProject.desc || sourceProject.description || ""
        milestoneModel.clear()
        ;(sourceProject.milestones || []).forEach(function(item) { milestoneModel.append({title: item.title || item.name || "", done: Boolean(item.done), relationId: item.relationId || Backend.newRelationId(), original: JSON.stringify(item)}) })
        if (!milestoneModel.count) milestoneModel.append({title: "", done: false, relationId: Backend.newRelationId(), original: "{}"})
    }
    function save(openGraph, childId) {
        var milestones = []
        for (var i = 0; i < milestoneModel.count; i++) {
            var item = milestoneModel.get(i)
            if (String(item.title).trim().length) milestones.push(Object.assign({}, JSON.parse(item.original || "{}"), {title: String(item.title).trim(), done: Boolean(item.done), relationId: item.relationId}))
        }
        if (!nameField.text.trim().length || !milestones.length) return
        var done = milestones.filter(function(item) { return item.done }).length
        var payload = Object.assign({}, sourceProject, {id: projectId < 0 ? Date.now() : projectId, name: nameField.text.trim(), desc: descField.text.trim(), progress: milestones.length ? done / milestones.length : 0, taskCount: milestones.length, milestones: milestones})
        if (projectId < 0) Backend.addProject(JSON.stringify(payload)); else Backend.updateProject(JSON.stringify(payload))
        if (openGraph) { projectId = payload.id; Backend.openTaskRelations(childId ? "milestone:" + payload.id + ":" + childId : "project:" + payload.id) }
        else { var router = nav(); if (router) router.pop() }
    }
    Component.onCompleted: { pageReady = true; load() }
    onProjectIdChanged: if (pageReady) load()
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: I18n.t("返回项目")
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { visible: false; text: I18n.t("返回项目")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true }
                Button { id: editorMore; text: I18n.t("更多"); flat: true; icon.name: "ic_fluent_more_horizontal_20_regular"; onClicked: editorMenu.open(); QuietMenu { id: editorMenu; parent: editorMore; MenuItem { text: I18n.t("关联任务"); onTriggered: page.save(true, "") } } } }
    SettingCard {
        Layout.fillWidth: true
        title: I18n.t("项目信息")
        icon.name: "ic_fluent_board_20_regular"
        ColumnLayout {
            Layout.fillWidth: true
            TextField { id: nameField
                Layout.fillWidth: true
                placeholderText: I18n.t("项目名称") }
            TextField { id: descField
                Layout.fillWidth: true
                placeholderText: I18n.t("目标描述（可选）") }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: I18n.t("里程碑")
        icon.name: "ic_fluent_flag_20_regular"
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: milestoneModel
                delegate: RowLayout {
                    Layout.fillWidth: true
                    CheckBox { checked: model.done
                onClicked: milestoneModel.setProperty(index, "done", checked) }
                    TextField { Layout.fillWidth: true
                text: model.title
                placeholderText: I18n.t("里程碑名称")
                onTextChanged: if (index < milestoneModel.count) milestoneModel.setProperty(index, "title", text) }
                    ToolButton { icon.name: "ic_fluent_link_20_regular"; ToolTip.text: I18n.t("关联这个里程碑"); ToolTip.visible: hovered; onClicked: page.save(true, model.relationId) }
                    ToolButton { icon.name: "ic_fluent_dismiss_20_regular"
                enabled: milestoneModel.count > 1
                onClicked: milestoneModel.remove(index) }
                }
            }
            Button { text: I18n.t("添加里程碑")
                icon.name: "ic_fluent_add_20_regular"
                onClicked: milestoneModel.append({title: "", done: false, relationId: Backend.newRelationId(), original: "{}"}) }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Button { text: I18n.t("取消")
                onClicked: { var router = page.nav(); if (router) router.pop() } }
        Button { text: I18n.t("保存项目")
                highlighted: true
                icon.name: "ic_fluent_save_20_regular"
                onClicked: page.save() }
    }
}

