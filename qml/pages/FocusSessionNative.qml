import QtQuick

FocusJourney {
    id: page
    property string mode: "single"
    property string titleText: ""
    property bool openImmersiveOnStart: mode !== "group"
    Component.onCompleted: Qt.callLater(function() {
        if (page.stage === "work" && page.openImmersiveOnStart) Backend.enterFocusStudio(page.sceneChoice)
    })
}
