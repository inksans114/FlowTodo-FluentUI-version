import QtQuick
import QtQuick.Layouts
import RinUI
import "../i18n"

ColumnLayout {
    id: quota
    property var usageData: ({})
    property bool compact: false
    property bool showTitle: true
    readonly property bool available: usageData.remainingFraction !== null && usageData.remainingFraction !== undefined
    readonly property string statusText: usageData.status === "provider" ? I18n.t("服务商管理") : I18n.t("次数已用完")
    spacing: compact ? 6 : 12
    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: quota.showTitle ? I18n.t("AI 使用次数") : I18n.t("剩余次数"); typography: Typography.Caption }
        Text { text: quota.available ? Number(quota.usageData.remaining) + " / " + Number(quota.usageData.limit) + I18n.t(" 次") : quota.statusText; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: quota.compact ? 5 : 7
        radius: height / 2
        color: Qt.alpha(Theme.currentTheme.colors.textSecondaryColor, 0.12)
        Rectangle {
            height: parent.height
            width: parent.width * (quota.available ? Math.max(0, Math.min(1, Number(quota.usageData.remainingFraction))) : 0)
            radius: height / 2
            color: Theme.currentTheme.colors.primaryColor
            Behavior on width { NumberAnimation { duration: 180 } }
        }
        Accessible.role: Accessible.ProgressBar
        Accessible.name: I18n.t("AI 使用次数") + " · " + (quota.available ? Number(quota.usageData.remaining) + " / " + Number(quota.usageData.limit) + I18n.t(" 次剩余") : quota.statusText)
    }
    Text {
        visible: !quota.compact
        Layout.fillWidth: true
        text: quota.usageData.status === "provider" ? I18n.t("自定义 API 不消耗 Free 次数") : I18n.t("当前通道提供 ") + Number(quota.usageData.limit || 0) + I18n.t(" 次 AI 使用")
        typography: Typography.Caption
        color: Theme.currentTheme.colors.textSecondaryColor
        wrapMode: Text.Wrap
    }
}
