import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"
import "."

Dialog {
    id: dialog
    objectName: "flowInvalidDialog"
    property string reason: ""
    title: I18n.t("这个流程不规范")
    modal: true
    width: Math.min(460, parent ? parent.width - 40 : 460)
    standardButtons: Dialog.NoButton
    contentItem: ColumnLayout {
        spacing: 12
        Text { Layout.fillWidth: true; text: I18n.t("这个流程不规范"); typography: Typography.Subtitle }
        Text { Layout.fillWidth: true; text: dialog.reason; wrapMode: Text.Wrap }
        Text { Layout.fillWidth: true; text: I18n.t("请调整后再开始。"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
    }
    footer: DialogButtonBox { JourneyButton { text: I18n.t("知道了"); highlighted: true; onClicked: dialog.close() } }
}
