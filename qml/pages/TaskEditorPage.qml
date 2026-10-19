import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "taskEditorPage"
    title: I18n.t("编辑任务")
    wrapperWidth: 720
    horizontalPadding: 32
    property bool showMore: false
    property double taskId: -1
    property var task: ({})
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { task = JSON.parse(Backend.tasksJson).find(function(t) { return Number(t.id) === page.taskId }) || ({}); titleField.text = task.title || ""; metaField.text = task.meta || ""; duration.value = Number(task.focusMinutes || 25) }
    Component.onCompleted: load()
    RowLayout {
        Layout.fillWidth: true
        ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"; onClicked: { var r = page.nav(); if (r) r.pop() } Accessible.name: I18n.t("返回") }
        Item { Layout.fillWidth: true }
        JourneyButton { objectName: "taskEditorMore"; text: I18n.t("更多"); flat: true; icon.name: "ic_fluent_more_horizontal_20_regular"; onClicked: page.showMore = !page.showMore }
    }
    Frame {
        Layout.fillWidth: true; padding: 20
        contentItem: ColumnLayout {
            spacing: 16
            TextField { id: titleField; objectName: "taskTitleField"; Accessible.name: I18n.t("任务名称"); Layout.fillWidth: true; placeholderText: I18n.t("任务名称"); maximumLength: 1000 }
            Text { visible: page.showMore; text: I18n.t("备注"); typography: Typography.BodyStrong }
            TextArea { id: metaField; objectName: "taskMetaField"; visible: page.showMore; Accessible.name: I18n.t("备注"); Layout.fillWidth: true; Layout.preferredHeight: 100; wrapMode: TextEdit.Wrap }
            RowLayout { visible: page.showMore; Text { text: I18n.t("专注时长") } JourneySpinBox { id: duration; objectName: "taskDurationField"; Accessible.name: I18n.t("专注时长"); from: 1; to: 180 } Text { text: I18n.t("分钟") } Item { Layout.fillWidth: true } }
            JourneyButton { objectName: "taskEditorRelations"; visible: page.showMore; text: I18n.t("关联任务"); flat: true; icon.name: "ic_fluent_link_20_regular"; onClicked: Backend.openTaskRelations("task:" + page.taskId) }
        }
    }
    Text { Layout.fillWidth: true; visible: !page.task.id; text: I18n.t("任务已不存在，请返回任务列表。"); color: Theme.currentTheme.colors.systemCriticalColor; wrapMode: Text.Wrap }
    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        JourneyButton { text: I18n.t("取消"); onClicked: { var r = page.nav(); if (r) r.pop() } }
        JourneyButton { text: I18n.t("保存"); highlighted: true; enabled: Boolean(page.task.id) && titleField.text.trim().length > 0; onClicked: { if (Backend.updateTaskDetails(JSON.stringify({id: page.taskId, title: titleField.text, meta: metaField.text, focusMinutes: duration.value}))) { var r = page.nav(); if (r) r.pop() } } }
    }
}
