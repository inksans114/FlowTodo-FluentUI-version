import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"

Dialog {
    id: root
    objectName: "DeleteConfirmDialog"
    property string itemType: I18n.t("内容")
    property string itemName: ""
    signal deleteConfirmed()

    title: I18n.t("删除") + itemType + "？"
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel

    onAccepted: root.deleteConfirmed()
    onOpened: {
        var confirmButton = footer.standardButton(Dialog.Ok)
        var cancelButton = footer.standardButton(Dialog.Cancel)
        if (confirmButton)
            confirmButton.text = I18n.t("删除")
        if (cancelButton)
            cancelButton.text = I18n.t("取消")
    }

    contentItem: ColumnLayout {
        spacing: 14
        Text {
            Layout.fillWidth: true
            text: root.title
            typography: Typography.Subtitle
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Icon {
                name: "ic_fluent_warning_20_regular"
                size: 22
                color: "#c42b1c"
            }
            Text {
                Layout.fillWidth: true
                text: "“" + String(root.itemName || I18n.t("未命名")) + "”"
                typography: Typography.BodyStrong
                wrapMode: Text.Wrap
            }
        }
        Text {
            Layout.fillWidth: true
            text: I18n.t("删除后无法恢复。")
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
            wrapMode: Text.Wrap
        }
    }
}
