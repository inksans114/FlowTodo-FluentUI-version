import QtQuick
import "../i18n"
import QtQuick.Controls as QQC
import QtQuick.Layouts
import RinUI
import RinUI as Rin
import "../components"
FluentPage {
    id: page
    title: ""
    wrapperWidth: 920
    horizontalPadding: width < 740 ? 24 : 40
    contentSpacing: 20
    property var cloud: { try { return JSON.parse(Backend.cloudJson) } catch(e) { return ({}) } }
    property var account: cloud.account || ({})
    property var usage: account.usage || ({})
    property bool trash: false
    property var pending: null
    StudioTokens { id: ui }
    Component.onCompleted: if (page.cloud.loggedIn) Backend.cloudBrowse(false)
    function load(t) { trash=t; Backend.cloudBrowse(t) }
    function describe(item) {
        var p=item.payload || {}, r=p.record || p, lines=[]
        if(item.kind === "tasks") lines.push(r.done ? I18n.t("状态：已完成") : I18n.t("状态：待完成"))
        if(r.scheduledDate) lines.push(I18n.t("日期：") + r.scheduledDate)
        if(p.note || r.meta || r.description) lines.push(p.note || r.meta || r.description)
        var steps=r.steps || (r.plan || {}).tasks || []
        for(var i=0;i<steps.length;i++) lines.push((i+1) + ". " + (steps[i].name || steps[i].title || I18n.t("步骤")) + (steps[i].duration ? " · " + steps[i].duration + I18n.t(" 分钟") : ""))
        if(r.captureOriginal || (r.plan || {}).captureOriginal) lines.push(r.captureOriginal || r.plan.captureOriginal)
        return lines.length ? lines.join("\n\n") : I18n.t("这条记录没有额外说明。")
    }
    RowLayout {
        Layout.fillWidth: true
        ColumnLayout { Layout.fillWidth: true; spacing: 8
            Text { text: I18n.t("云端存储"); color: ui.ink; font.pixelSize: 28; font.weight: Font.Bold }
            Text { text: I18n.t("你的记录，在襄阳保存。"); color: ui.muted; font.pixelSize: 14 }
        }
        Rin.Button { objectName: "cloudSyncAllButton"; text: I18n.t("一键同步全部"); icon.name: "ic_fluent_cloud_sync_20_regular"; highlighted: true; enabled: page.cloud.loggedIn && !page.cloud.busy; onClicked: Backend.cloudSyncAll() }
    }
    Rin.Frame {
        Layout.fillWidth: true; padding: 20
        background: Rectangle { color: ui.tint; radius: 16; border.color: ui.stroke }
        contentItem: ColumnLayout { spacing: 12
            Text { text: I18n.t("已使用 ") + Number(page.usage.storageMB || 0).toFixed(2) + " MB"; font.pixelSize: 20; font.weight: Font.DemiBold; color: ui.ink }
            Text { text: I18n.t("待办 ") + (page.usage.tasks || 0) + I18n.t("   ·   任务流 ") + (page.usage.flows || 0) + I18n.t("   ·   AI 方案 ") + (page.usage.aiPlans || 0); color: ui.muted; font.pixelSize: 13 }
            Text { Layout.fillWidth: true; text: I18n.t("同步会上传本机记录并获取云端更新。删除只影响云端副本，本机记录保留。"); wrapMode: Text.Wrap; color: ui.muted; font.pixelSize: 12 }
        }
    }
    RowLayout { Layout.fillWidth: true
        Rin.Button { text: I18n.t("我的记录"); highlighted: !page.trash; enabled: !page.cloud.busy; onClicked: page.load(false) }
        Rin.Button { text: I18n.t("回收站"); highlighted: page.trash; enabled: !page.cloud.busy; onClicked: page.load(true) }
        Rin.Button { objectName: "cloudImportAllButton"; text: I18n.t("全部导入本机"); visible: !page.trash; enabled: page.cloud.loggedIn && !page.cloud.busy; onClicked: { page.importId=""; importConfirm.open() } }
        Item { Layout.fillWidth: true }
        Rin.Button { text: I18n.t("刷新"); enabled: !page.cloud.busy; onClicked: page.load(page.trash) }
    }
    Text { visible: page.cloud.busy; text: I18n.t("正在连接襄阳…"); color: ui.muted }
    Text { visible: Boolean(page.cloud.error); text: page.cloud.error || ""; wrapMode: Text.Wrap; Layout.fillWidth: true; color: "#bc4545" }
    Text { visible: !page.cloud.busy; text: page.cloud.status || ""; color: ui.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12 }
    Text { visible: page.trash; text: I18n.t("回收站保留 7 天，恢复时会检查套餐额度。"); color: ui.muted; font.pixelSize: 12 }
    Rin.Frame {
        visible: !page.cloud.busy && !(page.cloud.library || []).length
        Layout.fillWidth: true; padding: 36
        contentItem: ColumnLayout { spacing: 12
            Icon { Layout.alignment: Qt.AlignHCenter; name: "ic_fluent_cloud_20_regular"; size: 32; color: ui.accent }
            Text { Layout.alignment: Qt.AlignHCenter; text: page.trash ? I18n.t("回收站为空") : I18n.t("这里还没有云端记录"); font.pixelSize: 18; color: ui.ink }
            Text { Layout.alignment: Qt.AlignHCenter; text: I18n.t("点击一键同步，让今天的进展留在云端。"); color: ui.muted; font.pixelSize: 12 }
        }
    }
    Repeater {
        model: page.cloud.library || []
        delegate: Rin.Frame {
            id: card
            objectName: "cloudRecordCard"
            required property var modelData
            property bool expanded: false
            Layout.fillWidth: true; padding: 20
            background: Rectangle { color: ui.surface; radius: 14; border.color: ui.stroke }
            contentItem: ColumnLayout { spacing: 12
                RowLayout { Layout.fillWidth: true; spacing: 12
                    Icon { name: "ic_fluent_document_20_regular"; size: 22; color: ui.accent }
                    ColumnLayout { Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 6
                        Text { Layout.fillWidth: true; text: card.modelData.title; font.pixelSize: 16; font.weight: Font.DemiBold; color: ui.ink; elide: Text.ElideRight }
                        Text { text: ({tasks:I18n.t("待办"),flows:I18n.t("任务流"),aiPlans:I18n.t("AI 方案")})[card.modelData.kind] + " · " + String(card.modelData.updatedAt || "").slice(0,10); font.pixelSize: 12; color: ui.muted }
                    }
                    Rin.Button { text: card.expanded ? I18n.t("收起") : I18n.t("查看"); onClicked: card.expanded=!card.expanded }
                    Rin.Button { text: I18n.t("导入本机"); visible: !page.trash; enabled: page.cloud.loggedIn && !page.cloud.busy; onClicked: { page.importId=card.modelData.id; importConfirm.open() } }
                    Rin.Button { text: page.trash ? I18n.t("恢复") : I18n.t("删除"); enabled: !page.cloud.busy; onClicked: { page.pending=card.modelData; confirm.open() } }
                }
                Text { objectName: "cloudRecordDetail"; visible: card.expanded; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText; text: page.describe(card.modelData); color: ui.muted; font.pixelSize: 13; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.5 }
            }
        }
    }
    property string importId: ""
    QQC.Dialog {
        id: importConfirm
        parent: QQC.Overlay.overlay
        width: Math.min(380,parent.width-32)
        anchors.centerIn: parent
        title: page.importId ? I18n.t("导入这条记录到本机？") : I18n.t("导入全部云端记录？")
        modal: true
        standardButtons: QQC.Dialog.Ok | QQC.Dialog.Cancel
        contentItem: Text { text: I18n.t("待办、任务流和 AI 方案会导入对应页面。\n本机已有记录会跳过，不会覆盖本机修改；AI 方案不会自动开始执行。"); wrapMode: Text.Wrap; color: ui.ink; textFormat: Text.PlainText; lineHeightMode: Text.ProportionalHeight; lineHeight: 1.5 }
        onAccepted: Backend.cloudImport(page.importId)
    }
    QQC.Dialog { id: confirm; parent: QQC.Overlay.overlay; width: Math.min(360,parent.width-32); anchors.centerIn: parent; modal: true; title: page.trash ? I18n.t("恢复云端记录？") : I18n.t("移到云端回收站？"); standardButtons: QQC.Dialog.Ok | QQC.Dialog.Cancel; contentItem: Text { width: 300; text: (page.pending ? page.pending.title : "") + I18n.t("\n本机记录会保留。"); wrapMode: Text.Wrap; color: ui.ink } onAccepted: if (page.pending) Backend.cloudRecordAction(page.pending.id,page.pending.version,page.trash) }
}
