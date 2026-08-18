import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "应用拦截"
    wrapperWidth: 880
    horizontalPadding: 36
    contentSpacing: 10
    property string query: ""
    property string returnLabel: "返回系统设置"
    ListModel { id: appModel }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    function load() {
        var all = []
        var selected = Backend.getSetting("focusGuardWhitelist", [])
        var selectedKeys = {}
        for (var i = 0; i < selected.length; i++) selectedKeys[String(selected[i].path || selected[i].process || selected[i]).toLowerCase()] = true
        try { all = JSON.parse(Backend.getFocusGuardAppsJson()) } catch (error) { all = [] }
        appModel.clear()
        for (var j = 0; j < all.length; j++) {
            var item = all[j]
            var key = String(item.path || item.process).toLowerCase()
            appModel.append({name: item.name, process: item.process, path: item.path, system: Boolean(item.system), selected: selected.length ? Boolean(selectedKeys[key]) : Boolean(item.system)})
        }
    }
    function save() {
        var picked = []
        for (var i = 0; i < appModel.count; i++) { var item = appModel.get(i); if (item.selected) picked.push({name: item.name, process: item.process, path: item.path}) }
        Backend.setSettingJson("focusGuardWhitelist", JSON.stringify(picked))
        page.goBack()
    }
    function goBack() { var router = nav(); if (router) router.pop() }
    Component.onCompleted: load()
    RowLayout { Layout.fillWidth: true
                ToolButton { icon.name: "ic_fluent_arrow_left_20_regular"
                ToolTip.text: page.returnLabel
                ToolTip.visible: hovered
                onClicked: page.goBack() }
                Text { text: page.returnLabel
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor }
                Item { Layout.fillWidth: true } }
    Text { Layout.fillWidth: true
                text: "开启沉浸拦截时，选中的程序不会触发提醒；系统关键程序默认允许。"
                typography: Typography.Body
                color: Theme.currentTheme.colors.textSecondaryColor
                wrapMode: Text.Wrap }
    RowLayout { Layout.fillWidth: true
                TextField { Layout.fillWidth: true
                placeholderText: "搜索应用"
                onTextChanged: page.query = text.trim().toLowerCase() }
                Button { text: "恢复系统默认"
                icon.name: "ic_fluent_arrow_reset_20_regular"
                onClicked: { for (var i = 0; i < appModel.count; i++) appModel.setProperty(i, "selected", Boolean(appModel.get(i).system)) } } }
    Frame { Layout.fillWidth: true
                Layout.preferredHeight: 440
                leftPadding: 8
                rightPadding: 8
                topPadding: 8
                bottomPadding: 8
        ScrollView { anchors.fill: parent
                clip: true
            ColumnLayout { width: parent.width
                spacing: 2
                Repeater { model: appModel
                delegate: Item {
                    visible: !page.query.length || (String(model.name || "") + " " + String(model.process || "")).toLowerCase().indexOf(page.query) >= 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? 48 : 0
                    RowLayout { anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                CheckBox { checked: Boolean(model.selected)
                onClicked: appModel.setProperty(index, "selected", checked) }
                ColumnLayout { Layout.fillWidth: true
                spacing: 0
                Text { Layout.fillWidth: true
                text: String(model.name)
                typography: Typography.Body
                elide: Text.ElideRight }
                Text { Layout.fillWidth: true
                text: String(model.process)
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                elide: Text.ElideMiddle } }
                Text { visible: Boolean(model.system)
                text: "系统"
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor } }
                } }
            }
        }
    }
    RowLayout { Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "取消"
                onClicked: page.goBack() }
                Button { text: "保存允许列表"
                highlighted: true
                icon.name: "ic_fluent_save_20_regular"
                onClicked: page.save() } }
}


