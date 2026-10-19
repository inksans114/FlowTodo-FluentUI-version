import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("启动准备")
    wrapperWidth: 720
    horizontalPadding: 32
    property string nodeKey: ""
    property var choices: JSON.parse(Backend.getRelationChoices(nodeKey))
    property int minutes: Number((choices.node || {}).minutes || 25)
    property bool shield: false
    property bool showMore: false
    RowLayout {
        Layout.fillWidth: true
        ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"; onClicked: { var item = page; while (item && item.objectName !== "MainNavigationView") item = item.parent; if (item) item.pop() } Accessible.name: I18n.t("返回") }
        Item { Layout.fillWidth: true }
        TaskRelationsButton { nodeKey: page.nodeKey }
    }
    Frame {
        Layout.fillWidth: true; padding: 24
        contentItem: ColumnLayout {
            spacing: 16
            Text { Layout.fillWidth: true; text: (page.choices.node || {}).title || I18n.t("任务已移除"); typography: Typography.Subtitle; wrapMode: Text.Wrap }
            Text { Layout.fillWidth: true; text: (page.choices.node || {}).collectionTitle || ""; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
            TextField { id: goal; Layout.fillWidth: true; placeholderText: activeFocus ? "" : I18n.t("这次先做什么？") }
            RowLayout { Text { text: I18n.t("专注时长") } JourneySpinBox { from: 1; to: 180; value: page.minutes; onValueModified: page.minutes = value } Text { text: I18n.t("分钟") } Item { Layout.fillWidth: true } }
            JourneyButton { text: I18n.t("更多"); flat: true; onClicked: page.showMore = !page.showMore }
            CheckBox { visible: page.showMore; text: I18n.t("启用应用拦截"); checked: page.shield; onToggled: page.shield = checked }
            Text { Layout.fillWidth: true; visible: page.showMore && page.choices.next.length > 0; text: I18n.t("接下来：") + page.choices.next.map(function(n) { return n.title }).join("、"); typography: Typography.Caption; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.primaryColor }
            JourneyButton { text: I18n.t("开始专注"); highlighted: true; enabled: Boolean((page.choices.node || {}).key) && !page.choices.node.done; onClicked: Backend.startRelationNode(page.nodeKey, page.minutes, goal.text, page.shield) }
        }
    }
    Connections { target: Backend; function onTaskRelationsChanged() { page.choices = JSON.parse(Backend.getRelationChoices(page.nodeKey)) } }
}
