import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "AI 服务"
    wrapperWidth: 820
    horizontalPadding: 36
    contentSpacing: 12
    property bool loading: true
    function navigationView() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() { loading = true; baseUrl.text = String(Backend.getSetting("aiBaseUrl", "https://api.openai.com/v1")); modelName.text = String(Backend.getSetting("aiModel", "gpt-4o-mini")); apiKey.text = String(Backend.getSetting("aiApiKey", "")); temperature.value = Number(Backend.getSetting("aiTemperature", 0.7)); timeout.value = Number(Backend.getSetting("aiTimeout", 240)); loading = false }
    Component.onCompleted: load()
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: "返回系统设置"
                ToolTip.visible: hovered
                onClicked: { var router = page.navigationView(); if (router) router.pop() } }
                Text { text: "返回系统设置"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }
    Text { Layout.fillWidth: true
                text: "使用 OpenAI 兼容接口。密钥只保存在本机 FlowTodo 数据目录。"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        ColumnLayout { anchors.fill: parent
                spacing: 12
            Text { text: "连接"
                typography: Typography.Subtitle }
            TextField { id: baseUrl
                Layout.fillWidth: true
                placeholderText: "https://api.openai.com/v1"
                onEditingFinished: if (!page.loading) Backend.setSetting("aiBaseUrl", text.trim()) }
            TextField { id: modelName
                Layout.fillWidth: true
                placeholderText: "模型名称，例如 gpt-4o-mini"
                onEditingFinished: if (!page.loading) Backend.setSetting("aiModel", text.trim()) }
            TextField { id: apiKey
                Layout.fillWidth: true
                placeholderText: "API Key"
                echoMode: TextInput.Password
                onEditingFinished: if (!page.loading) Backend.setSetting("aiApiKey", text.trim()) }
        }
    }
    Frame { Layout.fillWidth: true
                leftPadding: 18
                rightPadding: 18
                topPadding: 16
                bottomPadding: 16
        ColumnLayout { anchors.fill: parent
                spacing: 12
            Text { text: "生成参数"
                typography: Typography.Subtitle }
            RowLayout { Layout.fillWidth: true
                Text { Layout.preferredWidth: 100
                text: "温度"
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
                text: "超时"
                typography: Typography.BodyStrong }
                SpinBox { id: timeout
                from: 30
                to: 1200
                stepSize: 30
                onValueModified: if (!page.loading) Backend.setSetting("aiTimeout", value) }
                Text { text: "秒"
                typography: Typography.Caption } }
        }
    }
}


