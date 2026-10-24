import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"
import "../components"

FluentPage {
    id: page
    title: I18n.t("AI 服务")
    wrapperWidth: 760
    horizontalPadding: 32
    contentSpacing: 18
    property bool loading: true
    property bool showParameters: false
    property bool showSpeech: false
    property bool customService: false
    property bool officialService: false
    property var cloud: { try { return JSON.parse(Backend.cloudJson) } catch(e) { return ({}) } }
    function navigationView() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { loading = true; officialService = Backend.getSetting("aiServiceMode", "default") === "official"; customService = Backend.getSetting("aiServiceMode", "default") === "custom"; baseUrl.text = customService ? String(Backend.getSetting("aiBaseUrl", "https://api.openai.com/v1")) : ""; modelName.text = String(Backend.getSetting("aiModel", "gpt-4o-mini")); apiKey.text = customService ? String(Backend.getSetting("aiApiKey", "")) : ""; temperature.value = Number(Backend.getSetting("aiTemperature", 0.7)); timeout.value = Number(Backend.getSetting("aiTimeout", 240)); loading = false }
    Component.onCompleted: load()
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: I18n.t("返回系统设置")
                ToolTip.visible: hovered
                onClicked: { var router = page.navigationView(); if (router) router.pop() } }
                Text { text: I18n.t("返回系统设置")
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }
    Text { Layout.fillWidth: true
                text: I18n.t("选择官方通道，或配置自己的 OpenAI 兼容 API。官方通道的订阅和额度由账户管理。")
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        contentItem: ColumnLayout {
                spacing: 12
            Text { text: I18n.t("连接")
                typography: Typography.Subtitle }
            JourneyCombo {
                Layout.fillWidth: true
                model: [I18n.t("默认测试模型"), I18n.t("自定义 API"), I18n.t("官方通道")]
                currentIndex: page.officialService ? 2 : page.customService ? 1 : 0
                onActivated: { Backend.setSetting("aiServiceMode", currentIndex === 2 ? "official" : currentIndex === 1 ? "custom" : "default"); page.load() }
            }
            Text { visible: !page.customService && !page.officialService; Layout.fillWidth: true; text: I18n.t("正在使用默认测试模型。测试密钥不在界面显示；可切换到自定义 API 使用自己的服务。"); wrapMode: Text.Wrap; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
            Text { visible: page.customService; text: I18n.t("API 地址"); typography: Typography.Caption }
            JourneyField { id: baseUrl
                visible: page.customService
                Layout.fillWidth: true
                placeholderText: "https://api.openai.com/v1"
                onEditingFinished: if (!page.loading) Backend.setSetting("aiBaseUrl", text.trim()) }
            Text { visible: !page.officialService; text: I18n.t("模型名称"); typography: Typography.Caption }
            JourneyField { id: modelName
                visible: !page.officialService
                Layout.fillWidth: true
                placeholderText: I18n.t("模型名称，例如 gpt-4o-mini")
                onEditingFinished: if (!page.loading) Backend.setSetting("aiModel", text.trim()) }
            Text { visible: page.officialService; Layout.fillWidth: true; wrapMode: Text.Wrap; text: page.cloud.loggedIn ? I18n.t("官方通道 · ") + ((page.cloud.account || {}).user || {}).plan + I18n.t(" · 剩余 ") + (((page.cloud.account || {}).officialAI || {}).remaining || 0) + I18n.t(" 次\n") + ((((page.cloud.account || {}).officialAI || {}).active) ? I18n.t("订阅和金额额度由后台管理。") : I18n.t("官方通道尚未开放或当前账户未开通额度。")) : I18n.t("请先在我的账户登录。"); typography: Typography.Body }
            Text { visible: page.customService; text: "API Key"; typography: Typography.Caption }
            JourneyField { id: apiKey
                visible: page.customService
                Layout.fillWidth: true
                placeholderText: "API Key"
                echoMode: TextInput.Password
                onEditingFinished: if (!page.loading) Backend.setSetting("aiApiKey", text.trim()) }
        }
    }
    JourneyButton { flat: true; text: page.showParameters ? I18n.t("收起高级参数") : I18n.t("高级参数"); onClicked: page.showParameters = !page.showParameters }
    Frame { visible: page.showParameters; Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        contentItem: ColumnLayout {
                spacing: 12
            Text { text: I18n.t("生成参数")
                typography: Typography.Subtitle }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("使用服务默认输出额度"); wrapMode: Text.Wrap }
                Switch { id: serviceOutput; checked: Boolean(Backend.getSetting("aiServiceOutputLimit", true)); checkedText: I18n.t("默认"); uncheckedText: I18n.t("手动"); onToggled: Backend.setSetting("aiServiceOutputLimit", checked) }
            }
            Text { Layout.fillWidth: true; text: I18n.t("默认不向 API 指定输出 token 上限，实际额度由服务决定。任务数量不设上限；截断时自动续写并校验完整结果，结果生成最多 4 次请求。很长的原话会先分段整理，这些额外请求可能增加费用。关闭后可手动指定预算；服务仍可能限制该数值。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("日常规划输出 token 上限") }
                SpinBox { enabled: !serviceOutput.checked; from: 512; to: 2147483647; editable: true; stepSize: 256; value: Number(Backend.getSetting("aiShortOutputLimit", 1800)); onValueModified: Backend.setSetting("aiShortOutputLimit", value) }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("长期规划输出 token 上限") }
                SpinBox { enabled: !serviceOutput.checked; from: 512; to: 2147483647; editable: true; stepSize: 256; value: Number(Backend.getSetting("aiLongOutputLimit", 3600)); onValueModified: Backend.setSetting("aiLongOutputLimit", value) }
            }
            RowLayout { Layout.fillWidth: true
                Text { Layout.preferredWidth: 100
                text: I18n.t("温度")
                typography: Typography.BodyStrong }
                Slider { id: temperature
                Layout.fillWidth: true
                from: 0
                to: 2
                stepSize: 0.1
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("aiTemperature", value) }
                Text { text: temperature.value.toFixed(1)
                typography: Typography.Caption } }
            RowLayout { Layout.fillWidth: true
                Text { Layout.preferredWidth: 100
                text: I18n.t("超时")
                typography: Typography.BodyStrong }
                SpinBox { id: timeout
                from: 30
                to: 1200
                stepSize: 30
                onValueModified: if (!page.loading) Backend.setSetting("aiTimeout", value) }
                Text { text: I18n.t("秒")
                typography: Typography.Caption } }
        }
    }
    Frame {
        Layout.fillWidth: true
        padding: 20
        contentItem: ColumnLayout {
            spacing: 14
            Text { text: I18n.t("我的专注偏好"); typography: Typography.Subtitle }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("让 AI 参考我的起步和音乐偏好"); wrapMode: Text.Wrap }
                Switch { checked: Boolean(Backend.getSetting("aiUsePreferences", false)); checkedText: I18n.t("开启"); uncheckedText: I18n.t("关闭"); onToggled: Backend.setSetting("aiUsePreferences", checked) }
            }
            Text { Layout.fillWidth: true; text: I18n.t("开启后，下面的偏好文字会随任务请求发送给你配置的 AI 服务。音乐文件和文件路径不会发给 AI。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("难开始时，建议轻一点的起步（时长按状态调整）"); wrapMode: Text.Wrap }
                Switch { checked: Boolean(Backend.getSetting("aiGentleStart", true)); checkedText: I18n.t("开启"); uncheckedText: I18n.t("关闭"); onToggled: Backend.setSetting("aiGentleStart", checked) }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("沉浸引导中主动询问进度"); wrapMode: Text.Wrap }
                JourneyCombo {
                    Layout.preferredWidth: 180
                    model: [I18n.t("关闭"), I18n.t("每 10 分钟"), I18n.t("每 20 分钟"), I18n.t("每 30 分钟")]
                    currentIndex: Math.max(0, [0, 10, 20, 30].indexOf(Number(Backend.getSetting("guidedProgressCheckMinutes", 0))))
                    onActivated: Backend.setSetting("guidedProgressCheckMinutes", [0, 10, 20, 30][currentIndex])
                }
            }
            Text { Layout.fillWidth: true; text: I18n.t("默认关闭，也可以在沉浸场景的进度输入框中开启。按实际专注时间提醒；休息和填写期间不计时，弹窗本身不调用 AI。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            Text { text: I18n.t("专注时喜欢什么声音"); typography: Typography.Caption }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("小段完成时播放轻快的庆祝音效"); wrapMode: Text.Wrap }
                Switch { checked: Boolean(Backend.getSetting("guidedRewardSound", true)); checkedText: I18n.t("开启"); uncheckedText: I18n.t("关闭"); onToggled: Backend.setSetting("guidedRewardSound", checked) }
            }
            JourneyField { Layout.fillWidth: true; maximumLength: 40; text: String(Backend.getSetting("focusMusicPreference", "安静")); placeholderText: I18n.t("音乐偏好，例如：安静、雨声、无歌词轻音乐"); onEditingFinished: Backend.setSetting("focusMusicPreference", text.trim()) }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("开始专注时播放所选音乐"); wrapMode: Text.Wrap }
                Switch { checked: Boolean(Backend.getSetting("focusMusicAutoPlay", false)); checkedText: I18n.t("开启"); uncheckedText: I18n.t("关闭"); onToggled: Backend.setSetting("focusMusicAutoPlay", checked) }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { id: musicPath; Layout.fillWidth: true; Layout.minimumWidth: 0; text: String(Backend.getSetting("focusMusicPath", "")) || I18n.t("还未选择音乐"); elide: Text.ElideMiddle; typography: Typography.Caption }
                JourneyButton { text: I18n.t("选择音乐"); onClicked: { var path = Backend.chooseFocusMusic(); if (path) musicPath.text = path } }
                JourneyButton { text: I18n.t("停止播放"); onClicked: Backend.stopFocusMusic() }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: I18n.t("背景音乐音量") }
                Slider { id: musicVolume; Layout.fillWidth: true; from: 0; to: 100; value: Number(Backend.getSetting("focusMusicVolume", 0.25)) * 100; onPressedChanged: if (!pressed) Backend.setSetting("focusMusicVolume", value / 100) }
                Text { text: Math.round(musicVolume.value) + "%" }
            }
        }
    }
    Frame {
        Layout.fillWidth: true
        padding: 20
        contentItem: ColumnLayout {
            spacing: 12
            Text { text: I18n.t("语音输入"); typography: Typography.Subtitle }
            JourneyCombo {
                id: speechMode
                objectName: "speechInputMode"
                Layout.fillWidth: true
                model: [I18n.t("Windows 系统听写（无需 API）"), I18n.t("云端转写（可能收费）")]
                currentIndex: Backend.getSetting("speechInputMode", "system") === "cloud" ? 1 : 0
                onActivated: {
                    Backend.setSetting("speechInputMode", currentIndex === 1 ? "cloud" : "system")
                    page.showSpeech = currentIndex === 1
                }
            }
            Text { Layout.fillWidth: true; text: I18n.t("默认使用 Windows 自带听写。点击语音按钮就能在输入框中说话，不使用你的 AI 密钥。系统听写需联网；只有请求 AI 整理任务时才消耗 AI API。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            JourneyButton { visible: speechMode.currentIndex === 1; flat: true; text: page.showSpeech ? I18n.t("收起云端转写配置") : I18n.t("配置云端转写"); onClicked: page.showSpeech = !page.showSpeech }
        }
    }
    Frame {
        visible: page.showSpeech && speechMode.currentIndex === 1
        Layout.fillWidth: true
        padding: 20
        contentItem: ColumnLayout {
            spacing: 14
            Text { text: I18n.t("云端转写"); typography: Typography.Subtitle }
            Text { Layout.fillWidth: true; text: I18n.t("需要支持音频转写的服务，聊天 API 不一定支持。留空地址和密钥会使用上面的 AI 服务配置。录音只在你确认后上传。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            JourneyField { Layout.fillWidth: true; text: String(Backend.getSetting("speechBaseUrl", "")); placeholderText: I18n.t("语音 API 地址（留空使用 AI 地址）"); onEditingFinished: Backend.setSetting("speechBaseUrl", text.trim()) }
            JourneyField { Layout.fillWidth: true; text: String(Backend.getSetting("speechApiKey", "")); echoMode: TextInput.Password; placeholderText: I18n.t("语音 API Key（留空使用 AI 密钥）"); onEditingFinished: Backend.setSetting("speechApiKey", text.trim()) }
            JourneyField { Layout.fillWidth: true; text: String(Backend.getSetting("speechModel", "gpt-4o-transcribe")); placeholderText: I18n.t("语音模型名称"); onEditingFinished: Backend.setSetting("speechModel", text.trim()) }
            JourneyField { Layout.fillWidth: true; text: String(Backend.getSetting("speechVocabulary", "")); placeholderText: I18n.t("常用人名、课程名或专业词（可选，最多 200 字）"); maximumLength: 200; onEditingFinished: Backend.setSetting("speechVocabulary", text.trim()) }
            Text { Layout.fillWidth: true; text: I18n.t("此方式可能产生额外的语音识别费用，录音前会提示确认。切回 Windows 系统听写即可停止使用此服务。"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }

}


