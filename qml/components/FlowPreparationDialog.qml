import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"
import "."

Dialog {
    id: dialog
    objectName: "flowPreparationDialog"
    property string nodeKey: ""
    property var node: ({})
    modal: true
    width: Math.min(440, parent ? parent.width - 40 : 440)
    title: I18n.t("开始任务")
    standardButtons: Dialog.NoButton
    function present(key) {
        nodeKey = key
        node = JSON.parse(Backend.getRelationChoices(key)).node
        duration.value = Math.max(1, Math.min(180, Number(node.minutes || 25)))
        shield.checked = false
        open()
    }
    contentItem: ColumnLayout {
        spacing: 14
        Text { Layout.fillWidth: true; text: dialog.node.title || ""; typography: Typography.Subtitle; wrapMode: Text.Wrap }
        Text { Layout.fillWidth: true; text: dialog.node.collectionTitle || ""; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        RowLayout {
            visible: dialog.node.kind !== "group" && dialog.node.kind !== "project"
            Text { Layout.fillWidth: true; text: I18n.t("专注时长（分钟）") }
            SpinBox { id: duration; objectName: "flowStartMinutes"; from: 1; to: 180; value: 25; editable: true }
        }
        CheckBox { id: shield; text: I18n.t("专注护盾") }
    }
    footer: DialogButtonBox {
        JourneyButton { text: I18n.t("取消"); onClicked: dialog.close() }
        JourneyButton { objectName: "flowStartConfirm"; text: I18n.t("开始"); highlighted: true; onClicked: { if (Backend.startRelationNode(dialog.nodeKey, duration.value, "", shield.checked)) dialog.close() } }
    }
}
