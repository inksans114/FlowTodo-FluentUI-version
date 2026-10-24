import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import RinUI
import RinUI as Rin
import "../i18n"
Item {
    id: control
    objectName: "accountMenuRoot"
    height: 56
    property bool collapsed: false
    property var account: { try { return JSON.parse(Backend.accountJson) } catch (error) { return {name: "", usage: {}} } }
    readonly property string displayName: account.local ? I18n.t("本地访客") : (account.name || "")
    signal accountRequested()
    signal aiRequested()
    signal settingsRequested()
    signal helpRequested()
    function showAccount() { menu.close(); accountRequested() }
    Rin.Button {
        id: trigger; objectName: "accountMenuButton"
        anchors.fill: parent; anchors.margins: 6; flat: true
        leftPadding: control.collapsed ? 4 : 8; rightPadding: leftPadding
        Accessible.name: I18n.t("打开账户菜单")
        contentItem: RowLayout {
            spacing: 8
            AccountAvatar { objectName: "sidebarAccountAvatar"; Layout.preferredWidth: 24; Layout.preferredHeight: 24; Layout.alignment: Qt.AlignVCenter; account: control.account }
            Text { objectName: "sidebarAccountName"; visible: !control.collapsed; Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredHeight: 28; Layout.alignment: Qt.AlignVCenter; verticalAlignment: Text.AlignVCenter; lineHeightMode: Text.ProportionalHeight; lineHeight: 1; text: control.displayName; typography: Typography.Body; elide: Text.ElideRight }
            AccountPlanBadge { objectName: "sidebarAccountBadge"; visible: !control.collapsed; Layout.alignment: Qt.AlignVCenter; Layout.preferredHeight: 28; plan: control.account.planId || "free" }
            Item { objectName: "sidebarAccountMore"; visible: !control.collapsed; Layout.preferredWidth: 20; Layout.preferredHeight: 28; Layout.alignment: Qt.AlignVCenter
                Icon { anchors.centerIn: parent; name: "ic_fluent_more_horizontal_20_regular"; size: 16; color: Theme.currentTheme.colors.textSecondaryColor }
            }
        }
        onClicked: menu.visible ? menu.close() : menu.open()
    }
    Rin.Popup {
        id: menu; objectName: "accountFlyout"; parent: QQC.Overlay.overlay
        width: Math.min(260, parent.width - 24); padding: 8
        implicitHeight: contentItem.implicitHeight + topPadding + bottomPadding; height: implicitHeight
        position: Position.None; posX: 12; posY: 12; x: posX; y: posY
        onAboutToShow: {
            var p = control.mapToItem(menu.parent, 0, 0)
            posX = Math.max(12, Math.min(p.x + 6, menu.parent.width - width - 12))
            posY = Math.max(12, p.y - implicitHeight - 6)
        }
        closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 100 } }
        contentItem: ColumnLayout {
            spacing: 4
            Rin.Button {
                objectName: "accountProfileButton"; Layout.fillWidth: true; Layout.preferredHeight: 52
                flat: true; leftPadding: 8; rightPadding: 8
                contentItem: RowLayout {
                    spacing: 10
                    AccountAvatar { Layout.preferredWidth: 24; Layout.preferredHeight: 24; account: control.account }
                    ColumnLayout { Layout.fillWidth: true; spacing: 2
                        Text { Layout.fillWidth: true; text: control.displayName; typography: Typography.BodyStrong; elide: Text.ElideRight }
                        Text { text: control.account.plan || ""; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                    }
                    Icon { name: "ic_fluent_chevron_right_20_regular"; size: 12; color: Theme.currentTheme.colors.textSecondaryColor }
                }
                Accessible.name: I18n.t("查看个人账户")
                onClicked: control.showAccount()
            }
            Rin.MenuSeparator { Layout.fillWidth: true }
            ColumnLayout { Layout.fillWidth: true; Layout.margins: 8; spacing: 10
                AccountQuota { Layout.fillWidth: true; compact: true; usageData: control.account.usage || {} }
            }
            Rin.MenuSeparator { Layout.fillWidth: true }
            Rin.MenuItem { objectName: "accountPageMenuItem"; text: I18n.t("我的账户"); icon.name: "ic_fluent_person_20_regular"; Layout.fillWidth: true; onTriggered: control.showAccount() }
            Rin.MenuItem { objectName: "accountServiceMenuItem"; text: I18n.t("AI 服务"); icon.name: "ic_fluent_sparkle_20_regular"; Layout.fillWidth: true; onTriggered: { menu.close(); control.aiRequested() } }
            Rin.MenuItem { objectName: "accountSettingsMenuItem"; text: I18n.t("设置"); icon.name: "ic_fluent_settings_20_regular"; Layout.fillWidth: true; onTriggered: { menu.close(); control.settingsRequested() } }
            Rin.MenuItem { objectName: "accountLogoutMenuItem"; visible: !control.account.local; text: I18n.t("退出登录"); icon.name: "ic_fluent_sign_out_20_regular"; Layout.fillWidth: true; onTriggered: { menu.close(); logoutConfirm.open() } }
        }
    }
    LogoutConfirmDialog { id: logoutConfirm; objectName: "accountMenuLogoutDialog" }
}
