import QtQuick
import "../i18n"
import QtQuick.Layouts
import RinUI
Button {
    id: control
    objectName: "settingsPageBack"
    text: I18n.t("返回")
    flat: true
    icon.name: "ic_fluent_arrow_left_20_regular"
    Accessible.name: I18n.t("返回上一页")
    onClicked: {
        var item=control.parent
        while(item && item.objectName!=="MainNavigationView") item=item.parent
        if(item) item.pop()
    }
}
