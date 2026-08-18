import QtQuick 2.15

QtObject {
    id: root

    // 用法同ButtonGroup
    property bool exclusive: true
    property var items: []
    property Item checkedItem: null
    readonly property int checkState: {
        let count = 0;
        for (let b of items)
            if (b.checked)
                count++;
        return count === 0 ? Qt.Unchecked :
               count === items.length ? Qt.Checked :
               Qt.PartiallyChecked;
    }


    // 方法 / functions //
    function register(button) {
        if (items.indexOf(button) === -1)
            items.push(button)
    }

    function unregister(button) {
        const idx = items.indexOf(button)
        if (idx !== -1)
            items.splice(idx, 1)
    }

    function updateCheck(button) {
        if (exclusive) {
            for (let b of items) {
                b.checked = (b === button)
            }
            checkedItem = button
        } else {
            checkedItem = button.checked ? button : null
        }
    }
}
