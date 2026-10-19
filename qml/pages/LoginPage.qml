import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import RinUI
import RinUI as Rin
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "AccountLoginPage"
    title: ""
    wrapperWidth: 960
    horizontalPadding: width < 740 ? 24 : 40
    contentSpacing: 0
    property var cloud: { try { return JSON.parse(Backend.cloudJson) } catch(e) { return ({}) } }
    property double clock: Date.now() / 1000
    readonly property int cooldown: Math.max(0, Math.ceil(60 - (clock - Number(cloud.codeSentAt || 0))))
    readonly property bool compact: width < 800
    readonly property bool emailValid: /^[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}$/.test(email.text.trim())
    StudioTokens { id: ui; customAllowed: false }
    Timer { interval: 1000; running: page.cooldown > 0; repeat: true; onTriggered: page.clock = Date.now() / 1000 }
    Connections {
        target: Backend
        function onAccountChanged() {
            page.clock = Date.now() / 1000
            if (page.cloud.loggedIn) {
                var view = page
                while (view && view.objectName !== "MainNavigationView") view = view.parent
                if (view) view.push(Qt.resolvedUrl("UserAccount.qml"))
            }
        }
    }
    Item { Layout.preferredHeight: page.compact ? 24 : 54 }
    RowLayout {
        Layout.fillWidth: true
        spacing: 48
        ColumnLayout {
            visible: !page.compact
            Layout.fillWidth: true
            Layout.maximumWidth: 380
            Layout.alignment: Qt.AlignVCenter
            spacing: 22
            RowLayout {
                spacing: 12
                Image { source: Qt.resolvedUrl("../../logopromax.ico"); Layout.preferredWidth: 40; Layout.preferredHeight: 40; fillMode: Image.PreserveAspectFit }
                Text { text: "FlowTodo"; font.pixelSize: 20; font.weight: Font.DemiBold; color: ui.ink }
            }
            Text { Layout.fillWidth: true; text: I18n.t("你的每一步，\n都有归处。"); font.pixelSize: 36; font.weight: Font.DemiBold; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.2; color: ui.ink; wrapMode: Text.WordWrap }
            Text { Layout.fillWidth: true; text: I18n.t("登录，让任务、计划与个人资料\n在你的设备之间接续。"); font.pixelSize: 14; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.6; color: ui.muted; wrapMode: Text.WordWrap }
            Item { Layout.preferredHeight: 12 }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 164; radius: 18; color: ui.tint; border.color: ui.stroke
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 22; spacing: 12
                    RowLayout { spacing: 8
                        Icon { name: "ic_fluent_checkmark_circle_20_regular"; size: 18; color: ui.accent }
                        Text { text: I18n.t("给今天，一个清晰的开始"); font.pixelSize: 14; font.weight: Font.DemiBold; color: ui.ink }
                    }
                    Repeater {
                        model: [I18n.t("记下一个想法"), I18n.t("连接下一步行动"), I18n.t("留一点时间，专注自己")]
                        RowLayout {
                            spacing: 10
                            Rectangle { implicitWidth: 6; implicitHeight: 6; radius: 3; color: ui.accent; opacity: 0.65 }
                            Text { text: modelData; font.pixelSize: 13; color: ui.muted }
                        }
                    }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.maximumWidth: 420
            Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
            implicitHeight: form.implicitHeight + 64
            radius: 22; color: ui.surface; border.color: ui.stroke
            ColumnLayout {
                id: form; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: page.compact ? 24 : 32
                spacing: 16
                RowLayout { visible: page.compact; spacing: 10
                    Image { source: Qt.resolvedUrl("../../logopromax.ico"); Layout.preferredWidth: 28; Layout.preferredHeight: 28; fillMode: Image.PreserveAspectFit }
                    Text { text: "FlowTodo"; font.pixelSize: 16; font.weight: Font.DemiBold; color: ui.ink }
                }
                ColumnLayout { Layout.fillWidth: true; spacing: 8
                    Text { text: I18n.t("欢迎回来"); font.pixelSize: 28; font.weight: Font.DemiBold; color: ui.ink }
                    Text { Layout.fillWidth: true; text: I18n.t("用邮箱验证码，进入你的账户。"); font.pixelSize: 13; color: ui.muted; wrapMode: Text.WordWrap }
                }
                Item { Layout.preferredHeight: 4 }
                ColumnLayout { Layout.fillWidth: true; spacing: 8
                    Text { text: I18n.t("邮箱地址"); font.pixelSize: 13; font.weight: Font.DemiBold; color: ui.ink }
                    Rin.TextField {
                        id: email; objectName: "loginEmail"; Layout.fillWidth: true; Layout.preferredHeight: 44
                        placeholderText: "name@example.com"; maximumLength: 254
                        inputMethodHints: Qt.ImhEmailCharactersOnly | Qt.ImhNoAutoUppercase
                        Accessible.name: I18n.t("邮箱地址")
                        enabled: !page.cloud.busy
                        onAccepted: if (page.emailValid && !page.cooldown) Backend.cloudSendCode(text)
                    }
                }
                ColumnLayout { Layout.fillWidth: true; spacing: 8
                    Text { text: I18n.t("邮箱验证码"); font.pixelSize: 13; font.weight: Font.DemiBold; color: ui.ink }
                    RowLayout { Layout.fillWidth: true; spacing: 8
                        Rin.TextField {
                            id: code; objectName: "loginCode"; Layout.fillWidth: true; Layout.preferredHeight: 44
                            placeholderText: I18n.t("6 位验证码"); maximumLength: 6; validator: RegularExpressionValidator { regularExpression: /[0-9]{0,6}/ }
                            inputMethodHints: Qt.ImhDigitsOnly; Accessible.name: I18n.t("邮箱验证码")
                            enabled: !page.cloud.busy
                            onAccepted: if (text.length === 6) Backend.cloudSignIn(email.text,text)
                        }
                        Rin.Button {
                            objectName: "loginSendCode"; Layout.preferredHeight: 44; Layout.preferredWidth: 108
                            text: page.cooldown ? page.cooldown + "s 后重发" : I18n.t("获取验证码")
                            enabled: page.emailValid && !page.cloud.busy && page.cooldown === 0
                            onClicked: Backend.cloudSendCode(email.text)
                        }
                    }
                }
                Text {
                    objectName: "loginFeedback"; Layout.fillWidth: true; Layout.minimumHeight: 36
                    text: page.cloud.error || (page.cloud.codeSentAt ? I18n.t("验证码已发送，请检查收件箱或垃圾邮件。") : I18n.t("首次使用？先注册，再回到这里登录。"))
                    color: page.cloud.error ? (ui.dark ? "#ffb4ab" : "#b42318") : ui.muted
                    font.pixelSize: 12; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.5; wrapMode: Text.WordWrap
                    Accessible.role: Accessible.StaticText; Accessible.name: text
                }
                Rin.Button {
                    objectName: "loginSubmit"; Layout.fillWidth: true; Layout.preferredHeight: 46; highlighted: true
                    text: page.cloud.busy ? I18n.t("正在连接…") : I18n.t("登录 FlowTodo")
                    enabled: page.emailValid && code.text.length === 6 && !page.cloud.busy
                    onClicked: Backend.cloudSignIn(email.text,code.text)
                }
                RowLayout { Layout.alignment: Qt.AlignHCenter; spacing: 4
                    Text { text: I18n.t("还没有账户？"); font.pixelSize: 13; color: ui.muted }
                    Rin.Button { objectName: "loginRegister"; flat: true; text: I18n.t("创建账户"); enabled: !page.cloud.busy; onClicked: Backend.cloudRegister() }
                }
            }
        }
    }
    Item { Layout.preferredHeight: 24 }
    Rin.Button {
        objectName: "loginUseLocal"; Layout.alignment: Qt.AlignHCenter; flat: true; text: I18n.t("暂不登录，继续本地使用")
        onClicked: {
            var view = page
            while (view && view.objectName !== "MainNavigationView") view = view.parent
            if (view) view.push(Qt.resolvedUrl("HomeDashboard.qml"))
        }
    }
    Item { Layout.preferredHeight: 24 }
}
