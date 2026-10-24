import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "QuickCapturePage"
    title: I18n.t("随口记下")
    wrapperWidth: 760
    horizontalPadding: 32
    contentSpacing: 18
    property string batchId: ""
    property var drafts: []
    property bool restoring: true
    property bool draftDirty: false
    property string error: ""
    property string receipt: ""
    property bool waiting: false
    property string requestId: ""
    property string sentOriginal: ""
    // Stable stored values; only the dropdown labels are translated.
    readonly property var categoryKeys: ["其他", "学习", "工作", "生活"]
    readonly property bool serviceReady: Backend.aiServiceReady
    readonly property var selected: drafts.filter(function(task) { return !task._skip && task.title.trim().length })
    function persist() {
        if (!page.restoring && page.draftDirty && page.batchId.length) {
            if (Backend.saveQuickCaptureDraft(JSON.stringify({batchId: page.batchId, original: original.text, tasks: page.drafts}))) page.draftDirty = false
        }
    }
    function restore() {
        page.restoring = true
        var draft = JSON.parse(Backend.getQuickCaptureDraft())
        page.batchId = draft.batchId; original.text = draft.original || ""; page.drafts = draft.tasks || []
        page.draftDirty = false; page.restoring = false
    }
    function localPreview() {
        if (page.restoring) return
        var result = JSON.parse(Backend.previewQuickCapture(original.text))
        page.drafts = result.tasks || []; page.error = result.error || ""
        page.draftDirty = true
        saveTimer.restart()
    }
    function editTask(index, fields) {
        var tasks = page.drafts.slice(); tasks[index] = Object.assign({}, tasks[index], fields)
        page.drafts = tasks; page.draftDirty = true; saveTimer.restart()
    }
    function submit() {
        saveTimer.stop(); page.persist()
        var result = JSON.parse(Backend.addQuickCapture(JSON.stringify({batchId: page.batchId,
            tasks: page.selected.map(function(task) { return {title: task.title, category: task.category || "其他"} })})))
        if (!result.ok) { page.error = result.error; return }
        page.requestId = ""; page.waiting = false
        page.restore(); page.error = ""; page.receipt = I18n.t("已记下 ") + result.total + I18n.t(" 件事，可以继续说下一件。")
        original.forceActiveFocus()
    }
    function organize() {
        page.sentOriginal = original.text
        page.requestId = page.batchId + "-" + Date.now()
        page.persist(); page.error = ""
        page.waiting = Backend.organizeQuickCapture(page.sentOriginal, page.requestId)
    }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    Timer { id: saveTimer; interval: 300; onTriggered: page.persist() }
    Component.onCompleted: restore()
    Component.onDestruction: { saveTimer.stop(); page.persist() }
    Connections {
        target: Backend
        function onQuickCaptureReady(id, tasks, message) {
            if (id !== page.requestId) return
            page.waiting = false; page.requestId = ""
            if (original.text !== page.sentOriginal) { page.error = I18n.t("原话已改变，这次整理没有覆盖新内容。"); return }
            if (message.length) { page.error = message; return }
            page.drafts = JSON.parse(tasks); page.draftDirty = true; page.persist()
        }
    }
    Text { Layout.fillWidth: true; text: I18n.t("想到就记下，记完再说下一件。"); typography: Typography.Subtitle; wrapMode: Text.Wrap }
    Text { Layout.fillWidth: true; text: I18n.t("语音和文字都可以。默认直接记录，不用配置 AI，也不消耗 AI API 额度。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
    Frame {
        Layout.fillWidth: true; padding: 22
        contentItem: ColumnLayout {
            spacing: 14
            VoiceCapture { Layout.fillWidth: true; inputTarget: original; forceSystem: true; allowDuringAi: true }
            JourneyArea {
                id: original; objectName: "quickCaptureOriginal"
                Layout.fillWidth: true; Layout.preferredHeight: 145
                wrapMode: TextArea.Wrap
                placeholderText: I18n.t("买猫粮；交报告；给同学回消息\n也可以每行写一件事")
                onTextChanged: page.localPreview()
            }
            Text { Layout.fillWidth: true; text: I18n.t("多件事用换行、分号或句号隔开；普通逗号会保留。记下后输入框会清空，接着记下一批。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            RowLayout {
                Layout.fillWidth: true
                JourneyButton { objectName: "quickCaptureOrganize"; text: page.waiting ? I18n.t("正在整理…") : I18n.t("AI 拆分与分类（可选）"); enabled: !page.waiting && !Backend.aiRequestRunning && original.text.trim().length > 0 && original.text.length <= 4000; onClicked: { if (page.serviceReady) page.organize(); else { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("AiSettings.qml")) } } }
                Item { Layout.fillWidth: true }
                JourneyButton { objectName: "quickCaptureSubmit"; highlighted: true; text: page.selected.length ? I18n.t("记下 ") + page.selected.length + I18n.t(" 件事") : I18n.t("记下"); enabled: page.selected.length > 0; onClicked: page.submit() }
            }
            Text { Layout.fillWidth: true; text: I18n.t("可选 AI 只拆分与分类当前这段原话，不带旧对话、不生成专注计划，只发送一次请求。返回后仍由你确认。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
    Text { Layout.fillWidth: true; visible: page.receipt.length > 0; text: page.receipt; color: Theme.currentTheme.colors.primaryColor; wrapMode: Text.Wrap }
    Text { Layout.fillWidth: true; visible: page.error.length > 0; text: page.error; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap }
    Text { visible: page.drafts.length > 0; text: I18n.t("这次记下 · ") + page.drafts.length + I18n.t(" 件事"); typography: Typography.BodyStrong }
    Repeater {
        model: page.drafts
        delegate: Frame {
            id: card
            required property var modelData
            required property int index
            Layout.fillWidth: true; padding: 14
            contentItem: RowLayout {
                spacing: 10
                CheckBox { checked: !card.modelData._skip; onToggled: page.editTask(card.index, {_skip: !checked}) }
                JourneyField { objectName: "quickCaptureTitle_" + card.index; Layout.fillWidth: true; Layout.minimumWidth: 0; text: card.modelData.title; maximumLength: 400; onTextEdited: page.editTask(card.index, {title: text}) }
                JourneyCombo { objectName: "quickCaptureCategory_" + card.index; Layout.preferredWidth: 105; model: [I18n.t("其他"), I18n.t("学习"), I18n.t("工作"), I18n.t("生活")]; currentIndex: Math.max(0, page.categoryKeys.indexOf(card.modelData.category || "其他")); onActivated: page.editTask(card.index, {category: page.categoryKeys[currentIndex]}) }
            }
        }
    }
}
