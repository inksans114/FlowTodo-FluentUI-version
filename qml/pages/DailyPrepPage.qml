import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"

FluentPage {
    id: page
    title: I18n.t("每日启动预备")
    wrapperWidth: 760
    horizontalPadding: 34
    SettingCard { Layout.fillWidth: true; title: I18n.t("开始新的一天"); description: I18n.t("查看今日任务并选择一个专注入口"); icon.name: "ic_fluent_weather_sunny_20_regular"; ColumnLayout { Layout.fillWidth: true; Text { text: Backend.todayLabel; typography: Typography.Title }; Text { text: I18n.t("完成准备后，从今日任务或任务流开始。"); typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor }; Button { text: I18n.t("打开今日任务"); highlighted: true; icon.name: "ic_fluent_checkmark_circle_20_regular"; onClicked: page.parent && page.parent.pop ? page.parent.pop() : null } } }
}
