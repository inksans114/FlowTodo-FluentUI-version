import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

Dialog {
    id: root
    objectName: "FactoryResetDialog"
    signal resetConfirmed()

    title: "恢复出厂设置？"
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel

    onAccepted: root.resetConfirmed()
    onOpened: {
        var confirmButton = footer.standardButton(Dialog.Ok)
        var cancelButton = footer.standardButton(Dialog.Cancel)
        if (confirmButton)
            confirmButton.text = "清除所有数据"
        if (cancelButton)
            cancelButton.text = "取消"
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
                text: "将清除任务、日程、统计、成就、AI 计划、便签和相关记录。此操作无法撤销。"
                typography: Typography.Body
                wrapMode: Text.Wrap
            }
        }
        Text {
            Layout.fillWidth: true
            text: "应用设置会恢复默认。清除后无法恢复。"
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
            wrapMode: Text.Wrap
        }
    }
}
