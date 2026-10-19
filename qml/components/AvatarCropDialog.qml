import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import RinUI
import RinUI as Rin
import "../i18n"

Rin.Dialog {
    id: dialog
    objectName: "avatarCropDialog"
    parent: QQC.Overlay.overlay
    title: I18n.t("裁剪头像")
    width: Math.min(430, parent ? parent.width - 32 : 430)
    modal: true
    property var candidate: ({})
    property real panX: 0
    property real panY: 0
    property real zoom: 1
    readonly property real side: Math.min(candidate.width || 1, candidate.height || 1) / zoom
    readonly property real centerX: 0.5 + panX * ((candidate.width || 1) - side) / (2 * (candidate.width || 1))
    readonly property real centerY: 0.5 + panY * ((candidate.height || 1) - side) / (2 * (candidate.height || 1))
    signal saved()
    onClosed: Backend.discardAccountAvatar()
    function present(data) { candidate = JSON.parse(data); panX = 0; panY = 0; zoom = 1; open() }
    contentItem: ColumnLayout {
        spacing: 16
        Text { text: dialog.title; typography: Typography.Subtitle }
        Text { Layout.fillWidth: true; text: I18n.t("拖动图片调整位置，或使用下方滑块。原图会保留。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
        Rectangle {
            id: viewport
            objectName: "avatarCropViewport"
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 240; Layout.preferredHeight: 240
            color: "#191b20"; radius: 8; clip: true
            Image {
                id: original
                source: dialog.candidate.url || ""
                width: viewport.width * (dialog.candidate.width || 1) / dialog.side
                height: viewport.height * (dialog.candidate.height || 1) / dialog.side
                x: (viewport.width - width) * (dialog.panX + 1) / 2
                y: (viewport.height - height) * (dialog.panY + 1) / 2
                fillMode: Image.Stretch
                cache: false
            }
            Rectangle { anchors.fill: parent; anchors.margins: 1; color: "transparent"; border.color: "white"; border.width: 2; radius: width / 2 }
            MouseArea {
                anchors.fill: parent; cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                property real startX; property real startY; property real oldX; property real oldY
                onPressed: function(mouse) { startX = mouse.x; startY = mouse.y; oldX = dialog.panX; oldY = dialog.panY }
                onPositionChanged: function(mouse) {
                    if (!pressed) return
                    if (original.width > viewport.width) dialog.panX = Math.max(-1, Math.min(1, oldX - 2 * (mouse.x - startX) / (original.width - viewport.width)))
                    if (original.height > viewport.height) dialog.panY = Math.max(-1, Math.min(1, oldY - 2 * (mouse.y - startY) / (original.height - viewport.height)))
                }
            }
        }
        RowLayout { Layout.fillWidth: true; Text { text: I18n.t("缩放"); typography: Typography.Caption } Rin.Slider { objectName: "avatarZoomSlider"; Layout.fillWidth: true; from: 1; to: 4; value: dialog.zoom; onMoved: dialog.zoom = value; Accessible.name: I18n.t("头像缩放") } }
        RowLayout { Layout.fillWidth: true; Text { text: I18n.t("左右"); typography: Typography.Caption } Rin.Slider { Layout.fillWidth: true; from: -1; to: 1; value: dialog.panX; onMoved: dialog.panX = value; Accessible.name: I18n.t("头像水平位置") } }
        RowLayout { Layout.fillWidth: true; Text { text: I18n.t("上下"); typography: Typography.Caption } Rin.Slider { Layout.fillWidth: true; from: -1; to: 1; value: dialog.panY; onMoved: dialog.panY = value; Accessible.name: I18n.t("头像垂直位置") } }
    }
    footer: Rin.DialogButtonBox {
        Rin.Button { objectName: "avatarCropCancel"; Layout.fillWidth: true; text: I18n.t("取消"); onClicked: dialog.close() }
        Rin.Button { objectName: "avatarCropSave"; Layout.fillWidth: true; highlighted: true; text: I18n.t("保存头像"); onClicked: { if (Backend.saveAccountAvatar(dialog.centerX, dialog.centerY, dialog.zoom)) { dialog.close(); dialog.saved() } } }
    }
}
