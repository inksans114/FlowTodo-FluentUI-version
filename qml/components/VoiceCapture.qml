import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"

ColumnLayout {
    id: root
    property string transcript: ""
    property Item inputTarget
    property bool forceSystem: false
    property bool showHint: true
    property bool compact: false
    property bool allowDuringAi: false
    property bool cloudMode: !forceSystem && Backend.getSetting("speechInputMode", "system") === "cloud"
    readonly property bool busy: Backend.speechInput.state !== "idle"
    readonly property real controlWidth: cloudMode ? cloudCapture.implicitWidth : systemCapture.implicitWidth
    signal recognized(string text)
    spacing: 8
    Connections {
        target: Backend
        function onSettingsChanged() { root.cloudMode = !root.forceSystem && Backend.getSetting("speechInputMode", "system") === "cloud" }
    }
    Connections {
        target: Backend.speechInput
        function onTextReady(text) { if (root.cloudMode && root.visible) { root.transcript = text; root.recognized(text) } }
    }
    RowLayout {
        Layout.fillWidth: true
        InlineDictationButton {
            id: systemCapture
            objectName: "voiceCaptureButton"
            visible: !root.cloudMode
            inputTarget: root.inputTarget
            idleText: root.compact ? I18n.t("语音") : I18n.t("语音输入")
            Layout.fillWidth: true
            Layout.preferredWidth: 0
            Layout.minimumWidth: 0
            enabled: root.allowDuringAi || !Backend.aiRequestRunning
        }
        JourneyButton {
            id: cloudCapture
            visible: root.cloudMode
            objectName: "voiceCaptureButton"
            Layout.fillWidth: !root.compact
            implicitHeight: root.compact ? 40 : 48
            flat: root.compact
            highlighted: Backend.speechInput.state === "recording"
            icon.name: "ic_fluent_mic_20_regular"
            text: Backend.speechInput.state === "recording" ? I18n.t("说完了，识别文字") + " · " + Backend.speechInput.seconds + "s" : Backend.speechInput.state === "transcribing" ? I18n.t("正在识别…") : root.compact ? I18n.t("语音") : I18n.t("说一说想做的事")
            enabled: Backend.speechInput.state !== "transcribing" && (root.allowDuringAi || !Backend.aiRequestRunning)
            onClicked: {
                if (Backend.speechInput.state === "recording") Backend.speechInput.stop()
                else if (root.cloudMode) consent.open()
                else if (root.inputTarget) {
                    root.inputTarget.forceActiveFocus()
                    Backend.openSystemDictation(root.inputTarget)
                }
            }
        }
        JourneyButton { visible: root.busy; text: I18n.t("取消"); onClicked: Backend.speechInput.cancel() }
    }
    Text {
        visible: root.showHint || (root.cloudMode && !root.compact)
        Layout.fillWidth: true
        text: root.cloudMode ? I18n.t("云端转写 · 最多 90 秒，可能产生语音服务费用。先检查原话，再整理。") : I18n.t(Backend.systemDictationHint)
        typography: Typography.Caption
        wrapMode: Text.Wrap
        color: Theme.currentTheme.colors.textSecondaryColor
    }
    Dialog {
        id: consent
        objectName: "voiceConsent"
        title: I18n.t("开始语音输入")
        modal: true
        width: Math.min(480, parent ? parent.width : 480)
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: ColumnLayout {
            spacing: 12
            Text { Layout.fillWidth: true; text: consent.title; typography: Typography.Subtitle }
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: I18n.t("将使用麦克风；结束后录音会发送到你配置的语音服务识别，可能产生服务费用。本机不保存录音。服务地址：") + "\n" + String(Backend.getSetting("speechBaseUrl", "") || Backend.getSetting("aiBaseUrl", "https://api.openai.com/v1")) }
        }
        onAccepted: Backend.speechInput.start()
    }
    Component.onDestruction: if (Backend.speechInput.state === "recording") Backend.speechInput.cancel()
}
