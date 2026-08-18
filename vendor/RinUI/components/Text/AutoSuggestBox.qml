import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../themes"
import "../../components"


TextField {
    id: input
    property alias suggestions: input.model
    property var model: []
    property bool userInput: true
    property alias textRole: filteredModel.textRole
    property int maximumMenuHeight: 350
    signal suggestionChosen(string suggestion)

    function getFilteredSuggestions() {
        if (!suggestions) return []

        let role = textRole || "text"  // 默认 role 为 "text"
        let res = []

        if (suggestions instanceof ListModel) {
            for (let i = 0; i < suggestions.count; i++) {
                let item = suggestions.get(i)
                if (item[role] && item[role].toLowerCase().includes(input.text.toLowerCase()))
                    res.push(item[role])
            }
        } else if (Array.isArray(suggestions)) {
            for (let i = 0; i < suggestions.length; i++) {
                let s = suggestions[i]
                if (typeof s === "string") {
                    if (s.toLowerCase().includes(input.text.toLowerCase()))
                        res.push(s)
                } else if (s && s[role]) {
                    if (s[role].toLowerCase().includes(input.text.toLowerCase()))
                        res.push(s[role])
                }
            }
        }

        return res.length > 0 ? res : [qsTr("No results found")]
    }

    onTextChanged: {
        if (userInput) {
            filteredModel.model = getFilteredSuggestions()
            filteredModel.currentIndex = -1
            suggestionsPopup.open()
        }
    }

    onAccepted: {
        suggestionsPopup.close()
    }


    Popup {
        id: suggestionsPopup
        width: input.width
        y: input.height
        implicitWidth: 100
        implicitHeight: Math.min(filteredModel.contentHeight + 6, maximumMenuHeight)
        padding: 0


        ListView {
            id: filteredModel
            anchors.fill: parent
            anchors.topMargin: 4
            anchors.bottomMargin: 4
            clip: true

            ScrollBar.vertical: ScrollBar {
                id: scrollBar
                policy: ScrollBar.AsNeeded
            }

            delegate: ListViewDelegate {
                width: parent.width
                text: modelData
                onClicked: {
                    input.text = modelData
                    suggestionsPopup.close()
                    input.suggestionChosen(modelData)
                    accepted()
                }
            }
        }

        Keys.onPressed: {
            if (!suggestionsPopup.visible) return

            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                event.accepted = true
                if (filteredModel.currentIndex >= 0 && filteredModel.currentIndex < filteredModel.count) {
                    let selected = filteredModel.model[filteredModel.currentIndex]
                    text = selected
                    suggestionsPopup.close()
                    suggestionChosen(selected)
                    accepted()
                }
            }
        }
    }

    Keys.onPressed: {
        if (!suggestionsPopup.visible) return

        if (event.key === Qt.Key_Down) {
            event.accepted = true
            if (filteredModel.count > 0) {
                filteredModel.currentIndex = Math.min(filteredModel.currentIndex + 1, filteredModel.count - 1)
                // 临时标记不是用户输入，避免触发过滤
                userInput = false
                text = filteredModel.model[filteredModel.currentIndex]  // 仅改变 text 不触发过滤
                userInput = true
            }
        } else if (event.key === Qt.Key_Up) {
            event.accepted = true
            if (filteredModel.count > 0) {
                filteredModel.currentIndex = Math.max(filteredModel.currentIndex - 1, 0)
                userInput = false
                text = filteredModel.model[filteredModel.currentIndex]
                userInput = true
            }
        }
    }

}
