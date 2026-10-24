import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as BasicControls
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
    contentSpacing: 16
    property bool assistantMode: false
    StudioTokens { id: look }
    property var account: { try { return JSON.parse(Backend.accountJson) } catch (error) { return {usage: {}} } }
    readonly property bool hasUses: account.service === "custom" || Number((account.usage || {}).remaining || 0) > 0
    property var drafts: []
    property string summary: ""
    property bool waiting: false
    property string requestError: ""
    property string lastRequestAction: ""
    property int waitingSeconds: 0
    property var cloud: { try { return JSON.parse(Backend.cloudJson) } catch (error) { return ({loggedIn: false}) } }
    readonly property bool needsLogin: page.account.service === "official" && !page.cloud.loggedIn
    readonly property bool quotaExhausted: page.account.service !== "custom" && !page.needsLogin && !page.hasUses
    function beginRequest(action) {
        page.requestError = ""; page.lastRequestAction = action; page.waitingSeconds = 0; page.waiting = true
    }
    function openService() {
        page.persistDraft(); draftSave.stop()
        if (page.needsLogin) Backend.cloudLogin()
        else { var r = page.nav(); if (r) r.push(Qt.resolvedUrl("AiSettings.qml")) }
    }
    function retryRequest() {
        if (Backend.aiRequestRunning) return
        if (!page.serviceReady) { page.openService(); return }
        if (page.lastRequestAction === "answer") page.answer()
        else if (page.lastRequestAction === "guidance") { page.beginRequest("guidance"); Backend.prepareSavedAiCapture(page.savedId) }
        else { page.beginRequest("capture"); Backend.organizeCapture(original.text.trim()) }
    }
    Timer { interval: 1000; repeat: true; running: page.waiting && Backend.aiRequestRunning; onTriggered: page.waitingSeconds++ }
    property var questions: []
    property var answerTexts: []
    property var guidance: null
    property bool showDrafts: false
    property bool editOriginal: true
    property var currentGuided: null
    property string savedId: ""
    property string generatedOriginal: ""
    readonly property bool originalChanged: page.savedId.length > 0 && original.text !== page.generatedOriginal
    property var savedJourney: null
    property bool restoring: true
    property bool newInputDirty: false
    property bool needsGuidance: false
    function newCapture() {
        page.persistDraft(); draftSave.stop()
        Backend.newAiCapture()
        page.restoring = true
        page.savedId = ""; page.generatedOriginal = ""; original.text = ""
        page.drafts = []; page.questions = []; page.answerTexts = []; page.guidance = null
        page.summary = ""; page.savedJourney = null; page.showDrafts = false; page.editOriginal = true; page.needsGuidance = false
        page.newInputDirty = false; page.requestError = ""; page.waiting = false; page.waitingSeconds = 0; page.lastRequestAction = ""
        page.restoring = false; page.refreshGuided(); original.forceActiveFocus()
    }
    function persistDraft() {
        if (page.restoring) return
        if (!page.savedId.length) {
            if (page.newInputDirty) { Backend.saveNewAiCaptureDraft(original.text); page.newInputDirty = false }
            return
        }
        Backend.saveAiCaptureDraft(page.savedId, JSON.stringify({original: original.text, drafts: page.drafts,
            answerTexts: page.questions.map(function(question, index) { return String(page.answerTexts[index] || "") }), editOriginal: page.editOriginal, showDrafts: page.showDrafts}))
    }
    function changed() { if (!page.restoring) draftSave.restart() }
    onDraftsChanged: changed()
    onAnswerTextsChanged: changed()
    onEditOriginalChanged: changed()
    onShowDraftsChanged: changed()
    Timer { id: draftSave; interval: 300; onTriggered: page.persistDraft() }
    function refreshGuided() {
        try {
            var active = JSON.parse(Backend.focusJourneyJson).active
            page.currentGuided = active && active.status !== "review" && active.source && active.source.kind === "guided" && page.savedId.length > 0 && active.source.libraryId === page.savedId ? active : null
        } catch (error) { page.currentGuided = null }
    }
    function setAnswer(index, value) { var answers = page.answerTexts.slice(); answers[index] = value; page.answerTexts = answers }
    function readPlan(plan) {
        if (!plan.captureMode || plan.capturePhase === "continue") return
        page.restoring = true
        draftSave.stop()
        page.savedId = plan.libraryId || ""
        page.generatedOriginal = plan.captureOriginal || ""
        page.drafts = plan.tasks || []
        page.summary = plan.summary || ""
        page.questions = plan.questions || []
        page.answerTexts = []
        page.guidance = plan.guidance || null
        page.needsGuidance = page.drafts.length > 0 && !page.guidance && !page.questions.length
        page.newInputDirty = false
        page.showDrafts = false
        page.editOriginal = !page.guidance && !page.questions.length
        original.text = plan.captureOriginal || ""
        page.savedJourney = null
        if (page.savedId.length) {
            var record = JSON.parse(Backend.getSavedAiPlan(page.savedId))
            var draft = record.draft || {}
            page.savedJourney = record.journey || null
            if (draft.original !== undefined) original.text = draft.original
            if (draft.drafts) page.drafts = draft.drafts
            page.answerTexts = draft.answerTexts || []
            page.showDrafts = Boolean(draft.showDrafts)
            page.editOriginal = Boolean(draft.editOriginal)
            if (original.text !== (plan.captureOriginal || "")) {
                page.editOriginal = true
            }
        }
        page.restoring = false
        page.refreshGuided()
    }
    function answer() {
        var replies = page.questions.map(function(question, index) { return {question: question.question, answer: String(page.answerTexts[index] || "") } })
        page.beginRequest("answer")
        page.persistDraft()
        Backend.respondCapture(original.text, JSON.stringify(replies), page.savedId)
    }
    readonly property bool serviceReady: Backend.aiServiceReady && page.hasUses
    function showResult() {
        try {
            var record = JSON.parse(Backend.getSelectedAiCapture())
            if (record.pendingInput !== undefined) {
                page.restoring = true; draftSave.stop(); page.savedId = ""; page.generatedOriginal = ""; page.savedJourney = null; original.text = record.pendingInput
                page.requestError = ""; page.waiting = false; page.waitingSeconds = 0; page.lastRequestAction = ""
                page.drafts = []; page.questions = []; page.answerTexts = []; page.guidance = null; page.summary = ""; page.editOriginal = true
                page.needsGuidance = false; page.newInputDirty = false; page.restoring = false; page.refreshGuided()
            } else if (record.plan) page.readPlan(record.plan)
        } catch (error) { page.requestError = I18n.t("AI 结果读取失败，你的输入已保留，请重试或重新打开这份方案。") }
    }
    Component.onCompleted: {
        page.refreshGuided()
        page.showResult()
        page.restoring = false
    }
    Component.onDestruction: { draftSave.stop(); page.persistDraft() }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    Connections {
        target: Backend
        function onFocusJourneyChanged() { page.refreshGuided() }
        function onAiStateChanged() { if (!page.waiting && Backend.aiRequestRunning === false) page.showResult() }
        function onAiRequestFinished(ok, message) {
            if (!page.waiting) return
            page.waiting = false
            if (ok) {
                page.showResult()
            } else page.requestError = message || I18n.t("这次准备失败，你的回答已保留，请重试。")
        }
    }
    Item { visible: page.assistantMode; Layout.preferredHeight: 8 }
    RowLayout {
        visible: page.assistantMode; Layout.fillWidth: true; spacing: 8
        Text { Layout.fillWidth: true; text: I18n.t("AI 助手"); font.pixelSize: 28; font.weight: Font.DemiBold; color: look.ink }
        Button { objectName: "aiSavedPlans"; flat: true; text: I18n.t("已保存"); icon.name: "ic_fluent_folder_20_regular"; onClicked: { page.persistDraft(); var r = page.nav(); if (r) r.push(Qt.resolvedUrl("AiSavedPlans.qml")) } }
        Button { id: aiMore; objectName: "aiMore"; flat: true; icon.name: "ic_fluent_more_horizontal_20_regular"; text: I18n.t("更多"); onClicked: aiMenu.open()
            QuietMenu { id: aiMenu; parent: aiMore
                MenuItem { objectName: "aiNewIdea"; text: I18n.t("新的想法"); enabled: !Backend.aiRequestRunning; onTriggered: page.newCapture() }
                MenuItem { text: I18n.t("详细规划"); onTriggered: { var r = page.nav(); if (r) r.push(Qt.resolvedUrl("AiPlanWorkspace.qml")) } }
                MenuItem { objectName: "aiServiceSettings"; text: I18n.t("服务与偏好"); onTriggered: { var r = page.nav(); if (r) r.push(Qt.resolvedUrl("AiSettings.qml")) } }
            }
        }
    }
    Item { visible: page.assistantMode && page.editOriginal && !page.savedId.length; Layout.preferredHeight: page.height < 660 ? 12 : 40 }
    Text { Layout.fillWidth: true; visible: page.originalChanged; text: I18n.t("描述已修改，可重新准备或恢复原描述。"); wrapMode: Text.Wrap; color: look.muted }
    JourneyButton { visible: page.originalChanged; text: I18n.t("恢复生成时的描述"); flat: true; enabled: !Backend.aiRequestRunning; onClicked: original.text = page.generatedOriginal }
    Frame {
        visible: page.currentGuided !== null
        Layout.fillWidth: true
        padding: 20
        background: Rectangle { radius: 18; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 12
            Text { Layout.fillWidth: true; text: page.currentGuided ? page.currentGuided.step : ""; wrapMode: Text.Wrap; typography: Typography.BodyStrong }
            JourneyButton { objectName: "captureGuidedReturn"; Layout.fillWidth: true; highlighted: true; text: I18n.t("回到当前这一段"); onClicked: Backend.returnToGuidedFocus() }
        }
    }
    Frame {
        objectName: "aiComposer"
        visible: page.editOriginal
        Layout.fillWidth: true
        padding: 20
        background: Rectangle { radius: 18; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 12
            Text { text: I18n.t("想从哪件事开始？"); font.pixelSize: 20; font.weight: Font.DemiBold; color: look.ink }
            JourneyArea { id: original; objectName: "captureOriginal"; Layout.fillWidth: true; Layout.preferredHeight: 140; wrapMode: TextArea.Wrap; placeholderText: activeFocus ? "" : I18n.t("写下你的安排…"); Accessible.name: I18n.t("想做的事"); onTextChanged: { if (!page.restoring && !page.savedId.length) page.newInputDirty = true; page.changed() } }
            Text { Layout.fillWidth: true; visible: original.text.length > 6000; text: I18n.t("原话较长，会先分段提炼再准备，约 ") + (Math.ceil(original.text.length / 2200) + 1) + I18n.t(" 次 AI 请求；原文保留。也可先缩短描述以节省额度。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                VoiceCapture { objectName: "aiVoiceCapture"; compact: true; Layout.fillWidth: false; Layout.minimumWidth: controlWidth; Layout.preferredWidth: controlWidth; Layout.maximumWidth: controlWidth; showHint: false; inputTarget: original; onRecognized: function(text) { original.text += (original.text.trim().length ? "\n" : "") + text } }
                InlineHelp { helpText: I18n.t("写下安排，也可以语音输入。确认前不会添加任务。\n每次成功的 AI 回复计 1 次，补全或长文提炼可能调用多次。\n服务与偏好在右上角的更多里。"); Layout.preferredHeight: 40 }
                Item { Layout.fillWidth: true }
                JourneyButton {
                objectName: "capturePrepare"
                Layout.preferredHeight: 44
                highlighted: true
                text: Backend.aiRequestRunning ? I18n.t("准备中…") : I18n.t("准备开始")
                icon.name: "ic_fluent_arrow_right_20_regular"
                enabled: page.serviceReady && original.text.trim().length > 0 && !Backend.aiRequestRunning && !Backend.speechInput.state.match(/recording|transcribing/)
                onClicked: { page.persistDraft(); draftSave.stop(); page.savedId = ""; page.questions = []; page.guidance = null; page.needsGuidance = false; page.drafts = []; page.summary = ""; page.beginRequest("capture"); Backend.organizeCapture(original.text.trim()) }
                }
            }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: page.needsLogin ? I18n.t("登录后可使用官方 AI，你的输入会保留") : !Backend.aiServiceReady ? I18n.t("AI 服务未就绪，请检查服务与额度") : page.account.service === "custom" ? I18n.t("自定义 API") : (page.account.plan || "Free") + I18n.t(" · 剩余 ") + Number((page.account.usage || {}).remaining || 0) + I18n.t(" 次"); font.pixelSize: 12; color: look.muted }
                JourneyButton { objectName: "captureServiceAction"; visible: !page.serviceReady; flat: true; text: page.needsLogin ? I18n.t("登录并使用 AI") : I18n.t("检查服务与额度"); onClicked: page.openService() }
            }
        }
    }
    JourneyButton { visible: !page.editOriginal; flat: true; text: I18n.t("修改刚才的描述"); onClicked: page.editOriginal = true }
    RowLayout { visible: !page.editOriginal; Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: page.account.service === "custom" ? I18n.t("自定义 API") : (page.account.plan || "Free") + I18n.t(" · 剩余 ") + Number((page.account.usage || {}).remaining || 0) + I18n.t(" 次"); font.pixelSize: 12; color: look.muted }
        JourneyButton { objectName: "captureServiceAction"; visible: !page.serviceReady; flat: true; text: page.needsLogin ? I18n.t("登录并使用 AI") : I18n.t("检查服务与额度"); onClicked: page.openService() }
    }
    Text { Layout.fillWidth: true; visible: text.length > 0 && !page.guidance; text: page.summary; wrapMode: Text.Wrap }
    Frame {
        visible: page.needsGuidance && !page.currentGuided
        Layout.fillWidth: true
        padding: 24
        background: Rectangle { radius: 18; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 14
            Text { Layout.fillWidth: true; text: I18n.t("任务已记下，准备下一步"); typography: Typography.BodyStrong; wrapMode: Text.Wrap }
            JourneyButton { objectName: "capturePrepareGuidance"; Layout.fillWidth: true; highlighted: true; text: Backend.aiRequestRunning ? I18n.t("正在准备当前动作…") : I18n.t("准备当前动作"); enabled: page.serviceReady && !Backend.aiRequestRunning && !page.originalChanged; onClicked: { page.persistDraft(); draftSave.stop(); page.beginRequest("guidance"); Backend.prepareSavedAiCapture(page.savedId) } }
        }
    }
    Repeater {
        model: page.questions
        delegate: Frame {
            id: questionCard
            required property var modelData
            required property int index
            Layout.fillWidth: true
            padding: 20
            background: Rectangle { radius: 16; color: look.surface; border.color: look.stroke }
            contentItem: ColumnLayout {
                spacing: 12
                Text { Layout.fillWidth: true; text: questionCard.modelData.question; wrapMode: Text.Wrap; typography: Typography.BodyStrong }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Repeater {
                        model: questionCard.modelData.choices || []
                        delegate: JourneyButton {
                            required property string modelData
                            text: modelData
                            highlighted: page.answerTexts[questionCard.index] === modelData
                            enabled: !page.waiting
                            onClicked: page.setAnswer(questionCard.index, modelData)
                        }
                    }
                }
                JourneyField { objectName: "captureAnswer_" + questionCard.index; Layout.fillWidth: true; maximumLength: 500; placeholderText: I18n.t("也可以直接说你的想法"); text: String(page.answerTexts[questionCard.index] || ""); enabled: !page.waiting; onTextEdited: page.setAnswer(questionCard.index, text) }
            }
        }
    }
    RowLayout {
        visible: page.questions.length > 0
        Layout.fillWidth: true
        JourneyButton { objectName: "captureAnswer"; Layout.fillWidth: true; highlighted: true; text: page.waiting ? I18n.t("正在准备…") : I18n.t("按我的回答准备"); enabled: page.serviceReady && !Backend.aiRequestRunning && !page.originalChanged && page.answerTexts.some(function(text) { return text && text.trim().length }); onClicked: page.answer() }
        JourneyButton { text: I18n.t("先替我选个起点"); enabled: page.serviceReady && !Backend.aiRequestRunning && !page.originalChanged; onClicked: { page.answerTexts = []; page.answer() } }
    }
    Frame {
        objectName: "captureQuotaNotice"; visible: page.quotaExhausted
        Layout.fillWidth: true; padding: 18
        background: Rectangle { radius: 14; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 12
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; color: look.ink; text: I18n.t("AI 剩余 0 次，额度已用完。请接入自己的 API，或升级账号后继续；你的输入已保留。") }
            Flow {
                Layout.fillWidth: true; spacing: 10
                JourneyButton { objectName: "captureOwnApi"; text: I18n.t("接入自己的 API"); onClicked: { page.persistDraft(); draftSave.stop(); var r = page.nav(); if (r) r.push(Qt.resolvedUrl("AiSettings.qml")) } }
                JourneyButton { objectName: "captureUpgrade"; text: I18n.t("升级账号"); onClicked: upgradeInfo.open() }
            }
        }
    }
    BasicControls.Dialog {
        id: upgradeInfo; objectName: "captureUpgradeInfo"
        parent: BasicControls.Overlay.overlay; anchors.centerIn: parent
        width: Math.min(440, parent.width - 40); modal: true
        title: I18n.t("升级账号与额度")
        standardButtons: BasicControls.Dialog.Close
        contentItem: ColumnLayout {
            spacing: 16
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; color: look.ink; text: I18n.t("账号套餐和官方 AI 额度目前由账户后台管理。请登录后联系服务管理员升级，再刷新账户。你也可以接入自己的 API，不消耗官方额度。") }
            JourneyButton { text: page.cloud.loggedIn ? I18n.t("打开账户管理") : I18n.t("登录账户"); onClicked: { page.persistDraft(); draftSave.stop(); upgradeInfo.close(); if (!page.cloud.loggedIn) Backend.cloudLogin(); else { var r = page.nav(); if (r) r.push(Qt.resolvedUrl("UserAccount.qml")) } } }
        }
    }
    Frame {
        objectName: "captureRequestFeedback"
        visible: page.waiting || (page.requestError.length > 0 && !page.quotaExhausted)
        Layout.fillWidth: true; padding: 18
        background: Rectangle { radius: 14; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 10
            BasicControls.ProgressBar {
                id: requestProgress; objectName: "captureProgressBar"
                Layout.fillWidth: true; Layout.preferredHeight: 6
                visible: page.waiting; indeterminate: true
                Accessible.name: I18n.t("AI 正在准备")
                background: Rectangle { radius: 3; color: look.stroke }
                contentItem: Item {
                    clip: true
                    Rectangle {
                        id: requestIndicator; width: parent.width * 0.28; height: parent.height
                        radius: 3; color: look.accent
                        SequentialAnimation on x {
                            running: requestProgress.visible; loops: Animation.Infinite
                            NumberAnimation { from: 0; to: requestProgress.availableWidth - requestIndicator.width; duration: 1000; easing.type: Easing.InOutSine }
                            NumberAnimation { from: requestProgress.availableWidth - requestIndicator.width; to: 0; duration: 1000; easing.type: Easing.InOutSine }
                        }
                    }
                }
            }
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; color: look.ink; text: page.waiting ? I18n.t("AI 正在处理，已等待 ") + page.waitingSeconds + I18n.t(" 秒。") : page.requestError }
            Text { Layout.fillWidth: true; visible: page.waiting && page.waitingSeconds >= 60; wrapMode: Text.Wrap; color: look.muted; text: I18n.t("这次耗时较长，仍在等待结果。失败会在这里显示，不用重复提交。") }
            JourneyButton { objectName: "captureRetry"; visible: !page.waiting && page.requestError.length > 0; text: page.needsLogin ? I18n.t("登录并继续") : I18n.t("重试这一步"); enabled: !Backend.aiRequestRunning; onClicked: page.retryRequest() }
        }
    }
    Frame {
        visible: page.guidance !== null && !page.currentGuided
        Layout.fillWidth: true
        padding: 24
        background: Rectangle { radius: 18; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 16
            Text { Layout.fillWidth: true; text: page.guidance ? page.guidance.intro : ""; typography: Typography.Subtitle; wrapMode: Text.Wrap }
            Text { Layout.fillWidth: true; text: page.guidance ? page.guidance.steps[0].title : ""; wrapMode: Text.Wrap }
            JourneyButton { objectName: "captureGuidedStart"; Layout.fillWidth: true; highlighted: true; text: page.savedJourney && (page.savedJourney.status === "work" || page.savedJourney.status === "paused") ? I18n.t("继续保存的专注") : page.guidance ? I18n.t("准备好了，带我开始") + " · " + page.guidance.steps[0].minutes + I18n.t(" 分钟") : ""; enabled: !Backend.aiRequestRunning && !page.originalChanged; onClicked: { page.persistDraft(); if (page.savedJourney && (page.savedJourney.status === "work" || page.savedJourney.status === "paused")) Backend.continueSavedAiPlan(page.savedId); else Backend.startGuidedCapture(page.savedId) } }
            InlineHelp { Layout.alignment: Qt.AlignRight; helpText: I18n.t("全屏只显示当前步骤，可休息或调整节奏。\n重新准备或调整会调用 AI；倒计时不消耗使用次数。") }
        }
    }
    JourneyButton { visible: page.drafts.length > 0 && (page.guidance !== null || page.questions.length > 0); text: page.showDrafts ? I18n.t("收起任务清单") : I18n.t("查看或仅添加任务清单"); flat: true; onClicked: page.showDrafts = !page.showDrafts }
    Repeater {
        model: page.showDrafts || (!page.guidance && !page.questions.length) ? page.drafts : []
        delegate: Frame {
            required property var modelData
            required property int index
            property bool selected: true
            property string editedTitle: modelData.title
            Layout.fillWidth: true
            padding: 16
            background: Rectangle { radius: 14; color: look.surface; border.color: look.stroke }
            contentItem: RowLayout {
                spacing: 12
                CheckBox { objectName: "captureSelect_" + index; checked: !modelData._skip; onToggled: { var items = page.drafts.slice(); items[index] = Object.assign({}, modelData, {_skip: !checked}); page.drafts = items } }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    JourneyField { objectName: "captureTitle_" + index; Layout.fillWidth: true; text: modelData.title; onTextEdited: { var items = page.drafts.slice(); items[index] = Object.assign({}, modelData, {title: text}); page.drafts = items } }
                    Text { Layout.fillWidth: true; text: String(modelData.meta || "") + (modelData.scheduledDate ? " · " + modelData.scheduledDate + " " + (modelData.scheduledTime || "") : ""); wrapMode: Text.Wrap; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                }
            }
        }
    }
    JourneyButton {
        Layout.fillWidth: true
        visible: page.drafts.length > 0 && (page.showDrafts || (!page.guidance && !page.questions.length))
        text: I18n.t("添加选中的任务")
        highlighted: !page.guidance
        enabled: page.drafts.some(function(task) { return !task._skip && task.title.trim().length })
        onClicked: {
            var tasks = page.drafts.filter(function(task) { return !task._skip && task.title.trim().length }).map(function(task) { var item = Object.assign({}, task); delete item._skip; return item })
            if (Backend.importCapture(JSON.stringify(tasks), page.savedId)) { page.drafts = []; page.questions = []; page.answerTexts = []; page.summary = I18n.t("已记下。原方案已保存，之后仍可打开。") }
        }
    }
}
