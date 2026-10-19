import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "AiSavedPlansPage"
    title: I18n.t("已保存方案")
    wrapperWidth: 860
    horizontalPadding: 32
    property var records: []
    property string search: ""
    readonly property var filtered: records.filter(function(record) { return !page.search.length || (record.title + " " + record.step).toLowerCase().indexOf(page.search.toLowerCase()) >= 0 })
    function reload() { try { page.records = JSON.parse(Backend.savedAiPlansJson) } catch (error) { page.records = [] } }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function openRecord(record, copy) {
        var id = copy ? Backend.copySavedAiPlan(record.id) : record.id
        if (!id || (!copy && !Backend.openSavedAiPlan(id))) return
        var router = nav()
        if (router) router.push(Qt.resolvedUrl(record.kind === "capture" ? "AiWorkspace.qml" : "AiPlanWorkspace.qml"))
    }
    function status(record) {
        var labels = {work: I18n.t("可以接着做"), paused: I18n.t("已留接续点"), review: I18n.t("这一轮已结束"), questions: I18n.t("等待补充回答"), imported: I18n.t("任务已添加"), incomplete: I18n.t("待准备当前动作"), ready: I18n.t("已准备")}
        return labels[record.status] || I18n.t("已保存")
    }
    Component.onCompleted: reload()
    Connections { target: Backend; function onAiLibraryChanged() { page.reload() } }

    Text { Layout.fillWidth: true; text: I18n.t("之前的想法和安排，都留在这里。"); typography: Typography.Subtitle; wrapMode: Text.Wrap }
    Text { Layout.fillWidth: true; text: I18n.t("打开不会重新请求 AI。已留接续点的专注从停下的位置继续；另存副本可独立修改，原方案保留。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
    JourneyField { objectName: "savedPlansSearch"; Layout.fillWidth: true; placeholderText: I18n.t("搜索方案或当前步骤"); onTextEdited: page.search = text.trim() }
    Text { visible: !page.records.length; Layout.fillWidth: true; text: I18n.t("生成方案后会自动保存，不用再点保存。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
    Text { visible: page.records.length > 0 && !page.filtered.length; Layout.fillWidth: true; text: I18n.t("没有找到匹配的方案。"); color: Theme.currentTheme.colors.textSecondaryColor }
    Repeater {
        model: page.filtered
        delegate: Frame {
            id: card
            required property var modelData
            Layout.fillWidth: true
            padding: 22
            contentItem: ColumnLayout {
                spacing: 12
                RowLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: card.modelData.title; wrapMode: Text.Wrap; typography: Typography.BodyStrong }
                    Text { text: page.status(card.modelData); typography: Typography.Caption; color: Theme.currentTheme.colors.primaryColor }
                }
                Text { visible: card.modelData.step.length > 0; Layout.fillWidth: true; text: I18n.t("记录到：") + card.modelData.step; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
                Text { Layout.fillWidth: true; text: String(card.modelData.updatedAt || card.modelData.createdAt).replace("T", " ") + " · " + (card.modelData.kind === "capture" ? I18n.t("AI 引导") : card.modelData.kind === "long" ? I18n.t("长期规划") : I18n.t("详细规划")); wrapMode: Text.Wrap; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    JourneyButton { objectName: "savedPlanCopy_" + card.modelData.id; text: I18n.t("另存副本"); flat: true; enabled: !Backend.aiRequestRunning; onClicked: page.openRecord(card.modelData, true) }
                    JourneyButton { objectName: "savedPlanOpen_" + card.modelData.id; text: I18n.t("打开"); enabled: !Backend.aiRequestRunning; onClicked: page.openRecord(card.modelData, false) }
                    JourneyButton { objectName: "savedPlanContinue_" + card.modelData.id; visible: card.modelData.resumable; highlighted: true; text: I18n.t("继续专注"); enabled: !Backend.aiRequestRunning; onClicked: Backend.continueSavedAiPlan(card.modelData.id) }
                }
            }
        }
    }
}
