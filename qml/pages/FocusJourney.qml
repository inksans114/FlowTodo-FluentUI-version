import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "focusJourneyPage"
    title: ""
    wrapperWidth: 720
    horizontalPadding: 32
    contentSpacing: 16
    StudioTokens { id: look }
    property double initialTaskId: -1
    property double selectedTaskId: -1
    property int durationMinutes: Number(Backend.getSetting("focusQuickDuration", 5))
    property bool shieldEnabled: false
    property bool showAdvanced: false
    property bool showTaskPicker: false
    property bool customDuration: false
    property bool immersive: Boolean(Backend.getSetting("focusImmersive", false))
    property string sceneChoice: String(Backend.getSetting("focusScene", "tree"))
    property bool pomodoro: Boolean(Backend.getSetting("focusPomodoro", false))
    property bool showRhythm: false
    property int roundCount: Number(Backend.getSetting("focusRounds", 4))
    property int shortBreak: Number(Backend.getSetting("focusShortBreak", 5))
    property int longBreak: Number(Backend.getSetting("focusLongBreak", 15))
    property int longBreakEvery: Number(Backend.getSetting("focusLongBreakEvery", 4))
    property bool showThoughts: false
    property bool showCapture: false
    property bool thoughtSaved: false
    property bool allTasks: false
    property var tasks: []
    property var journey: ({})
    property var session: ({})
    property string loadedKey: ""
    property bool draftReady: false
    readonly property var active: journey.active || ({})
    readonly property string stage: String(active.status || "prepare")
    readonly property bool compact: width - horizontalPadding * 2 < 700 || height < 660
    readonly property var pendingThoughts: (journey.thoughts || []).filter(function(item) { return !item.resolved })
    readonly property var taskChoices: [{label: I18n.t("自由专注"), id: -1}].concat(tasks.filter(function(item) {
        return !item.done && (page.allTasks || String(item.scheduledDate || item.dailyDate || "") === page.todayKey())
    }).map(function(item) { return {label: String(item.title), id: Number(item.id)} }))
    readonly property int remaining: Math.max(0, Number(session.remaining !== undefined && session.remaining !== null && stage === "work"
        ? session.remaining : active.remainingSeconds || 0))
    readonly property var latest: (journey.history || []).length ? journey.history[journey.history.length - 1] : ({})

    function todayKey() { return Qt.formatDate(new Date(), "yyyy-MM-dd") }
    function saveDraft() {
        if (!draftReady) return
        var draft = { version: 1, stageKey: loadedKey, scrollPosition: scrollPosition,
            step: stepInput.text, thought: thoughtInput.text,
            progress: progressInput.text, nextAction: nextInput.text,
            reviewProgress: reviewProgress.text, reviewNext: reviewNext.text,
            markTaskDone: markTaskDone.checked }
        var fields = ["selectedTaskId", "durationMinutes", "shieldEnabled", "showAdvanced",
            "showTaskPicker", "customDuration", "immersive", "sceneChoice", "pomodoro",
            "showRhythm", "roundCount", "shortBreak", "longBreak", "longBreakEvery",
            "showThoughts", "showCapture", "allTasks"]
        fields.forEach(function(name) { draft[name] = page[name] })
        Backend.setSetting("focusPageDraft", JSON.stringify(draft))
    }
    function restoreDraft() {
        var draft
        try { draft = JSON.parse(String(Backend.getSetting("focusPageDraft", "{}"))) }
        catch (error) { return }
        if (!draft || draft.version !== 1) return
        // Load the filter before the task selection so valid non-today tasks survive.
        var fields = ["allTasks", "selectedTaskId", "durationMinutes", "shieldEnabled", "showAdvanced",
            "showTaskPicker", "customDuration", "immersive", "sceneChoice", "pomodoro",
            "showRhythm", "roundCount", "shortBreak", "longBreak", "longBreakEvery", "showThoughts"]
        fields.forEach(function(name) { if (draft[name] !== undefined) page[name] = draft[name] })
        if (!taskChoices.some(function(item) { return item.id === page.selectedTaskId })) selectedTaskId = -1
        stepInput.text = String(draft.step || "")
        thoughtInput.text = String(draft.thought || "")
        // Session drafts only apply to the same session and phase. The timer always
        // comes from the backend, including transitions that happened while away.
        if (draft.stageKey === loadedKey) {
            progressInput.text = String(draft.progress || "")
            nextInput.text = String(draft.nextAction || "")
            reviewProgress.text = String(draft.reviewProgress || "")
            reviewNext.text = String(draft.reviewNext || "")
            markTaskDone.checked = Boolean(draft.markTaskDone)
            showCapture = Boolean(draft.showCapture)
            Qt.callLater(function() { page.scrollPosition = Math.max(0, Number(draft.scrollPosition) || 0) })
        }
    }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function open(name, properties) { var router = nav(); if (router) router.push(Qt.resolvedUrl(name), properties || ({})) }
    function clock(value) { var seconds = Math.max(0, Math.floor(Number(value) || 0)); return String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0") }
    function reloadTasks() {
        try { tasks = JSON.parse(Backend.tasksJson) } catch (error) { tasks = [] }
    }
    function reloadSession() { try { session = JSON.parse(Backend.focusSessionJson) } catch (error) { session = ({}) } }
    function reloadJourney() {
        try { journey = JSON.parse(Backend.focusJourneyJson) } catch (error) { journey = ({}) }
        var key = String(active.id || "") + ":" + stage
        if (key !== loadedKey) {
            progressInput.text = String(active.progress || "")
            nextInput.text = String(active.nextAction || active.step || "")
            reviewProgress.text = String(active.progress || "")
            reviewNext.text = String(active.nextAction || "")
            markTaskDone.checked = false
            showCapture = false
            loadedKey = key
        }
    }
    function enterStudio() { if (immersive) Backend.enterFocusStudio(sceneChoice) }
    function start() {
        var ok = pomodoro ? Backend.startPomodoroFocus(selectedTaskId, durationMinutes, shortBreak, longBreak, roundCount, stepInput.text, shieldEnabled, longBreakEvery)
            : Backend.startStepFocus(selectedTaskId, durationMinutes, stepInput.text, shieldEnabled)
        if (ok) {
            Backend.setSetting("focusQuickDuration", durationMinutes)
            Backend.setSetting("focusPomodoro", pomodoro)
            Backend.setSetting("focusImmersive", immersive)
            Backend.setSetting("focusScene", sceneChoice)
            Backend.setSetting("focusRounds", roundCount)
            Backend.setSetting("focusShortBreak", shortBreak)
            Backend.setSetting("focusLongBreak", longBreak)
            Backend.setSetting("focusLongBreakEvery", longBreakEvery)
            enterStudio()
        }
    }
    function capture() {
        if (Backend.captureFocusThought(thoughtInput.text)) {
            thoughtInput.clear(); showCapture = false; thoughtSaved = true; savedNotice.restart()
        }
    }
    function pause() { Backend.pauseStepFocus(String(active.progress || ""), String(active.nextAction || active.step || "")) }
    function saveReview(continueNext) {
        var nextStep = reviewNext.text
        if (Backend.saveStepReview(reviewProgress.text, nextStep, markTaskDone.checked)) {
            stepInput.text = nextStep
            if (continueNext && Backend.resumeStepFocus(nextStep)) enterStudio()
        }
    }
    onTaskChoicesChanged: {
        if (!taskChoices.some(function(item) { return item.id === page.selectedTaskId })) selectedTaskId = -1
    }
    onInitialTaskIdChanged: if (initialTaskId >= 0) { allTasks = true; selectedTaskId = initialTaskId }
    Component.onCompleted: {
        reloadTasks(); reloadSession(); reloadJourney()
        restoreDraft()
        if (initialTaskId >= 0) { allTasks = true; selectedTaskId = initialTaskId }
        draftReady = true
    }
    onVisibleChanged: if (!visible) saveDraft()
    Component.onDestruction: saveDraft()
    Connections {
        target: Backend
        function onTasksChanged() { page.reloadTasks() }
        function onFocusSessionChanged() { page.reloadSession() }
        function onFocusJourneyChanged() { page.reloadJourney() }
    }
    Timer { interval: 60000; repeat: true; running: page.visible; onTriggered: page.reloadTasks() }
    Timer { id: savedNotice; interval: 2600; onTriggered: page.thoughtSaved = false }
    Shortcut { sequence: "Ctrl+Shift+Space"; enabled: page.visible && page.stage === "work"; onActivated: { page.showCapture = true; thoughtInput.forceActiveFocus() } }

    Item { Layout.preferredHeight: 8 }
    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: page.stage === "work" ? I18n.t("专注中") : page.stage === "paused" ? I18n.t("已暂停") : page.stage === "review" ? I18n.t("本轮进展") : I18n.t("专注"); font.pixelSize: 28; font.weight: Font.DemiBold; color: look.ink }
        InlineHelp { helpText: I18n.t("直接开始，或写下这次要做的事。\n关联任务可选择已有任务；更多里可调整番茄钟、场景和拦截。\n暂停后不计时，记录下一步便可接着做。"); Layout.preferredHeight: 44 }
    }

    Item {
        visible: page.stage === "prepare"
        Layout.fillWidth: true
        Layout.preferredHeight: preparationBody.implicitHeight + (page.height < 660 ? 16 : 40)
        ColumnLayout {
            id: preparationBody
            objectName: "focusPreparationBody"
            width: Math.min(parent.width, 600)
            height: implicitHeight
            anchors.horizontalCenter: parent.horizontalCenter
            y: page.height < 660 ? 8 : 24
            spacing: 16
            Frame {
                visible: page.stage === "prepare" && Boolean(page.journey.checkpoint)
                Layout.fillWidth: true
                padding: 18
                contentItem: RowLayout {
                    spacing: 16
                    ColumnLayout {
                        Layout.fillWidth: true
                        Text { text: I18n.t("上次留下的下一步"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                        Text { Layout.fillWidth: true; text: String((page.journey.checkpoint || {}).step || ""); wrapMode: Text.Wrap }
                    }
                    JourneyButton { text: I18n.t("接着做"); onClicked: { if (Backend.resumeStepFocus("")) page.enterStudio() } }
                }
            }

            Frame {
                id: preparationCard
                objectName: "focusPreparationCard"
                visible: page.stage === "prepare"
                Layout.fillWidth: true
                padding: 24
                background: Rectangle {
                    radius: 18
                    color: look.surface
                    border.color: look.stroke
                }
                contentItem: ColumnLayout {
                    spacing: 16
                    RowLayout { Layout.fillWidth: true; spacing: 16
                        ColumnLayout { spacing: 2
                            Text { text: I18n.t("本轮时长"); font.pixelSize: 12; color: look.muted }
                            Text { objectName: "focusDurationDisplay"; text: page.clock(page.durationMinutes * 60); font.pixelSize: 42; font.weight: Font.DemiBold; color: look.ink }
                        }
                        Item { Layout.fillWidth: true }
                        RowLayout { spacing: 6
                            Repeater { model: [5, 15, 25]; delegate: JourneyButton {
                                required property int modelData
                                objectName: "focusDuration_" + modelData
                                implicitHeight: 40; text: modelData + I18n.t(" 分钟")
                                background: Rectangle { radius: 9; color: page.durationMinutes === modelData && !page.customDuration ? look.tint : "transparent"; border.color: page.durationMinutes === modelData && !page.customDuration ? look.accent : look.stroke }
                                onClicked: { page.durationMinutes = modelData; page.customDuration = false }
                            } }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                    JourneyField {
                        id: stepInput
                        objectName: "focusStepInput"
                        Layout.fillWidth: true
                        implicitHeight: 44
                        placeholderText: activeFocus ? "" : I18n.t("这次，专心做什么？")
                        maximumLength: 1000
                        onAccepted: page.start()
                        Accessible.name: I18n.t("这一轮的具体行动")
                    }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        JourneyButton {
                            objectName: "focusTaskShortcut"
                            flat: true
                            icon.name: "ic_fluent_link_20_regular"
                            Layout.maximumWidth: preparationCard.width - 100
                            text: page.selectedTaskId < 0 ? I18n.t("关联任务") : String((page.taskChoices.find(function(item) { return item.id === page.selectedTaskId }) || {}).label || "")
                            onClicked: page.showTaskPicker = !page.showTaskPicker
                        }
                        Item { Layout.fillWidth: true }
                        JourneyButton { visible: page.selectedTaskId >= 0; flat: true; text: I18n.t("清除"); onClicked: page.selectedTaskId = -1 }
                    }
                    RowLayout {
                        visible: page.showTaskPicker
                        Layout.fillWidth: true
                        JourneyCombo {
                            id: taskPicker
                            objectName: "focusTaskPicker"
                            Layout.fillWidth: true
                            model: page.taskChoices
                            textRole: "label"
                            currentIndex: Math.max(0, page.taskChoices.findIndex(function(item) { return item.id === page.selectedTaskId }))
                            onActivated: { page.selectedTaskId = page.taskChoices[index].id; page.showTaskPicker = false }
                            Accessible.name: I18n.t("关联任务")
                        }
                        CheckBox { text: I18n.t("全部"); checked: page.allTasks; onToggled: page.allTasks = checked }
                    }
                    RowLayout { Layout.fillWidth: true; spacing: 10
                        JourneyButton { objectName: "quickStartFocus"; Layout.fillWidth: true; implicitHeight: 44; text: (page.immersive ? I18n.t("进入专注") : I18n.t("开始专注")) + (page.pomodoro ? " · " + page.roundCount + I18n.t(" 轮") : ""); highlighted: true; icon.name: "ic_fluent_play_20_regular"; onClicked: page.start() }
                        JourneyButton { objectName: "focusMore"; implicitHeight: 44; flat: true; text: I18n.t("更多"); icon.name: page.showAdvanced ? "ic_fluent_chevron_up_20_regular" : "ic_fluent_more_horizontal_20_regular"; onClicked: page.showAdvanced = !page.showAdvanced }
                    }
                    JourneyButton { visible: page.showAdvanced && Boolean(Backend.getSetting("aiGentleStart", true)) && (page.durationMinutes > 5 || page.pomodoro); flat: true; text: I18n.t("先做 5 分钟"); onClicked: { page.durationMinutes = 5; page.pomodoro = false; page.customDuration = false; page.start() } }
                    RowLayout {
                        Layout.fillWidth: true
                        visible: page.showAdvanced
                        Text { Layout.fillWidth: true; text: I18n.t("沉浸场景"); typography: Typography.BodyStrong }
                        Switch { objectName: "immersiveSwitch"; checkedText: I18n.t("开启"); uncheckedText: I18n.t("关闭"); checked: page.immersive; onToggled: page.immersive = checked; Accessible.name: I18n.t("开始后进入全屏") }
                    }
                    RowLayout {
                        visible: page.showAdvanced && page.immersive
                        objectName: "immersiveScenes"
                        Layout.fillWidth: true
                        spacing: 12
                        Repeater { model: [{name: "tree", label: I18n.t("生长之森"), color: "#17372c"}, {name: "room", label: I18n.t("专注小屋"), color: "#2c303d"}]; delegate: Item {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: page.compact ? 76 : 88
                            Rectangle { anchors.fill: parent; radius: Theme.currentTheme.appearance.cardRadius; color: modelData.color; border.width: page.sceneChoice === modelData.name ? 2 : 0; border.color: Theme.currentTheme.colors.primaryColor }
                            Image { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: parent.width * 0.62; height: parent.height - 2; source: Qt.resolvedUrl("../../focus-studio/assets/" + modelData.name + ".svg"); fillMode: Image.PreserveAspectFit }
                            Column { anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                                Text { text: modelData.label; color: "#ecede3"; font.pixelSize: 13; font.weight: Font.Medium }
                            }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: page.sceneChoice = modelData.name }
                            Accessible.role: Accessible.Button
                            Accessible.name: modelData.label
                            Accessible.onPressAction: page.sceneChoice = modelData.name
                            activeFocusOnTab: true
                            Keys.onSpacePressed: page.sceneChoice = modelData.name
                            Keys.onReturnPressed: page.sceneChoice = modelData.name
                        } }
                    }
                    RowLayout {
                        visible: page.showAdvanced
                        Layout.fillWidth: true
                        Text { Layout.fillWidth: true; text: I18n.t("时长"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                        CheckBox { text: I18n.t("番茄钟"); checked: page.pomodoro; onToggled: { page.pomodoro = checked; if (checked && page.durationMinutes < 15) page.durationMinutes = 25 } }
                    }
                    Flow {
                        visible: page.showAdvanced
                        Layout.fillWidth: true
                        spacing: 8
                        JourneyButton { implicitHeight: 38; text: page.customDuration ? page.durationMinutes + I18n.t(" 分钟") : I18n.t("自定义"); flat: true; onClicked: page.customDuration = !page.customDuration }
                        JourneySpinBox { visible: page.customDuration; from: 1; to: 180; value: page.durationMinutes; onValueModified: page.durationMinutes = value; Accessible.name: I18n.t("自定义分钟") }
                    }
                    RowLayout {
                        visible: page.showAdvanced && page.pomodoro
                        Layout.fillWidth: true
                        Text { Layout.fillWidth: true; text: page.roundCount + I18n.t(" 轮 · 每轮休息 ") + page.shortBreak + I18n.t(" 分钟"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                        JourneyButton { flat: true; text: I18n.t("调整节奏"); onClicked: page.showRhythm = !page.showRhythm }
                    }
                    ColumnLayout {
                        visible: page.showAdvanced && page.pomodoro && page.showRhythm
                        Layout.fillWidth: true
                        spacing: 10
                        RowLayout { Layout.fillWidth: true; Text { Layout.fillWidth: true; text: I18n.t("专注轮数") } JourneySpinBox { from: 1; to: 12; value: page.roundCount; onValueModified: page.roundCount = value } }
                        RowLayout { Layout.fillWidth: true; Text { Layout.fillWidth: true; text: I18n.t("短休息（分钟）") } JourneySpinBox { from: 1; to: 30; value: page.shortBreak; onValueModified: page.shortBreak = value } }
                        RowLayout { Layout.fillWidth: true; Text { Layout.fillWidth: true; text: I18n.t("每几轮安排长休息") } JourneySpinBox { from: 1; to: 12; value: page.longBreakEvery; onValueModified: page.longBreakEvery = value } }
                        RowLayout { Layout.fillWidth: true; Text { Layout.fillWidth: true; text: I18n.t("长休息（分钟）") } JourneySpinBox { from: 1; to: 60; value: page.longBreak; onValueModified: page.longBreak = value } }
                        Text { Layout.fillWidth: true; text: I18n.t("休息后自动开始下一轮，最后一轮结束后收尾。"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap }
                    }
                    ColumnLayout {
                        visible: page.showAdvanced
                        Layout.fillWidth: true
                        spacing: 8
                        JourneyButton { objectName: "focusRelationsMore"; flat: true; text: I18n.t("查看任务流"); icon.name: "ic_fluent_link_20_regular"; onClicked: Backend.openTaskRelations(page.selectedTaskId >= 0 ? "task:" + page.selectedTaskId : "") }
                        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.currentTheme.colors.controlBorderColor }
                        RowLayout { Layout.fillWidth: true; Text { Layout.fillWidth: true; text: I18n.t("应用拦截"); wrapMode: Text.Wrap } Switch { checkedText: ""; uncheckedText: ""; Accessible.name: I18n.t("应用拦截"); checked: page.shieldEnabled; onToggled: page.shieldEnabled = checked } }
                        JourneyButton { flat: true; text: I18n.t("允许的应用"); onClicked: page.open("FocusGuardApps.qml", {returnLabel: I18n.t("返回专注")}) }
                    }
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                JourneyButton { objectName: "openSupervision"; flat: true; text: I18n.t("监督模式"); icon.name: "ic_fluent_video_20_regular"; onClicked: page.open("SupervisionWorkspace.qml") }
            }

            RowLayout {
                visible: page.stage === "prepare" && Boolean(page.latest.id) && !page.journey.checkpoint
                Layout.fillWidth: true
                spacing: 8
                Text { text: I18n.t("上次"); font.pixelSize: 12; color: look.muted }
                Text { Layout.fillWidth: true; text: String(page.latest.progress || page.latest.step || ""); font.pixelSize: 12; color: look.muted; elide: Text.ElideRight }
                Text { text: page.clock(page.latest.elapsedSeconds); font.pixelSize: 12; color: look.muted }
            }
        }
    }

    Frame {
        objectName: "focusWorkCard"
        visible: page.stage === "work"
        Layout.fillWidth: true
        padding: page.compact ? 24 : 32
        background: Rectangle { radius: 18; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 20
            Text { text: page.session.type === "break" ? I18n.t("休息中") : I18n.t("正在推进"); typography: Typography.Caption; color: Theme.currentTheme.colors.primaryColor }
            Text { visible: String(page.active.title || "") !== String(page.active.step || ""); Layout.fillWidth: true; text: String(page.active.title || ""); typography: Typography.Caption; color: look.muted; wrapMode: Text.Wrap }
            Text { Layout.fillWidth: true; text: String(page.active.step || page.active.title || ""); font.pixelSize: 24; font.weight: Font.DemiBold; color: look.ink; wrapMode: Text.Wrap }
            Text { visible: Number(page.session.totalTasks || 0) > 1; text: I18n.t("当前阶段 ") + (Number(page.session.index || 0) + 1) + " / " + page.session.totalTasks; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
            RowLayout {
                Layout.fillWidth: true
                Text { text: page.clock(page.remaining); font.pixelSize: 56; font.weight: Font.DemiBold; color: look.ink }
                Text { text: I18n.t("剩余"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true }
                Text { text: I18n.t("已投入 ") + page.clock(page.active.elapsedSeconds); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
            }
            ProgressBar { layer.enabled: false; Layout.fillWidth: true; from: 0; to: 1; value: Math.max(0, Math.min(1, 1 - page.remaining / Math.max(1, Number(page.session.taskSeconds || page.active.plannedSeconds || 1)))) }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                JourneyButton { flat: true; text: I18n.t("进入沉浸"); onClicked: Backend.enterFocusStudio(page.sceneChoice) }
                JourneyButton { flat: true; text: I18n.t("暂存念头"); icon.name: "ic_fluent_note_20_regular"; onClicked: { page.showCapture = !page.showCapture; if (page.showCapture) thoughtInput.forceActiveFocus() } }
                JourneyButton { objectName: "focusPause"; flat: true; text: I18n.t("暂停"); icon.name: "ic_fluent_pause_20_regular"; onClicked: page.pause() }
                JourneyButton { text: page.active.mode === "single" ? I18n.t("完成本轮") : I18n.t("收尾这一轮"); highlighted: true; icon.name: "ic_fluent_checkmark_20_regular"; onClicked: Backend.endStepFocus() }
            }
            ColumnLayout {
                visible: page.showCapture
                Layout.fillWidth: true
                spacing: 8
                JourneyField { id: thoughtInput; Layout.fillWidth: true; placeholderText: I18n.t("先记一句，稍后再处理。按 Enter 保存"); maximumLength: 2000; onAccepted: page.capture(); Accessible.name: I18n.t("暂存念头") }
                RowLayout {
                    JourneyButton { text: I18n.t("存下，继续做"); enabled: thoughtInput.text.trim().length > 0; onClicked: page.capture() }
                    Text { text: "Ctrl+Shift+Space"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                }
            }
            Text { visible: page.thoughtSaved; text: I18n.t("已存好，回到眼前这一步。"); typography: Typography.Caption; color: Theme.currentTheme.colors.primaryColor }
        }
    }

    Frame {
        visible: page.stage === "paused"
        Layout.fillWidth: true
        padding: 24
        background: Rectangle { radius: 18; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 16
            Text { Layout.fillWidth: true; text: String(page.active.title || ""); typography: Typography.Subtitle; wrapMode: Text.Wrap }
            Text { text: I18n.t("已投入 ") + page.clock(page.active.elapsedSeconds) + "   ·   " + I18n.t("剩余 ") + page.clock(page.remaining); color: Theme.currentTheme.colors.textSecondaryColor }
            Text { text: I18n.t("做到哪里了？"); typography: Typography.BodyStrong }
            JourneyArea { id: progressInput; objectName: "focusProgressInput"; Layout.fillWidth: true; Layout.preferredHeight: 80; placeholderText: I18n.t("例如：读到第三节，已经整理一个观点"); Accessible.name: I18n.t("离开前的进展") }
            Text { text: I18n.t("下一步"); typography: Typography.BodyStrong }
            JourneyField { id: nextInput; objectName: "focusNextInput"; Layout.fillWidth: true; placeholderText: I18n.t("例如：整理第二个观点"); maximumLength: 1000; Accessible.name: I18n.t("回来后的下一步") }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                JourneyButton { text: I18n.t("接着做"); highlighted: true; icon.name: "ic_fluent_play_20_regular"; onClicked: { Backend.pauseStepFocus(progressInput.text, nextInput.text); if (Backend.resumeStepFocus(nextInput.text)) page.enterStudio() } }
                JourneyButton { text: I18n.t("保存，稍后回来"); onClicked: { if (Backend.parkStepFocus(progressInput.text, nextInput.text)) savedBookmark.visible = true } }
                JourneyButton { text: I18n.t("收尾这一步"); flat: true; onClicked: { Backend.parkStepFocus(progressInput.text, nextInput.text); Backend.endStepFocus() } }
            }
            Text { id: savedBookmark; visible: false; Layout.fillWidth: true; text: I18n.t("接续记录已保存，可以安心离开。下次打开仍在这里。"); typography: Typography.Caption; color: Theme.currentTheme.colors.primaryColor; wrapMode: Text.Wrap }
        }
    }

    Frame {
        visible: page.stage === "review"
        Layout.fillWidth: true
        padding: 24
        background: Rectangle { radius: 18; color: look.surface; border.color: look.stroke }
        contentItem: ColumnLayout {
            spacing: 16
            Text { Layout.fillWidth: true; text: String(page.active.step || page.active.title || ""); typography: Typography.Subtitle; wrapMode: Text.Wrap }
            Text { text: I18n.t("实际投入 ") + page.clock(page.active.elapsedSeconds); color: Theme.currentTheme.colors.textSecondaryColor }
            Text { text: I18n.t("这次的进展"); typography: Typography.BodyStrong }
            JourneyArea { id: reviewProgress; objectName: "focusReviewProgress"; Layout.fillWidth: true; Layout.preferredHeight: 80; placeholderText: I18n.t("例如：整理了三个可引用的观点"); Accessible.name: I18n.t("这一轮的实际进展") }
            Text { text: I18n.t("为下一步留个起点（可选）"); typography: Typography.BodyStrong }
            JourneyField { id: reviewNext; objectName: "focusReviewNext"; Layout.fillWidth: true; placeholderText: I18n.t("例如：用这些观点写第一段"); maximumLength: 1000; Accessible.name: I18n.t("下一轮的行动") }
            CheckBox { id: markTaskDone; visible: (page.active.mode === "single" && page.active.taskId !== undefined && page.active.taskId !== null) || Boolean((page.active.source || {}).relationNodeKey); text: I18n.t("整个任务也已完成"); checked: false }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                JourneyButton { text: I18n.t("保存并休息"); highlighted: true; icon.name: "ic_fluent_checkmark_20_regular"; onClicked: page.saveReview(false) }
                JourneyButton { text: I18n.t("继续下一步"); enabled: reviewNext.text.trim().length > 0 && !markTaskDone.checked; onClicked: page.saveReview(true) }
            }
        }
    }

    JourneyButton {
        visible: page.pendingThoughts.length > 0 && (page.stage === "prepare" || page.stage === "review")
        flat: true
        text: I18n.t("稍后处理") + "  ·  " + page.pendingThoughts.length
        icon.name: "ic_fluent_note_20_regular"
        onClicked: page.showThoughts = !page.showThoughts
    }
    ColumnLayout {
        visible: page.showThoughts && (page.stage === "prepare" || page.stage === "review")
        Layout.fillWidth: true
        spacing: 8
        Repeater { model: page.pendingThoughts; delegate: Frame {
            required property var modelData
            Layout.fillWidth: true
            padding: 14
            contentItem: RowLayout {
                spacing: 12
                Text { Layout.fillWidth: true; text: String(modelData.text); wrapMode: Text.Wrap }
                JourneyButton { text: I18n.t("已处理"); flat: true; onClicked: Backend.resolveFocusThought(String(modelData.id)) }
            }
        } }
    }
}
