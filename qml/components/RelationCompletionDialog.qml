import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"
import "."

Dialog {
    id: dialog
    objectName: "relationCompletionDialog"
    property string nodeKey: ""
    property bool completeSource: true
    property var choices: ({node: {}, next: [], together: []})
    property string nextKey: ""
    property bool showTogether: false
    modal: true
    width: Math.min(520, parent ? parent.width - 40 : 520)
    title: I18n.t("接下来做什么？")
    standardButtons: Dialog.NoButton
    background: Rectangle {
        color: Theme.currentTheme.colors.backgroundAcrylicColor
        radius: Theme.currentTheme.appearance.windowRadius
        border.color: Theme.currentTheme.colors.windowBorderColor
    }
    function present(key, complete) {
        nodeKey = key; completeSource = complete
        choices = JSON.parse(Backend.getRelationChoices(key))
        nextKey = choices.next.length ? choices.next[0].key : ""
        nextChoice.currentIndex = choices.next.length ? 1 : 0
        showTogether = false; together.checked = false; open()
    }
    Connections {
        target: Backend
        function onTaskRelationsChanged() {
            if (!dialog.visible) return
            var previous = dialog.nextKey
            dialog.choices = JSON.parse(Backend.getRelationChoices(dialog.nodeKey))
            var index = dialog.choices.next.findIndex(function(n) { return n.key === previous })
            if (index < 0 && previous.length && dialog.choices.next.length) index = 0
            dialog.nextKey = index >= 0 ? dialog.choices.next[index].key : ""
            nextChoice.currentIndex = index + 1
        }
    }
    contentItem: ScrollView {
        id: contentScroll
        implicitHeight: Math.min(body.implicitHeight, dialog.parent ? dialog.parent.height - 180 : 440)
        contentWidth: availableWidth
        clip: true
        ColumnLayout {
        id: body
        width: contentScroll.availableWidth
        spacing: 14
        Text { Layout.fillWidth: true; text: dialog.title; typography: Typography.Subtitle }
        Text { Layout.fillWidth: true; text: dialog.choices.node.title || ""; typography: Typography.BodyStrong; wrapMode: Text.Wrap }
        CheckBox { id: together; Layout.fillWidth: true; visible: dialog.completeSource && dialog.choices.together.length > 0; text: I18n.t("同时完成关联任务") + " (" + dialog.choices.together.length + ")"; checked: false }
        JourneyButton { visible: together.visible; flat: true; text: dialog.showTogether ? I18n.t("收起列表") : I18n.t("查看列表"); onClicked: dialog.showTogether = !dialog.showTogether }
        Text { Layout.fillWidth: true; visible: together.visible && dialog.showTogether; text: dialog.choices.together.map(function(n) { return n.title + " · " + n.collectionTitle }).join("\n"); wrapMode: Text.Wrap; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        Text { visible: dialog.choices.next.length > 0; text: I18n.t("下一项"); typography: Typography.BodyStrong }
        ComboBox {
            id: nextChoice
            Layout.fillWidth: true
            visible: dialog.choices.next.length > 0
            model: [{label: I18n.t("稍后再做"), key: ""}].concat(dialog.choices.next.map(function(n) { return {label: n.title + " · " + n.collectionTitle, key: n.key} }))
            textRole: "label"
            onActivated: dialog.nextKey = model[currentIndex].key
            Accessible.name: I18n.t("接下来做哪个关联任务")
        }
        InlineHelp { helpText: I18n.t("确认前可查看同时完成的任务。
选择下一项后继续任务流；稍后再做会结束本次执行。"); Layout.alignment: Qt.AlignRight }
        }
    }
    footer: DialogButtonBox {
        JourneyButton { text: I18n.t("取消"); onClicked: dialog.close() }
        JourneyButton { objectName: "flowNextConfirm"; text: dialog.nextKey ? (dialog.completeSource ? I18n.t("完成并继续") : I18n.t("继续下一项")) : dialog.completeSource ? I18n.t("确认完成") : I18n.t("关闭"); highlighted: true; onClicked: { if (Backend.confirmRelationCompletion(dialog.nodeKey, dialog.completeSource, together.checked, dialog.nextKey)) dialog.close() } }
    }
}
