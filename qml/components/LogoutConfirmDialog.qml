import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import RinUI
import RinUI as Rin
import "../i18n"

Rin.Dialog {
    id: root
    objectName: "accountLogoutDialog"
    parent: QQC.Overlay.overlay
    width: Math.min(400, parent.width - 32)
    title: I18n.t("退出当前账户？")
    modal: true
    standardButtons: QQC.Dialog.Ok | QQC.Dialog.Cancel
    onAccepted: Backend.cloudLogout()
    onOpened: {
        footer.standardButton(QQC.Dialog.Ok).text = I18n.t("退出登录")
        footer.standardButton(QQC.Dialog.Ok).highlighted = true
        footer.standardButton(QQC.Dialog.Cancel).text = I18n.t("取消")
        footer.standardButton(QQC.Dialog.Cancel).forceActiveFocus()
    }
    contentItem: ColumnLayout {
        spacing: 12
        Text { Layout.fillWidth: true; text: root.title; typography: Typography.Subtitle; wrapMode: Text.Wrap }
        Text {
            Layout.fillWidth: true
            text: I18n.t("本机记录会保留，云同步和官方 AI 将暂停。")
            typography: Typography.Body
            wrapMode: Text.Wrap
        }
    }
}
