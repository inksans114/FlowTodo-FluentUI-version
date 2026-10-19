import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("应用与数据")
    wrapperWidth: 900
    horizontalPadding: 32
    contentSpacing: 18
    property bool loading: true
    readonly property var languageOptions: Backend.availableLanguages
    readonly property var languageLabels: languageOptions.map(function(option) { return option.label })
    function languageIndexOf(code) { for (var i = 0; i < languageOptions.length; i++) { if (languageOptions[i].code === code) return i } return 0 }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        loading = true
        duration.value = Number(Backend.getSetting("focusDuration", 25))
        archivePeriod.currentIndex = Math.max(0, [0, 3, 7, 14].indexOf(Number(Backend.getSetting("taskAutoArchiveDays", 0))))
        breakDuration.value = Number(Backend.getSetting("breakDuration", 5))
        autoStart.checked = Boolean(Backend.getSetting("autoStart", false))
        closeBehavior.currentIndex = String(Backend.getSetting("closeBehavior", "tray")) === "exit" ? 1 : 0
        soundEnabled.checked = Boolean(Backend.getSetting("notificationSoundEnabled", true))
        soundVolume.value = Math.round(Number(Backend.getSetting("notificationSoundVolume", 0.8)) * 100)
        var configuredSound = String(Backend.getSetting("notificationSoundPath", ""))
        soundPath.text = configuredSound.length ? configuredSound : I18n.t("使用默认音效")
        languageBox.currentIndex = page.languageIndexOf(String(Backend.language))
        loading = false
    }
    function resetAllData() { Backend.clearAllUserData() }
    Component.onCompleted: load()
    Connections { target: Backend; function onSettingsChanged() { page.load() } }
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: I18n.t("返回系统设置")
                ToolTip.visible: hovered
                onClicked: { var router = page.nav(); if (router) router.pop() } }
                Text { text: I18n.t("返回系统设置")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }
    Text { text: I18n.t("专注")
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        contentItem: ColumnLayout {
                spacing: 12
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("默认专注时长")
                typography: Typography.BodyStrong }
                Slider { id: duration
                Layout.preferredWidth: 280
                from: 5
                to: 120
                stepSize: 5
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("focusDuration", Math.round(value)) }
                Text { text: Math.round(duration.value) + I18n.t(" 分钟")
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true
                text: I18n.t("默认休息时长")
                typography: Typography.BodyStrong }
                Slider { id: breakDuration
                Layout.preferredWidth: 280
                from: 1
                to: 60
                stepSize: 1
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("breakDuration", Math.round(value)) }
                Text { text: Math.round(breakDuration.value) + I18n.t(" 分钟")
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                visible: Backend.windowsFeaturesAvailable
                Text { Layout.fillWidth: true
                text: I18n.t("应用拦截")
                typography: Typography.BodyStrong }
                Button { text: I18n.t("选择允许的应用")
                icon.name: "ic_fluent_shield_checkmark_20_regular"
                onClicked: { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("FocusGuardApps.qml")) } } }
        }
    }
    Text { text: I18n.t("普通任务自动归档"); typography: Typography.Subtitle }
    Frame {
        Layout.fillWidth: true
        padding: 18
        contentItem: ColumnLayout {
            spacing: 12
            Text { Layout.fillWidth: true; text: I18n.t("普通未完成任务到期后移入归档，可随时恢复。每日重复、番茄钟、项目关联和长期任务不参与；有未来排期的任务不会提前归档。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("保留时长"); typography: Typography.BodyStrong }
                ComboBox { id: archivePeriod; objectName: "taskArchivePeriod"; Layout.preferredWidth: 160; model: [I18n.t("关闭"), I18n.t("三天"), I18n.t("一周"), I18n.t("两周")]; onActivated: function(index) { if (!page.loading) Backend.setSetting("taskAutoArchiveDays", [0, 3, 7, 14][index]) } }
                Button { text: I18n.t("查看归档任务"); onClicked: { var router = page.nav(); if (router) router.push(Qt.resolvedUrl("ArchivedTasks.qml")) } }
            }
            Text { Layout.fillWidth: true; text: I18n.t("从创建或最后一次调整排期起计时。没有时间记录的旧任务从首次识别时开始计时，不会立即清理。"); wrapMode: Text.Wrap; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
    Text { text: I18n.t("窗口关闭")
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        contentItem: RowLayout {
                ColumnLayout { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0
                spacing: 2
                Text { text: I18n.t("关闭主窗口时")
                typography: Typography.BodyStrong }
                Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: I18n.t("选择隐藏到系统托盘，或直接退出应用")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
                ComboBox { id: closeBehavior
                objectName: "closeBehavior"
                Layout.preferredWidth: 190
                model: [I18n.t("最小化到系统托盘"), I18n.t("直接关闭应用")]
                onActivated: function(index) { if (!page.loading) Backend.setSetting("closeBehavior", index === 1 ? "exit" : "tray") } }
        }
    }
    Connections { target: Backend
                function onLanguageChanged() { languageBox.currentIndex = page.languageIndexOf(String(Backend.language)) }
                function onSettingsChanged() { if (!page.loading) page.load() } }
    Text { text: I18n.t("提醒音效")
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        contentItem: ColumnLayout {
                spacing: 12
            RowLayout { Layout.fillWidth: true; spacing: 24
                ColumnLayout { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0; spacing: 2
                    Text { Layout.fillWidth: true; text: I18n.t("启用提醒音效"); typography: Typography.BodyStrong }
                    Text { Layout.fillWidth: true; text: I18n.t("用于专注结束、日程、每日任务和应用通知"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; wrapMode: Text.Wrap }
                }
                Switch { id: soundEnabled; Layout.alignment: Qt.AlignRight | Qt.AlignVCenter; objectName: "soundEnabled"; checkedText: I18n.t("开启"); uncheckedText: I18n.t("关闭"); onClicked: if (!page.loading) Backend.setSetting("notificationSoundEnabled", checked) }
            }
            RowLayout { Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("音量"); typography: Typography.BodyStrong }
                Slider { id: soundVolume; Layout.preferredWidth: 280; from: 0; to: 100; stepSize: 1
                    onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("notificationSoundVolume", value / 100) }
                Text { text: Math.round(soundVolume.value) + "%"; typography: Typography.Caption }
            }
            RowLayout { Layout.fillWidth: true; spacing: 10
                Text { id: soundPath; Layout.fillWidth: true; text: I18n.t("使用默认音效"); typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; elide: Text.ElideMiddle }
                Button { Layout.alignment: Qt.AlignRight | Qt.AlignVCenter; text: I18n.t("导入"); icon.name: "ic_fluent_folder_open_20_regular"; onClicked: { var path = Backend.chooseNotificationSound(); if (path) soundPath.text = path } }
                Button { text: I18n.t("试听"); icon.name: "ic_fluent_play_20_regular"; onClicked: Backend.previewNotificationSound() }
                Button { flat: true; text: I18n.t("恢复默认"); onClicked: { Backend.setSetting("notificationSoundPath", ""); soundPath.text = I18n.t("使用默认音效") } }
            }
        }
    }
    Text { text: I18n.t("语言")
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        contentItem: RowLayout {
                ColumnLayout { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0
                spacing: 2
                Text { text: I18n.t("界面语言")
                typography: Typography.BodyStrong }
                Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: I18n.t("选择应用界面使用的语言")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
                ComboBox { id: languageBox
                objectName: "languageBox"
                Layout.preferredWidth: 190
                model: page.languageLabels
                onActivated: function(index) { if (!page.loading) Backend.setLanguage(page.languageOptions[index].code) } }
        }
    }
    Text { text: I18n.t("应用")
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        contentItem: RowLayout {
                ColumnLayout { Layout.fillWidth: true; spacing: 2
                Text {
                text: Backend.windowsFeaturesAvailable ? I18n.t("开机自动启动") : I18n.t("登录启动（Mac 测试版暂未支持）")
                typography: Typography.BodyStrong }
                Text { visible: Backend.windowsFeaturesAvailable
                    text: I18n.t("登录 Windows 时，通过启动目录快捷方式启动")
                    typography: Typography.Caption
                    color: Theme.currentTheme.colors.textSecondaryColor } }
                Switch { id: autoStart; objectName: "autoStartSwitch"; enabled: Backend.windowsFeaturesAvailable
                checkedText: I18n.t("开启"); uncheckedText: I18n.t("关闭")
                onClicked: if (!page.loading) checked = Backend.setAutoStartEnabled(checked) } }
    }
    Text { text: I18n.t("数据")
                typography: Typography.Subtitle }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        contentItem: ColumnLayout {
                spacing: 16
                RowLayout { Layout.fillWidth: true
                    ColumnLayout { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0
                        spacing: 2
                        Text { text: I18n.t("FlowTodo 数据目录")
                            typography: Typography.BodyStrong }
                        Text { Layout.fillWidth: true
                            text: Backend.dataPath
                            typography: Typography.Caption
                            color: Theme.currentTheme.colors.textSecondaryColor
                            elide: Text.ElideMiddle } }
                    Button { text: I18n.t("更改")
                        icon.name: "ic_fluent_folder_open_20_regular"
                        onClicked: Backend.chooseDataDirectory() } }
                Rectangle { Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    Layout.minimumHeight: 1
                    color: Theme.currentTheme.colors.controlBorderColor }
                RowLayout { Layout.fillWidth: true
                    ColumnLayout { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0
                        spacing: 2
                        Text { text: I18n.t("恢复出厂设置")
                            typography: Typography.BodyStrong }
                        Text { Layout.fillWidth: true
                            text: I18n.t("清除所有本地数据与设置，恢复应用初始状态")
                            typography: Typography.Caption
                            color: Theme.currentTheme.colors.textSecondaryColor
                            wrapMode: Text.Wrap } }
                    Button { text: I18n.t("清除所有数据")
                        icon.name: "ic_fluent_delete_20_regular"
                        onClicked: resetDialog.open() } }
        }
    }

    FactoryResetDialog { id: resetDialog
        onResetConfirmed: page.resetAllData() }
}


