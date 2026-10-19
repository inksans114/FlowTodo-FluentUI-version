import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import RinUI
import RinUI as Rin
import "../components"
import "../i18n"
FluentPage {
    id: page
    title: ""
    wrapperWidth: 920
    horizontalPadding: width < 740 ? 28 : 48
    contentSpacing: 24
    property var account: { try { return JSON.parse(Backend.accountJson) } catch (error) { return {name: "", usage: {}} } }
    readonly property var stats: { try { return JSON.parse(Backend.statsJson) } catch (error) { return {tasks: {}, focus: {}} } }
    property var cloud: { try { return JSON.parse(Backend.cloudJson) } catch(e) { return ({}) } }
    property var records: { Backend.accountJson; try { return JSON.parse(Backend.cloudRecordsJson) } catch(e) { return [] } }
    property var selected: ({})
    readonly property var usage: account.usage || ({})
    function router() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function openService() { var view = router(); if (view) view.push(Qt.resolvedUrl("AiSettings.qml")) }
    function importAvatar() { var candidate = Backend.chooseAccountAvatar(); if (candidate) cropDialog.present(candidate) }
    StudioTokens { id: ui }
    Item { Layout.preferredHeight: 14 }
    ColumnLayout { Layout.fillWidth: true; spacing: 6
        Text { text: I18n.t("我的账户"); font.pixelSize: 28; font.weight: Font.DemiBold; color: ui.ink }
        Text { text: I18n.t("个人资料、专注数据与 AI 使用"); font.pixelSize: 13; color: ui.muted }
    }
    Rin.Frame {
        Layout.fillWidth: true; padding: 24
        background: Rectangle { radius: ui.radius; color: ui.surface; border.color: ui.stroke }
        contentItem: RowLayout {
            spacing: 16
            Rin.Button {
                objectName: "accountAvatarButton"; flat: true
                enabled: Boolean(page.cloud.loggedIn)
                Layout.preferredWidth: 48; Layout.preferredHeight: 48; padding: 4
                contentItem: AccountAvatar { account: page.account }
                Accessible.name: I18n.t("导入并裁剪头像")
                onClicked: page.importAvatar()
            }
            ColumnLayout { Layout.fillWidth: true; spacing: 6
                Text { Layout.fillWidth: true; text: page.account.name; font.pixelSize: 20; font.weight: Font.DemiBold; color: ui.ink; elide: Text.ElideRight }
                Text { Layout.fillWidth: true; elide: Text.ElideRight; text: page.account.local ? "本地访客" : page.account.handle; font.pixelSize: 12; color: ui.muted }
                AccountPlanBadge { plan: page.account.planId || "free" }
            }
            Rin.Button { objectName: "accountEditButton"; text: I18n.t("编辑资料"); enabled: Boolean(page.cloud.loggedIn); icon.name: "ic_fluent_edit_20_regular"; onClicked: { nickname.text = page.account.name; editDialog.open() } }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Rin.Button { objectName: "accountCloudStorageButton"; text: "管理云端存储"; icon.name: "ic_fluent_cloud_20_regular"; highlighted: true; enabled: page.cloud.loggedIn; onClicked: { var view=page.router(); if(view) view.push(Qt.resolvedUrl("CloudStorage.qml")) } }
        Rin.Button { text: "刷新账户"; enabled: page.cloud.loggedIn && !page.cloud.busy; onClicked: Backend.cloudRefresh() }
        Item { Layout.fillWidth: true }
        Rin.Button { objectName: "accountLogoutButton"; text: page.cloud.loggedIn ? "退出登录" : "登录账户"; enabled: page.cloud.loggedIn || !page.cloud.busy; onClicked: page.cloud.loggedIn ? logoutDialog.open() : Backend.cloudLogin() }
    }
    Text { visible: Boolean(page.cloud.error); text: page.cloud.error || ""; color: "#bc4545"; wrapMode: Text.Wrap; Layout.fillWidth: true }
    Rin.Frame {
        visible: Boolean(page.cloud.loggedIn); Layout.fillWidth: true; padding: 20
        background: Rectangle { radius: ui.radius; color: ui.surface; border.color: ui.stroke }
        contentItem: RowLayout {
            spacing: 16
            ColumnLayout { Layout.fillWidth: true; spacing: 5
                Text { text: "手机与电脑自动同步"; font.pixelSize: 14; font.weight: Font.DemiBold; color: ui.ink }
                Text { Layout.fillWidth: true; text: page.cloud.autoSync ? (page.cloud.lastSync ? "上次同步 " + page.cloud.lastSync : "应用运行时同步待办与任务流") : "已关闭自动同步，仍可手动同步"; font.pixelSize: 12; color: ui.muted; wrapMode: Text.Wrap }
                Text { visible: Boolean((page.cloud.conflicts || []).length); text: "有同步冲突，请在云端存储页面确认版本"; font.pixelSize: 12; color: "#bc4545"; wrapMode: Text.Wrap }
            }
            Rin.Switch { objectName: "accountAutoSync"; checked: Boolean(page.cloud.autoSync); checkedText: "开启"; uncheckedText: "关闭"; onClicked: Backend.setSetting("cloudAutoSync", checked) }
        }
    }
    LogoutConfirmDialog { id: logoutDialog; objectName: "accountPageLogoutDialog" }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 12
        Text { text: I18n.t("我的数据"); font.pixelSize: 18; font.weight: Font.DemiBold; color: ui.ink }
        GridLayout {
            Layout.fillWidth: true
            objectName: "metricGrid"
            uniformCellWidths: true
            columns: width >= 900 ? 4 : 2
            columnSpacing: 8
            rowSpacing: 8
            MetricCard { Layout.fillWidth: true; Layout.minimumWidth: 0; objectName: "focusTotalCard"; label: I18n.t("累计专注"); value: String((page.stats.focus || {}).totalMinutes || 0) + I18n.t(" 分钟"); iconName: "ic_fluent_timer_20_regular"; accent: "#0f6cbd" }
            MetricCard { Layout.fillWidth: true; Layout.minimumWidth: 0; objectName: "focusTodayCard"; label: I18n.t("今日专注"); value: String((page.stats.focus || {}).todayMinutes || 0) + I18n.t(" 分钟"); iconName: "ic_fluent_weather_sunny_20_regular"; accent: "#107c10" }
            MetricCard { Layout.fillWidth: true; Layout.minimumWidth: 0; objectName: "focusSessionsCard"; label: I18n.t("专注次数"); value: String((page.stats.focus || {}).totalSessions || 0); iconName: "ic_fluent_history_20_regular"; accent: "#8764b8" }
            MetricCard { Layout.fillWidth: true; Layout.minimumWidth: 0; objectName: "tasksCompletedCard"; label: I18n.t("累计完成"); value: String((page.stats.tasks || {}).done || 0); iconName: "ic_fluent_checkmark_circle_20_regular"; accent: "#d83b01" }
        }

        Rin.Button {
            objectName: "accountFocusDataButton"
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            leftPadding: 20; rightPadding: 20
            Accessible.name: I18n.t("我的专注数据")
            contentItem: RowLayout {
                spacing: 16
                Icon { name: "ic_fluent_data_bar_vertical_20_regular"; size: 24; color: ui.accent }
                Text { Layout.fillWidth: true; text: I18n.t("我的专注数据"); font.pixelSize: 14; color: ui.ink }
                Icon { name: "ic_fluent_chevron_right_20_regular"; size: 16; color: ui.muted }
            }
            onClicked: { var view = page.router(); if (view) view.push(Qt.resolvedUrl("AccountOverview.qml")) }
        }
    }
    Rin.Frame {
        Layout.fillWidth: true; padding: 24
        background: Rectangle { radius: ui.radius; color: ui.tint; border.color: ui.stroke }
        contentItem: RowLayout {
            spacing: 16
            Icon { name: "ic_fluent_sparkle_20_regular"; size: 28; color: ui.accent }
            ColumnLayout { Layout.fillWidth: true; spacing: 6
                Text { text: page.account.plan; font.pixelSize: 18; font.weight: Font.DemiBold; color: ui.ink }
                Text { Layout.fillWidth: true; text: page.cloud.loggedIn ? "官方 AI · 本期 " + Number(((page.cloud.account || {}).officialAI || {}).limit || 0) + " 次，剩余 " + Number(((page.cloud.account || {}).officialAI || {}).remaining || 0) + " 次" : "本机 AI 体验 · 共 " + Number(page.usage.limit || 5) + " 次"; font.pixelSize: 13; color: ui.muted; wrapMode: Text.Wrap }
            }
            Rin.Button { objectName: "accountManageServiceButton"; text: I18n.t("管理服务"); onClicked: page.openService() }
        }
    }
    RowLayout { Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: I18n.t("AI 使用次数"); font.pixelSize: 18; font.weight: Font.DemiBold; color: ui.ink }
        Text { text: page.account.plan; font.pixelSize: 12; color: ui.muted }
    }
    Rin.Frame {
        Layout.fillWidth: true; padding: 24
        background: Rectangle { radius: ui.radius; color: ui.surface; border.color: ui.stroke }
        contentItem: ColumnLayout {
            spacing: 16
            RowLayout { Layout.fillWidth: true; spacing: 8
                Text { text: page.usage.status === "provider" ? Number(page.usage.used || 0).toLocaleString() : String(page.usage.remaining || 0); font.pixelSize: 40; font.weight: Font.DemiBold; color: ui.ink }
                Text { Layout.alignment: Qt.AlignBottom; Layout.bottomMargin: 7; text: page.usage.status === "provider" ? I18n.t("次已使用") : I18n.t("次剩余"); font.pixelSize: 14; color: ui.muted }
                Item { Layout.fillWidth: true }
                Icon { name: "ic_fluent_sparkle_20_regular"; size: 24; color: ui.accent }
            }
            AccountQuota { Layout.fillWidth: true; compact: true; usageData: page.usage; showTitle: false }
            RowLayout { Layout.fillWidth: true; spacing: 12
                Text { Layout.fillWidth: true; text: page.usage.status === "provider" ? I18n.t("不消耗 Free 次数") : "成功回复计 1 次；结果不确定时暂时保留额度。"; font.pixelSize: 12; color: ui.muted; wrapMode: Text.Wrap }
                Rin.Button { visible: page.usage.status === "exhausted"; text: I18n.t("接入自己的 API"); onClicked: page.openService() }
            }
        }
    }
    Text { visible: Boolean(page.usage.historyIncomplete); Layout.fillWidth: true; text: I18n.t("旧版本使用记录不完整，次数从可恢复的记录累计。"); font.pixelSize: 12; color: ui.muted; wrapMode: Text.Wrap }
    RowLayout { Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: I18n.t("本机累计使用"); font.pixelSize: 14; color: ui.ink }
        Text { text: Number(page.account.totalRequests || 0).toLocaleString() + I18n.t(" 次"); font.pixelSize: 13; color: ui.muted }
    }
    Item { Layout.preferredHeight: 20 }
    AvatarCropDialog { id: cropDialog }
    Rin.Dialog {
        id: editDialog; objectName: "accountEditDialog"; parent: QQC.Overlay.overlay
        title: I18n.t("编辑资料"); width: Math.min(400, parent.width - 32); modal: true
        standardButtons: QQC.Dialog.NoButton
        onOpened: { nickname.forceActiveFocus(); nickname.selectAll() }
        contentItem: ColumnLayout {
            spacing: 16
            Text { text: editDialog.title; typography: Typography.Subtitle }
            RowLayout {
                Layout.fillWidth: true; spacing: 12
                AccountAvatar { Layout.preferredWidth: 32; Layout.preferredHeight: 32; account: page.account }
                Rin.Button { objectName: "accountImportAvatar"; text: I18n.t("选择本地图片"); onClicked: page.importAvatar() }
                Rin.Button { visible: Boolean(page.account.avatarUrl); flat: true; text: I18n.t("移除"); onClicked: Backend.removeAccountAvatar() }
            }
            Text { text: I18n.t("昵称"); typography: Typography.Caption }
            Rin.TextField { id: nickname; objectName: "accountNickname"; Layout.fillWidth: true; maximumLength: 40; placeholderText: I18n.t("输入昵称"); onAccepted: { if (Backend.renameAccount(text)) editDialog.close() } }
        }
        footer: Rin.DialogButtonBox {
            Rin.Button { objectName: "accountCancelButton"; Layout.fillWidth: true; text: I18n.t("取消"); onClicked: editDialog.close() }
            Rin.Button { objectName: "accountSaveButton"; Layout.fillWidth: true; text: I18n.t("保存"); highlighted: true; enabled: nickname.text.trim().length > 0; onClicked: { if (Backend.renameAccount(nickname.text)) editDialog.close() } }
        }
    }
}
