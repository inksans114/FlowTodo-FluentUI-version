import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "桌面便签"
    wrapperWidth: 900
    horizontalPadding: 36
    contentSpacing: 12
    property var notes: []

    function reload() {
        try { notes = JSON.parse(Backend.notesJson) } catch (error) { notes = [] }
    }
    Component.onCompleted: reload()
    Connections { target: Backend; function onNotesChanged() { page.reload() } }

    RowLayout {
        Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: "独立显示在桌面上的纸片便签"; typography: Typography.Body; color: Theme.currentTheme.colors.textSecondaryColor }
        Button { text: "新建便签"; highlighted: true; icon.name: "ic_fluent_note_add_20_regular"; onClicked: Backend.createNote() }
        Button { text: "显示全部"; icon.name: "ic_fluent_eye_20_regular"; onClicked: Backend.showNotes() }
    }

    Repeater {
        model: page.notes
        delegate: Frame {
            required property var modelData
            property bool initialized: false
            Layout.fillWidth: true
            Layout.preferredHeight: 90
            leftPadding: 16; rightPadding: 12; topPadding: 10; bottomPadding: 10
            RowLayout {
                anchors.fill: parent; spacing: 12
                Icon { name: modelData.collapsed ? "ic_fluent_stack_20_regular" : "ic_fluent_note_20_regular"; size: 22; color: Theme.currentTheme.colors.primaryColor }
                ColumnLayout { Layout.fillWidth: true; spacing: 3
                    Text { text: String(modelData.title || "未命名便签"); typography: Typography.BodyStrong; elide: Text.ElideRight }
                    Text { Layout.fillWidth: true; text: modelData.visible ? (modelData.collapsed ? "已折叠为胶囊" : "正在桌面显示") : "已隐藏"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                    RowLayout {
                        spacing: 8
                        CheckBox {
                            text: "置顶"
                            checked: Boolean(modelData.alwaysOnTop)
                            onClicked: if (initialized) Backend.setNoteAlwaysOnTop(modelData.id, checked)
                        }
                        Text { text: "胶囊位置"; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                        Segmented {
                            Layout.preferredWidth: 128
                            currentIndex: String(modelData.capsuleSide) === "left" ? 0 : 1
                            onCurrentIndexChanged: if (initialized && currentIndex >= 0) Backend.setNoteCapsuleSide(modelData.id, currentIndex === 0 ? "left" : "right")
                            SegmentedItem { text: "左" }
                            SegmentedItem { text: "右" }
                        }
                    }
                }
                Button { text: modelData.visible ? "隐藏" : "显示"; icon.name: modelData.visible ? "ic_fluent_eye_off_20_regular" : "ic_fluent_eye_20_regular"; onClicked: modelData.visible ? Backend.hideNote(modelData.id) : Backend.showNote(modelData.id) }
                Button { text: modelData.collapsed ? "在主应用展开" : "折叠"; icon.name: modelData.collapsed ? "ic_fluent_open_20_regular" : "ic_fluent_arrow_minimize_20_regular"; onClicked: Backend.toggleNoteCollapse(modelData.id) }
                ToolButton { icon.name: "ic_fluent_delete_20_regular"; ToolTip.text: "删除便签"; ToolTip.visible: hovered; onClicked: Backend.deleteNote(modelData.id) }
            }
            Component.onCompleted: initialized = true
        }
    }

    Text {
        visible: page.notes.length === 0
        Layout.fillWidth: true
        text: "还没有便签，先创建一张纸片。"
        horizontalAlignment: Text.AlignHCenter
        color: Theme.currentTheme.colors.textSecondaryColor
        typography: Typography.Body
    }
}
