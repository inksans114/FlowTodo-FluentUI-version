import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: projectId < 0 ? "新建项目" : "编辑项目"
    wrapperWidth: 860
    horizontalPadding: 34
    property double projectId: Backend.activeProjectId
    property var sourceProject: ({})
    property bool pageReady: false
    ListModel { id: milestoneModel }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        var projects = []
        try { projects = JSON.parse(Backend.projectsJson) } catch (error) {}
        sourceProject = projects.find(function(item) { return Number(item.id) === projectId }) || {name: "", desc: "", milestones: []}
        nameField.text = sourceProject.name || ""
        descField.text = sourceProject.desc || sourceProject.description || ""
        milestoneModel.clear()
        ;(sourceProject.milestones || []).forEach(function(item) { milestoneModel.append({title: item.title || item.name || "", done: Boolean(item.done)}) })
        if (!milestoneModel.count) milestoneModel.append({title: "", done: false})
    }
    function save() {
        var milestones = []
        for (var i = 0; i < milestoneModel.count; i++) {
            var item = milestoneModel.get(i)
            if (String(item.title).trim().length) milestones.push({title: String(item.title).trim(), done: Boolean(item.done)})
        }
        if (!nameField.text.trim().length || !milestones.length) return
        var done = milestones.filter(function(item) { return item.done }).length
        var payload = {id: projectId < 0 ? Date.now() : projectId, name: nameField.text.trim(), desc: descField.text.trim(), progress: milestones.length ? done / milestones.length : 0, taskCount: milestones.length, milestones: milestones}
        if (projectId < 0) Backend.addProject(JSON.stringify(payload)); else Backend.updateProject(JSON.stringify(payload))
        var router = nav(); if (router) router.pop()
    }
    Component.onCompleted: { pageReady = true; load() }
    onProjectIdChanged: if (pageReady) load()
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: "返回项目"
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { text: "返回项目"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }
    SettingCard {
        Layout.fillWidth: true
        title: "项目信息"
        description: "项目名称和目标说明"
        icon.name: "ic_fluent_board_20_regular"
        ColumnLayout {
            Layout.fillWidth: true
            TextField { id: nameField
                Layout.fillWidth: true
                placeholderText: "项目名称" }
            TextField { id: descField
                Layout.fillWidth: true
                placeholderText: "目标描述（可选）" }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "里程碑"
        description: "完成专注后会自动更新项目进度"
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
                placeholderText: "里程碑名称"
                onTextChanged: if (index < milestoneModel.count) milestoneModel.setProperty(index, "title", text) }
                    ToolButton { icon.name: "ic_fluent_dismiss_20_regular"
                enabled: milestoneModel.count > 1
                onClicked: milestoneModel.remove(index) }
                }
            }
            Button { text: "添加里程碑"
                icon.name: "ic_fluent_add_20_regular"
                onClicked: milestoneModel.append({title: "", done: false}) }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Button { text: "取消"
                onClicked: { var router = page.nav(); if (router) router.pop() } }
        Button { text: "保存项目"
                highlighted: true
                icon.name: "ic_fluent_save_20_regular"
                onClicked: page.save() }
    }
}

