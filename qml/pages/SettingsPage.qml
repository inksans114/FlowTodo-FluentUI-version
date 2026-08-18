import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "系统设置"
    wrapperWidth: 1000
    horizontalPadding: 34

    property bool loading: true
    property string selectedUiTheme: "material"
    property string selectedIslandTheme: "material"

    property var themeChoices: [
        { id: "default", title: "Class Widgets 默认" },
        { id: "cw1", title: "Class Widgets 1" },
        { id: "win10", title: "Windows 10" },
        { id: "material", title: "Material You" }
    ]

    function loadSettings() {
        loading = true
        var mode = String(Backend.getSetting("theme", "auto"))
        themeMode.currentIndex = ["auto", "light", "dark"].indexOf(mode)
        if (themeMode.currentIndex < 0) themeMode.currentIndex = 0

        var backdrop = String(Backend.getSetting("nativeBackdrop", "none"))
        backdropMode.currentIndex = ["none", "mica", "acrylic"].indexOf(backdrop)
        if (backdropMode.currentIndex < 0) backdropMode.currentIndex = 0

        selectedUiTheme = String(Backend.getSetting("nativeUiTheme", "material"))
        selectedIslandTheme = String(Backend.getSetting("islandTheme", "material"))
        focusDuration.value = Number(Backend.getSetting("focusDuration", 25))
        autoNext.checked = Boolean(Backend.getSetting("autoNext", false))
        autoStart.checked = Boolean(Backend.getSetting("autoStart", false))
        aiBaseUrl.text = String(Backend.getSetting("aiBaseUrl", "https://api.openai.com/v1"))
        aiModel.text = String(Backend.getSetting("aiModel", "gpt-4o-mini"))
        aiApiKey.text = String(Backend.getSetting("aiApiKey", ""))
        aiTemperature.value = Number(Backend.getSetting("aiTemperature", 0.7))
        aiTimeout.value = Number(Backend.getSetting("aiTimeout", 240))
        aiAutoApply.checked = Boolean(Backend.getSetting("aiAutoApply", true))
        aiReplaceOnApply.checked = Boolean(Backend.getSetting("aiReplaceOnApply", true))
        islandOpacity.value = Number(Backend.getSetting("islandOpacity", 1))
        islandScale.value = Number(Backend.getSetting("islandScale", 1))
        islandLighting.checked = Boolean(Backend.getSetting("islandLightingEffect", true))

        var anchor = String(Backend.getSetting("islandAnchor", "top_center"))
        islandAnchor.currentIndex = ["top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right"].indexOf(anchor)
        if (islandAnchor.currentIndex < 0) islandAnchor.currentIndex = 1

        var layer = String(Backend.getSetting("islandLayer", "top"))
        islandLayer.currentIndex = ["top", "bottom"].indexOf(layer)
        if (islandLayer.currentIndex < 0) islandLayer.currentIndex = 0
        loading = false
    }

    function chooseUiTheme(themeId) {
        selectedUiTheme = themeId
        Backend.setSetting("nativeUiTheme", themeId)
    }

    function chooseIslandTheme(themeId) {
        selectedIslandTheme = themeId
        Backend.setSetting("islandTheme", themeId)
    }

    Component.onCompleted: loadSettings()
    Connections {
        target: Backend
        function onSettingsChanged() {
            if (!page.loading) page.loadSettings()
        }
    }

    Text {
        Layout.fillWidth: true
        text: "外观"
        typography: Typography.BodyStrong
    }

    SettingCard {
        Layout.fillWidth: true
        title: "明暗模式"
        description: "浅色、深色或跟随 Windows 系统设置"
        icon.name: "ic_fluent_dark_theme_20_regular"
        ComboBox {
            id: themeMode
            Layout.preferredWidth: 150
            model: ["跟随系统", "浅色", "深色"]
            onActivated: function(index) {
                if (!page.loading) Backend.setSetting("theme", ["auto", "light", "dark"][index])
            }
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "窗口材质"
        description: "RinUI 原生窗口背景，关闭时使用稳定实色"
        icon.name: "ic_fluent_layer_20_regular"
        ComboBox {
            id: backdropMode
            Layout.preferredWidth: 150
            model: ["实色", "Mica", "Acrylic"]
            onActivated: function(index) {
                if (!page.loading) Backend.setSetting("nativeBackdrop", ["none", "mica", "acrylic"][index])
            }
        }
    }

    Text {
        Layout.fillWidth: true
        text: "应用界面主题"
        typography: Typography.BodyStrong
    }
    Flow {
        Layout.fillWidth: true
        spacing: 10
        Repeater {
            model: page.themeChoices
            delegate: ThemeChoiceCard {
                required property var modelData
                title: modelData.title
                themeId: modelData.id
                preview: Backend.themePreviewUrl(modelData.id)
                selected: page.selectedUiTheme === modelData.id
                onChosen: function(themeId) { page.chooseUiTheme(themeId) }
            }
        }
    }

    Text {
        Layout.fillWidth: true
        text: "专注"
        typography: Typography.BodyStrong
    }
    SettingCard {
        Layout.fillWidth: true
        title: "默认专注时长"
        description: "从原生首页启动任务时使用"
        icon.name: "ic_fluent_timer_20_regular"
        RowLayout {
            Layout.preferredWidth: 280
            Slider {
                id: focusDuration
                Layout.fillWidth: true
                from: 5
                to: 120
                stepSize: 5
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("focusDuration", Math.round(value))
            }
            Text {
                Layout.preferredWidth: 64
                horizontalAlignment: Text.AlignRight
                text: Math.round(focusDuration.value) + " 分钟"
                typography: Typography.Caption
            }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "自动进入下一阶段"
        description: "完成当前阶段后继续任务流"
        icon.name: "ic_fluent_arrow_step_in_20_regular"
        Switch {
            id: autoNext
            onClicked: if (!page.loading) Backend.setSetting("autoNext", checked)
        }
    }

    Text {
        Layout.fillWidth: true
        text: "灵动岛"
        typography: Typography.BodyStrong
    }
    Flow {
        Layout.fillWidth: true
        spacing: 10
        Repeater {
            model: page.themeChoices
            delegate: ThemeChoiceCard {
                required property var modelData
                title: modelData.title
                themeId: modelData.id
                preview: Backend.themePreviewUrl(modelData.id)
                selected: page.selectedIslandTheme === modelData.id
                onChosen: function(themeId) { page.chooseIslandTheme(themeId) }
            }
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "透明度"
        description: "调整完整和 mini 模式的窗口透明度"
        icon.name: "ic_fluent_transparency_square_20_regular"
        RowLayout {
            Layout.preferredWidth: 260
            Slider {
                id: islandOpacity
                Layout.fillWidth: true
                from: 0.35
                to: 1
                stepSize: 0.05
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("islandOpacity", value)
            }
            Text {
                Layout.preferredWidth: 52
                horizontalAlignment: Text.AlignRight
                text: Math.round(islandOpacity.value * 100) + "%"
                typography: Typography.Caption
            }
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "组件缩放"
        description: "调整灵动岛整体大小"
        icon.name: "ic_fluent_resize_20_regular"
        RowLayout {
            Layout.preferredWidth: 260
            Slider {
                id: islandScale
                Layout.fillWidth: true
                from: 0.75
                to: 1.35
                stepSize: 0.05
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("islandScale", value)
            }
            Text {
                Layout.preferredWidth: 52
                horizontalAlignment: Text.AlignRight
                text: Math.round(islandScale.value * 100) + "%"
                typography: Typography.Caption
            }
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "启动位置"
        description: "选择灵动岛在屏幕上的默认锚点"
        icon.name: "ic_fluent_location_20_regular"
        ComboBox {
            id: islandAnchor
            Layout.preferredWidth: 150
            model: ["左上", "顶部中央", "右上", "左下", "底部中央", "右下"]
            onActivated: function(index) {
                if (!page.loading) Backend.setSetting("islandAnchor", ["top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right"][index])
            }
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "悬浮层级"
        description: "始终置顶或放置到桌面层"
        icon.name: "ic_fluent_stack_20_regular"
        ComboBox {
            id: islandLayer
            Layout.preferredWidth: 150
            model: ["始终置顶", "置于底层"]
            onActivated: function(index) {
                if (!page.loading) Backend.setSetting("islandLayer", ["top", "bottom"][index])
            }
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "光影效果"
        description: "显示灵动岛下方的柔和阴影"
        icon.name: "ic_fluent_sparkle_20_regular"
        Switch {
            id: islandLighting
            onClicked: if (!page.loading) Backend.setSetting("islandLightingEffect", checked)
        }
    }

    Text {
        Layout.fillWidth: true
        text: "AI 规划"
        typography: Typography.BodyStrong
    }
    SettingCard {
        Layout.fillWidth: true
        title: "API 服务地址"
        description: "支持 OpenAI 兼容接口"
        icon.name: "ic_fluent_cloud_20_regular"
        TextField {
            id: aiBaseUrl
            Layout.preferredWidth: 360
            placeholderText: "https://api.openai.com/v1"
            onEditingFinished: if (!page.loading) Backend.setSetting("aiBaseUrl", text.trim())
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "模型与密钥"
        description: "密钥只保存在本地设置文件"
        icon.name: "ic_fluent_key_20_regular"
        RowLayout {
            Layout.preferredWidth: 470
            TextField {
                id: aiModel
                Layout.preferredWidth: 170
                placeholderText: "gpt-4o-mini"
                onEditingFinished: if (!page.loading) Backend.setSetting("aiModel", text.trim())
            }
            TextField {
                id: aiApiKey
                Layout.fillWidth: true
                placeholderText: "API Key"
                echoMode: TextInput.Password
                onEditingFinished: if (!page.loading) Backend.setSetting("aiApiKey", text.trim())
            }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "生成参数"
        description: "调整温度和长期计划的等待时间"
        icon.name: "ic_fluent_options_20_regular"
        RowLayout {
            Layout.preferredWidth: 430
            Text { text: "温度"; typography: Typography.Caption }
            Slider {
                id: aiTemperature
                Layout.fillWidth: true
                from: 0
                to: 2
                stepSize: 0.1
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("aiTemperature", value)
            }
            Text { text: aiTemperature.value.toFixed(1); typography: Typography.Caption }
            SpinBox {
                id: aiTimeout
                from: 30
                to: 1200
                stepSize: 30
                onValueModified: if (!page.loading) Backend.setSetting("aiTimeout", value)
            }
            Text { text: "秒"; typography: Typography.Caption }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "自动导入短期计划"
        description: "生成短期计划后直接写入任务、任务流和项目"
        icon.name: "ic_fluent_arrow_download_20_regular"
        Switch { id: aiAutoApply; onClicked: if (!page.loading) Backend.setSetting("aiAutoApply", checked) }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "替换旧 AI 内容"
        description: "导入新计划时清理上一次 AI 生成的条目"
        icon.name: "ic_fluent_arrow_repeat_all_20_regular"
        Switch { id: aiReplaceOnApply; onClicked: if (!page.loading) Backend.setSetting("aiReplaceOnApply", checked) }
    }

    Text {
        Layout.fillWidth: true
        text: "应用"
        typography: Typography.BodyStrong
    }
    SettingCard {
        Layout.fillWidth: true
        title: "开机自动启动"
        description: "使用 Windows 注册表或启动目录启动 FlowTodo"
        icon.name: "ic_fluent_power_20_regular"
        Switch { id: autoStart; onClicked: if (!page.loading) Backend.setSetting("autoStart", checked) }
    }

    Text {
        Layout.fillWidth: true
        text: "数据"
        typography: Typography.BodyStrong
    }
    SettingCard {
        Layout.fillWidth: true
        title: "FlowTodo 数据目录"
        description: "原版与原生实验共用同一套 JSON 数据"
        icon.name: "ic_fluent_folder_20_regular"
        Text {
            Layout.preferredWidth: 360
            text: Backend.dataPath
            typography: Typography.Caption
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideMiddle
            color: Theme.currentTheme.colors.textSecondaryColor
        }
        Button {
            text: "更改"
            icon.name: "ic_fluent_folder_open_20_regular"
            onClicked: Backend.chooseDataDirectory()
        }
    }
}
