import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import RinUI
import "../i18n"

ColumnLayout {
    id: panel
    spacing: 24
    property bool aboutMode: true
    property var update: { try { return JSON.parse(Backend.updateJson) } catch (error) { return ({}) } }
    readonly property bool compact: width < 740
    readonly property bool working: update.status === "checking" || update.status === "downloading" || update.status === "installing"
    readonly property string stateTitle: {
        switch (update.status) {
        case "checking": return I18n.t("正在检查更新")
        case "available": return I18n.t("发现新版本")
        case "downloading": return I18n.t("正在下载更新")
        case "ready": return I18n.t("更新已准备好")
        case "installing": return I18n.t("正在准备安装")
        case "error": return I18n.t("更新暂未完成")
        case "store": return I18n.t("由 Microsoft Store 管理更新")
        default: return I18n.t("版本与更新")
        }
    }
    StudioTokens { id: ui; customAllowed: false }
    Frame {
        objectName: "storeProductHeader"
        Layout.fillWidth: true
        padding: panel.compact ? 24 : 32
        background: Rectangle {
            radius: 24
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: ui.dark ? "#30313b" : "#fff3ec" }
                GradientStop { position: 0.55; color: ui.dark ? "#2b303b" : "#f6f4fc" }
                GradientStop { position: 1; color: ui.dark ? "#253443" : "#eaf3ff" }
            }
        }
        contentItem: RowLayout {
            spacing: panel.compact ? 20 : 28
            Image {
                objectName: "aboutAppIcon"
                Layout.preferredWidth: panel.compact ? 88 : 116
                Layout.preferredHeight: panel.compact ? 88 : 116
                Layout.alignment: Qt.AlignTop
                Layout.topMargin: 4
                source: Qt.resolvedUrl("../../logopromax.ico")
                sourceSize.width: 160; sourceSize.height: 160
                fillMode: Image.PreserveAspectFit
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 10
                Text { text: I18n.t("效率与专注"); font.pixelSize: 12; font.weight: Font.Medium; color: ui.muted }
                Text {
                    Layout.fillWidth: true
                    text: panel.aboutMode ? "FlowTodo" : I18n.t("软件更新")
                    font.pixelSize: panel.compact ? 32 : 40
                    font.weight: Font.DemiBold; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.15; color: ui.ink; wrapMode: Text.Wrap
                }
                Text { Layout.fillWidth: true; text: I18n.t("把想法变成行动，专注眼前的一件事。"); font.pixelSize: 14; color: ui.muted; wrapMode: Text.Wrap }
                Flow {
                    Layout.fillWidth: true; Layout.topMargin: 12; spacing: 10
                    Button {
                        objectName: "checkUpdatesButton"
                        visible: !panel.update.ready && !(panel.update.availableVersion && panel.update.canInstall)
                        text: panel.update.status === "checking" ? I18n.t("正在检查更新") : I18n.t("检查更新")
                        highlighted: true; icon.name: "ic_fluent_arrow_sync_20_regular"
                        enabled: !panel.update.busy && !panel.update.ready
                        implicitHeight: 38; leftPadding: 22; rightPadding: 22
                        onClicked: Backend.checkForUpdates()
                    }
                    Button {
                        objectName: "downloadUpdateButton"
                        visible: Boolean(panel.update.availableVersion) && !panel.update.ready && panel.update.canInstall
                        text: panel.update.status === "downloading" ? I18n.t("正在下载更新") : I18n.t("下载更新")
                        highlighted: true; icon.name: "ic_fluent_arrow_download_20_regular"
                        enabled: !panel.update.busy
                        implicitHeight: 38; leftPadding: 22; rightPadding: 22
                        onClicked: Backend.downloadUpdate()
                    }
                    Button {
                        objectName: "installUpdateButton"
                        visible: Boolean(panel.update.ready) && panel.update.canInstall
                        text: I18n.t("安装并重启"); highlighted: true; enabled: !panel.update.busy
                        implicitHeight: 38; leftPadding: 22; rightPadding: 22
                        onClicked: installConfirmation.open()
                    }
                    Button { text: I18n.t("发布记录"); flat: true; implicitHeight: 38; onClicked: Backend.openReleasePage() }
                }
            }
        }
    }
    RowLayout {
        objectName: "releaseMetadata"
        Layout.fillWidth: true; Layout.leftMargin: 4; Layout.rightMargin: 4
        spacing: panel.compact ? 18 : 32
        ColumnLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0; spacing: 5
            Text { Layout.fillWidth: true; text: I18n.t("当前版本"); font.pixelSize: 12; color: ui.muted }
            Text { objectName: "currentVersionLabel"; Layout.fillWidth: true; text: Backend.appVersion; font.pixelSize: 20; font.weight: Font.DemiBold; color: ui.ink }
        }
        Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 34; color: ui.stroke }
        ColumnLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0; spacing: 5
            Text { Layout.fillWidth: true; text: I18n.t("更新通道"); font.pixelSize: 12; color: ui.muted }
            Text { Layout.fillWidth: true; text: panel.update.storeManaged ? "Microsoft Store" : I18n.t("正式版"); font.pixelSize: 15; font.weight: Font.Medium; color: ui.ink; wrapMode: Text.Wrap }
        }
        Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 34; color: ui.stroke }
        ColumnLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0; spacing: 5
            Text { Layout.fillWidth: true; text: I18n.t("自动更新"); font.pixelSize: 12; color: ui.muted }
            Text { Layout.fillWidth: true; text: panel.update.storeManaged ? I18n.t("由商店管理") : panel.update.autoDownload ? I18n.t("已开启") : I18n.t("已关闭"); font.pixelSize: 15; font.weight: Font.Medium; color: ui.ink }
        }
    }
    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: ui.stroke }
    GridLayout {
        objectName: "releaseDetailsGrid"
        Layout.fillWidth: true
        columns: panel.compact ? 1 : 2
        columnSpacing: 24; rowSpacing: 20
        ColumnLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 560
            Layout.alignment: Qt.AlignTop; spacing: 16
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    Layout.preferredWidth: 34; Layout.preferredHeight: 34; radius: 10; color: ui.tint
                    Icon { anchors.centerIn: parent; name: panel.update.ready ? "ic_fluent_checkmark_circle_20_regular" : "ic_fluent_arrow_sync_20_regular"; size: 19; color: ui.accent }
                }
                Text { objectName: "updateStateTitle"; Layout.fillWidth: true; text: panel.stateTitle; font.pixelSize: 19; font.weight: Font.DemiBold; color: ui.ink; wrapMode: Text.Wrap }
            }
            Text {
                objectName: "updateStatusMessage"
                Layout.fillWidth: true; text: I18n.t(panel.update.message || "")
                wrapMode: Text.Wrap; font.pixelSize: 13; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.45; color: ui.muted
            }
            Text { visible: Boolean(panel.update.availableVersion); text: I18n.t("可用版本") + "  " + String(panel.update.availableVersion || ""); font.pixelSize: 13; font.weight: Font.Medium; color: ui.accent }
            ProgressBar { objectName: "updateDownloadProgress"; Layout.fillWidth: true; visible: panel.working; indeterminate: panel.update.status !== "downloading"; from: 0; to: 100; value: Number(panel.update.progress || 0) }
            Text { visible: panel.update.status === "downloading"; text: Math.round(Number(panel.update.progress || 0)) + "%"; font.pixelSize: 12; color: ui.muted }
            Frame {
                objectName: "releaseNotesCard"
                Layout.fillWidth: true; Layout.topMargin: 4; padding: 22
                background: Rectangle { radius: 16; color: ui.surface; border.color: ui.stroke }
                contentItem: ColumnLayout {
                    spacing: 12
                    Text { text: I18n.t("更新内容"); font.pixelSize: 15; font.weight: Font.DemiBold; color: ui.ink }
                    Text { Layout.fillWidth: true; text: panel.update.notes || I18n.t("检查新版本后，可以在这里查看更新说明。"); textFormat: Text.PlainText; font.pixelSize: 13; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.5; wrapMode: Text.Wrap; color: ui.muted }
                }
            }
        }
        Frame {
            objectName: "automaticUpdateCard"
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 270; Layout.alignment: Qt.AlignTop
            padding: 22
            background: Rectangle { radius: 16; color: ui.surface; border.color: ui.stroke }
            contentItem: ColumnLayout {
                spacing: 16
                RowLayout {
                    Layout.fillWidth: true; spacing: 12
                    Text { Layout.fillWidth: true; text: I18n.t("自动更新"); font.pixelSize: 15; font.weight: Font.DemiBold; color: ui.ink; wrapMode: Text.Wrap }
                    Switch {
                        objectName: "automaticUpdateSwitch"
                        enabled: !panel.update.storeManaged; checked: Boolean(panel.update.autoDownload)
                        checkedText: ""; uncheckedText: ""; Accessible.name: I18n.t("自动更新")
                        onClicked: Backend.setSetting("updateAutoDownload", checked)
                    }
                }
                Text { Layout.fillWidth: true; text: panel.update.storeManaged ? I18n.t("此版本的更新由 Microsoft Store 提供。") : I18n.t("在后台检查和下载，让更新随时就绪。"); wrapMode: Text.Wrap; font.pixelSize: 13; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.45; color: ui.muted }
                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: ui.stroke }
                RowLayout {
                    Layout.fillWidth: true; spacing: 8
                    Icon { name: "ic_fluent_shield_checkmark_20_regular"; size: 17; color: ui.muted }
                    Text { Layout.fillWidth: true; text: I18n.t("由你决定安装时间"); font.pixelSize: 12; font.weight: Font.Medium; color: ui.ink; wrapMode: Text.Wrap }
                }
                Text { Layout.fillWidth: true; text: I18n.t("下载完成后，你可以继续工作，准备好后再安装。"); font.pixelSize: 12; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.45; color: ui.muted; wrapMode: Text.Wrap }
            }
        }
    }
    Dialog {
        id: installConfirmation
        objectName: "installUpdateDialog"
        parent: QQC.Overlay.overlay
        width: Math.min(400, parent ? parent.width - 32 : 400)
        title: I18n.t("安装并重启 FlowTodo？"); modal: true; standardButtons: Dialog.NoButton
        contentItem: ColumnLayout {
            spacing: 18
            Text { text: installConfirmation.title; typography: Typography.Subtitle; Layout.fillWidth: true; wrapMode: Text.Wrap }
            Text { Layout.preferredWidth: 320; Layout.fillWidth: true; text: I18n.t("软件将关闭以安装更新，完成后自动重新打开。本地任务与设置会保留。"); wrapMode: Text.Wrap }
            RowLayout {
                Item { Layout.fillWidth: true }
                Button { text: I18n.t("稍后"); onClicked: installConfirmation.close() }
                Button { objectName: "confirmInstallUpdate"; text: I18n.t("安装并重启"); highlighted: true; onClicked: { installConfirmation.close(); Backend.installUpdate() } }
            }
        }
    }
}
