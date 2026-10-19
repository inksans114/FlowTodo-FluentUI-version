import QtQuick
import QtQuick.Controls
import RinUI
import "../i18n"

Button {
    id: control
    property string nodeKey: ""
    objectName: "taskRelationsMore"
    text: I18n.t("更多")
    flat: true
    icon.name: "ic_fluent_more_horizontal_20_regular"
    onClicked: options.open()
    QuietMenu {
        id: options
        parent: control
        MenuItem { text: I18n.t("关联任务"); icon.name: "ic_fluent_link_20_regular"; onTriggered: Backend.openTaskRelations(control.nodeKey) }
    }
}
