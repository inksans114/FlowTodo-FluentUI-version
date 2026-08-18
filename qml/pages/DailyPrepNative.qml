import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "每日启动预备"
    wrapperWidth: 760
    horizontalPadding: 34
    property var welcome: ({})
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    Component.onCompleted: { try { welcome = JSON.parse(Backend.check_daily_welcome()) } catch (error) { welcome = {} } }
    SettingCard {
        Layout.fillWidth: true
        title: Backend.todayLabel
        description: welcome.need_welcome ? "新的一天，从一次清晰的准备开始" : "今日准备已经完成，也可以随时重新查看"
        icon.name: "ic_fluent_weather_sunny_20_regular"
        ColumnLayout {
            Layout.fillWidth: true
            Text { text: "今日任务、任务流和项目都已同步"; typography: Typography.Body }
            Button { text: "进入今日任务"; highlighted: true; icon.name: "ic_fluent_checkmark_circle_20_regular"; onClicked: { var router = page.nav(); if (router) router.safePop() } }
        }
    }
}
