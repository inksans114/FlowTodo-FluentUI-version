import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"

FluentPage {
    id: page
    objectName: "archivedTasksPage"
    title: I18n.t("归档任务")
    wrapperWidth: 720
    property var archived: []
    function reload() { try { archived = JSON.parse(Backend.getArchivedTasks()) } catch (error) { archived = [] } }
    function nav() { var item = page; while (item) { if (item.objectName === "MainNavigationView") return item; item = item.parent } return null }
    Component.onCompleted: reload()
    Connections { target: Backend; function onTasksChanged() { page.reload() } }
    Button { text: I18n.t("返回"); flat: true; onClicked: { var router = page.nav(); if (router) router.pop() } }
    Text { Layout.fillWidth: true; text: I18n.t("这些任务已从待办列表移走，没有被标记为完成。需要时可以恢复到今天。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
    Text { visible: page.archived.length === 0; text: I18n.t("目前没有归档任务") }
    Repeater {
        model: page.archived
        delegate: Frame {
            required property var modelData
            Layout.fillWidth: true
            padding: 18
            contentItem: RowLayout {
                spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; text: String(modelData.title || ""); wrapMode: Text.Wrap; typography: Typography.BodyStrong }
                    Text { text: I18n.t("归档于 ") + String(modelData.archivedAt || "").slice(0, 10); color: Theme.currentTheme.colors.textSecondaryColor; typography: Typography.Caption }
                }
                Button { text: I18n.t("恢复到今天"); onClicked: Backend.restoreArchivedTask(Number(modelData.id)) }
            }
        }
    }
}
