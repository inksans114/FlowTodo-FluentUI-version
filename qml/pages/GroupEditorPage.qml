import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "groupEditorPage"
    title: groupId < 0 ? I18n.t("新建任务流") : I18n.t("编辑任务流")
    wrapperWidth: 860
    horizontalPadding: 34
    property double groupId: Backend.activeGroupId
    property var sourceGroup: ({})
    property bool pageReady: false
    property string draggedStepId: ""
    property string validationError: ""
    property var existingTasks: []
    property var selectedTaskIds: []
    ListModel { id: stepsModel }
    ListModel { id: launchAppsModel }

    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function reorderStep(relationId, pointerY) {
        var from = -1
        for (var i = 0; i < stepsModel.count; i++) {
            if (stepsModel.get(i).relationId === relationId) { from = i; break }
        }
        if (from < 0) return
        var to = from
        // Cross the next row's centre before moving, so a stationary pointer
        // cannot repeatedly swap two rows after the layout updates.
        while (to + 1 < stepsModel.count) {
            var next = stepsRepeater.itemAt(to + 1)
            if (!next || pointerY <= next.y + next.height / 2) break
            to++
        }
        while (to > 0) {
            var previous = stepsRepeater.itemAt(to - 1)
            if (!previous || pointerY >= previous.y + previous.height / 2) break
            to--
        }
        if (to !== from) stepsModel.move(from, to, 1)
    }
    function load() {
        JSON.parse(Backend.taskRelationsJson)
        var groups = []
        try { groups = JSON.parse(Backend.groupsJson) } catch (error) {}
        sourceGroup = groups.find(function(item) { return Number(item.id) === groupId }) || {name: "", description: "", steps: []}
        nameField.text = sourceGroup.name || ""
        descriptionField.text = sourceGroup.description || ""
        stepsModel.clear()
        var todos = JSON.parse(Backend.tasksJson)
        ;(sourceGroup.steps || []).forEach(function(step) { var todo = todos.find(function(t) { return Number(t.id) === Number(step.taskId) }); stepsModel.append({title: todo ? todo.title : step.name || step.title || "", duration: Number(step.duration || step.time || 25), type: step.type || "focus", relationId: step.relationId || Backend.newRelationId(), original: JSON.stringify(step)}) })
        if (!stepsModel.count) stepsModel.append({title: "", duration: 25, type: "focus", relationId: Backend.newRelationId(), original: "{}"})
        launchAppsModel.clear()
        var configuredApps = sourceGroup.launchApps || sourceGroup.applications || []
        if (!Array.isArray(configuredApps)) configuredApps = [configuredApps]
        configuredApps.forEach(function(item) {
            var path = typeof item === "string" ? item : (item && item.path ? item.path : "")
            if (String(path).trim().length) launchAppsModel.append({path: String(path)})
        })
    }
    function save(openGraph, childId) {
        var linkedStepId = String(childId || "")
        var steps = []
        for (var i = 0; i < stepsModel.count; i++) {
            var step = stepsModel.get(i)
            if (String(step.title).trim().length) steps.push(Object.assign({}, JSON.parse(step.original || "{}"), {name: String(step.title).trim(), duration: Number(step.duration), type: String(step.type || "focus"), relationId: step.relationId}))
        }
        if (!steps.length || (linkedStepId && !steps.some(function(step) { return step.relationId === linkedStepId }))) {
            validationError = openGraph ? I18n.t("先填写步骤名称，再关联任务。") : I18n.t("请至少填写一个步骤名称。")
            Backend.messageRequested("warning", I18n.t("请填写步骤名称"), validationError)
            return false
        }
        var groupName = nameField.text.trim()
        if (!groupName.length) {
            if (openGraph) groupName = I18n.t("未命名任务流")
            else {
                validationError = I18n.t("请填写任务流名称。")
                nameField.forceActiveFocus()
                Backend.messageRequested("warning", I18n.t("任务流未保存"), validationError)
                return false
            }
        }
        validationError = ""
        var launchApps = []
        for (var j = 0; j < launchAppsModel.count; j++) {
            var appPath = String(launchAppsModel.get(j).path || "").trim()
            if (appPath.length && launchApps.indexOf(appPath) < 0) launchApps.push(appPath)
        }
        var payload = Object.assign({}, sourceGroup, {id: groupId < 0 ? Date.now() : groupId, name: groupName, description: descriptionField.text.trim(), steps: steps, launchApps: launchApps, theme: sourceGroup.theme || "primary"})
        if (!Backend.saveGroupJson(JSON.stringify(payload))) return false
        if (openGraph) {
            groupId = payload.id
            var linked = steps.find(function(s) { return s.relationId === linkedStepId })
            var nodeKey = linked && linked.taskId !== undefined ? "task:" + linked.taskId : linkedStepId ? "step:" + payload.id + ":" + linkedStepId : "group:" + payload.id
            Qt.callLater(function() { Backend.openTaskRelations(nodeKey) })
        }
        else { var router = nav(); if (router) router.pop() }
        return true
    }
    Component.onCompleted: { pageReady = true; load() }
    onGroupIdChanged: if (pageReady) load()

    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: I18n.t("返回任务流")
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { visible: false; text: I18n.t("返回任务流")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true }
                Button { id: editorMore; text: I18n.t("更多"); flat: true; icon.name: "ic_fluent_more_horizontal_20_regular"; onClicked: editorMenu.open(); QuietMenu { id: editorMenu; parent: editorMore; MenuItem { text: I18n.t("关联任务"); onTriggered: page.save(true, "") } } } }

    SettingCard { Layout.fillWidth: true
                title: I18n.t("任务流信息")
                icon.name: "ic_fluent_info_20_regular"
        ColumnLayout { Layout.fillWidth: true
            TextField { id: nameField
                objectName: "groupNameField"
                Layout.fillWidth: true
                placeholderText: I18n.t("任务流名称")
                onTextEdited: page.validationError = "" }
            TextField { id: descriptionField
                Layout.fillWidth: true
                placeholderText: I18n.t("描述（可选）") }
        }
    }
    SettingCard { Layout.fillWidth: true
                title: I18n.t("流程步骤")
                icon.name: "ic_fluent_list_20_regular"
        ColumnLayout { id: stepsColumn; Layout.fillWidth: true
                spacing: 8
            Repeater { id: stepsRepeater; model: stepsModel
                delegate: RowLayout { Layout.fillWidth: true
                opacity: page.draggedStepId === model.relationId ? 0.65 : 1
                ToolButton { objectName: "stepDragHandle_" + index
                icon.name: "ic_fluent_re_order_dots_vertical_20_regular"
                Accessible.name: I18n.t("拖动排序")
                ToolTip.text: I18n.t("拖动排序")
                ToolTip.visible: stepDragArea.containsMouse && !stepDragArea.pressed
                MouseArea {
                    id: stepDragArea
                    anchors.fill: parent
                    z: 2
                    hoverEnabled: true
                    preventStealing: true
                    cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    property string stepId: ""
                    property real pressY: 0
                    property bool sorting: false
                    onPressed: function(mouse) {
                        stepId = model.relationId
                        pressY = mapToItem(stepsColumn, mouse.x, mouse.y).y
                        sorting = false
                    }
                    onPositionChanged: function(mouse) {
                        if (!pressed) return
                        var pointerY = mapToItem(stepsColumn, mouse.x, mouse.y).y
                        if (!sorting && Math.abs(pointerY - pressY) < 6) return
                        sorting = true
                        page.draggedStepId = stepId
                        page.reorderStep(stepId, pointerY)
                    }
                    onReleased: { sorting = false; page.draggedStepId = "" }
                    onCanceled: { sorting = false; page.draggedStepId = "" }
                } }
                TextField { Layout.fillWidth: true
                objectName: "groupStepTitle_" + index
                placeholderText: I18n.t("步骤名称")
                text: model.title
                readOnly: JSON.parse(model.original || "{}").taskId !== undefined
                onTextEdited: { page.validationError = ""; if (index < stepsModel.count) stepsModel.setProperty(index, "title", text) } }
                SpinBox { from: 1
                to: 240
                value: model.duration
                stepSize: 5
                onValueModified: stepsModel.setProperty(index, "duration", value) }
                ToolButton { objectName: "groupStepRelation_" + index; icon.name: "ic_fluent_link_20_regular"; Accessible.name: I18n.t("关联这个步骤"); ToolTip.text: I18n.t("关联这个步骤"); ToolTip.visible: hovered; onClicked: page.save(true, model.relationId) }
                ToolButton { icon.name: "ic_fluent_dismiss_20_regular"
                enabled: stepsModel.count > 1
                onClicked: stepsModel.remove(index) }
            } }
            Button { text: I18n.t("添加步骤")
                icon.name: "ic_fluent_add_20_regular"
                onClicked: stepsModel.append({title: "", duration: 25, type: "focus", relationId: Backend.newRelationId(), original: "{}"}) }
            Button { objectName: "addExistingTasks"; text: I18n.t("加入已有待办"); icon.name: "ic_fluent_link_20_regular"; onClicked: {
                var used = []
                for (var i = 0; i < stepsModel.count; i++) { var source = JSON.parse(stepsModel.get(i).original || "{}"); if (source.taskId !== undefined) used.push(Number(source.taskId)) }
                JSON.parse(Backend.groupsJson).filter(function(g) { return Number(g.id) !== page.groupId }).forEach(function(g) { (g.steps || []).forEach(function(s) { if (s.taskId !== undefined) used.push(Number(s.taskId)) }) })
                page.existingTasks = JSON.parse(Backend.tasksJson).filter(function(t) { return !t.done && !t.archived && used.indexOf(Number(t.id)) < 0 })
                page.selectedTaskIds = []; taskPicker.open()
            } }
            Text { objectName: "groupEditorError"; visible: page.validationError.length > 0; Layout.fillWidth: true; text: page.validationError; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor; Accessible.role: Accessible.AlertMessage }
        }
    }
    SettingCard { Layout.fillWidth: true
                title: I18n.t("自动打开软件")
                icon.name: "ic_fluent_apps_20_regular"
        ColumnLayout { Layout.fillWidth: true; spacing: 8
            Text { Layout.fillWidth: true; text: I18n.t("选择常用编辑器、浏览器或资料工具，任务流启动后会自动打开。"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap }
            Repeater { model: launchAppsModel
                delegate: RowLayout { Layout.fillWidth: true
                    TextField { Layout.fillWidth: true; text: model.path; placeholderText: I18n.t("软件路径（.exe / .lnk / .bat）"); onTextChanged: if (index < launchAppsModel.count) launchAppsModel.setProperty(index, "path", text) }
                    Button { text: I18n.t("选择"); icon.name: "ic_fluent_folder_open_20_regular"; onClicked: { var selected = Backend.chooseExecutable(); if (selected) launchAppsModel.setProperty(index, "path", selected) } }
                    ToolButton { icon.name: "ic_fluent_dismiss_20_regular"; ToolTip.text: I18n.t("移除软件"); ToolTip.visible: hovered; onClicked: launchAppsModel.remove(index) }
                }
            }
            Button { text: I18n.t("添加软件"); icon.name: "ic_fluent_add_20_regular"; onClicked: { var selected = Backend.chooseExecutable(); if (selected) launchAppsModel.append({path: selected}) } }
        }
    }
    RowLayout { Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Button { text: I18n.t("取消")
                onClicked: { var router = page.nav(); if (router) router.pop() } }
        Button { text: I18n.t("保存任务流")
                highlighted: true
                icon.name: "ic_fluent_save_20_regular"
                onClicked: page.save() }
    }
    Dialog {
        id: taskPicker
        objectName: "flowTaskPicker"
        title: I18n.t("加入已有待办")
        modal: true
        width: Math.min(460, page.width - 40)
        standardButtons: Dialog.NoButton
        contentItem: ScrollView {
            implicitHeight: Math.min(320, taskChoices.implicitHeight)
            contentWidth: availableWidth
            clip: true
            ColumnLayout {
                id: taskChoices
                width: taskPicker.availableWidth
                Text { text: I18n.t("加入已有待办"); typography: Typography.Subtitle }
                Text { visible: page.existingTasks.length === 0; text: I18n.t("没有可加入的待办") }
                Repeater { model: page.existingTasks
                    CheckBox {
                        required property var modelData
                        objectName: "flowPickTask_" + modelData.id
                        Layout.fillWidth: true
                        text: modelData.title
                        onToggled: {
                            var selected = page.selectedTaskIds.slice()
                            if (checked) selected.push(Number(modelData.id)); else selected = selected.filter(function(id) { return id !== Number(modelData.id) })
                            page.selectedTaskIds = selected
                        }
                    }
                }
            }
        }
        footer: DialogButtonBox {
            JourneyButton { text: I18n.t("取消"); onClicked: taskPicker.close() }
            JourneyButton { objectName: "flowPickTasksConfirm"; text: I18n.t("加入") + " (" + page.selectedTaskIds.length + ")"; highlighted: true; enabled: page.selectedTaskIds.length > 0; onClicked: {
                for (var i = stepsModel.count - 1; i >= 0; i--) if (!String(stepsModel.get(i).title).trim().length) stepsModel.remove(i)
                page.existingTasks.filter(function(t) { return page.selectedTaskIds.indexOf(Number(t.id)) >= 0 }).forEach(function(t) {
                    stepsModel.append({title: t.title, duration: Number(t.focusMinutes || 25), type: "focus", relationId: Backend.newRelationId(), original: JSON.stringify({taskId: Number(t.id)})})
                })
                taskPicker.close()
            } }
        }
    }
}

