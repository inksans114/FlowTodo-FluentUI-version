import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: groupId < 0 ? "新建任务流" : "编辑任务流"
    wrapperWidth: 860
    horizontalPadding: 34
    property double groupId: Backend.activeGroupId
    property var sourceGroup: ({})
    property bool pageReady: false
    ListModel { id: stepsModel }

    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        var groups = []
        try { groups = JSON.parse(Backend.groupsJson) } catch (error) {}
        sourceGroup = groups.find(function(item) { return Number(item.id) === groupId }) || {name: "", description: "", steps: []}
        nameField.text = sourceGroup.name || ""
        descriptionField.text = sourceGroup.description || ""
        stepsModel.clear()
        ;(sourceGroup.steps || []).forEach(function(step) { stepsModel.append({title: step.name || step.title || "", duration: Number(step.duration || step.time || 25), type: step.type || "focus"}) })
        if (!stepsModel.count) stepsModel.append({title: "", duration: 25, type: "focus"})
    }
    function save() {
        var steps = []
        for (var i = 0; i < stepsModel.count; i++) {
            var step = stepsModel.get(i)
            if (String(step.title).trim().length) steps.push({name: String(step.title).trim(), duration: Number(step.duration), type: String(step.type || "focus")})
        }
        if (!nameField.text.trim().length || !steps.length) return
        var payload = {id: groupId < 0 ? Date.now() : groupId, name: nameField.text.trim(), description: descriptionField.text.trim(), steps: steps, theme: sourceGroup.theme || "primary"}
        if (groupId < 0) Backend.addGroup(JSON.stringify(payload)); else Backend.updateGroup(JSON.stringify(payload))
        var router = nav(); if (router) router.pop()
    }
    Component.onCompleted: { pageReady = true; load() }
    onGroupIdChanged: if (pageReady) load()

    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: "返回任务流"
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { text: "返回任务流"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }

    SettingCard { Layout.fillWidth: true
                title: "任务流信息"
                description: "为这套流程命名并说明用途"
                icon.name: "ic_fluent_info_20_regular"
        ColumnLayout { Layout.fillWidth: true
            TextField { id: nameField
                Layout.fillWidth: true
                placeholderText: "任务流名称" }
            TextField { id: descriptionField
                Layout.fillWidth: true
                placeholderText: "描述（可选）" }
        }
    }
    SettingCard { Layout.fillWidth: true
                title: "流程步骤"
                description: "调整顺序、名称和每一步专注时长"
                icon.name: "ic_fluent_list_20_regular"
        ColumnLayout { Layout.fillWidth: true
                spacing: 8
            Repeater { model: stepsModel
                delegate: RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_re_order_dots_vertical_20_regular"
                ToolTip.text: "拖动排序"
                ToolTip.visible: hovered }
                TextField { Layout.fillWidth: true
                placeholderText: "步骤名称"
                text: model.title
                onTextChanged: if (index < stepsModel.count) stepsModel.setProperty(index, "title", text) }
                SpinBox { from: 1
                to: 240
                value: model.duration
                stepSize: 5
                onValueModified: stepsModel.setProperty(index, "duration", value) }
                ToolButton { icon.name: "ic_fluent_dismiss_20_regular"
                enabled: stepsModel.count > 1
                onClicked: stepsModel.remove(index) }
            } }
            Button { text: "添加步骤"
                icon.name: "ic_fluent_add_20_regular"
                onClicked: stepsModel.append({title: "", duration: 25, type: "focus"}) }
        }
    }
    RowLayout { Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Button { text: "取消"
                onClicked: { var router = page.nav(); if (router) router.pop() } }
        Button { text: "保存任务流"
                highlighted: true
                icon.name: "ic_fluent_save_20_regular"
                onClicked: page.save() }
    }
}

