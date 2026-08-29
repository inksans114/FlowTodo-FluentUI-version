import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentPage {
    id: page
    title: "桌面便签"
    wrapperWidth: 860
    horizontalPadding: 36
    contentSpacing: 12
    property bool loading: true

    function load() {
        loading = true
        enabledSwitch.checked = Boolean(Backend.getSetting("notesEnabled", true))
        autoShow.checked = Boolean(Backend.getSetting("notesAutoShow", false))
        topSwitch.checked = Boolean(Backend.getSetting("notesAlwaysOnTop", false))
        opacitySlider.value = Number(Backend.getSetting("notesOpacity", 0.96))
        edgeSwitch.checked = Boolean(Backend.getSetting("notesEdgeDock", true))
        widthSlider.value = Number(Backend.getSetting("notesDefaultWidth", 320))
        heightSlider.value = Number(Backend.getSetting("notesDefaultHeight", 360))
        gapSlider.value = Number(Backend.getSetting("notesCapsuleGap", 6))
        loading = false
    }
    Component.onCompleted: load()
    Connections { target: Backend; function onSettingsChanged() { if (!page.loading) page.load() } }

    SettingCard {
        Layout.fillWidth: true
        title: "启用桌面便签"
        description: "在桌面上显示可独立移动的便签纸片"
        icon.name: "ic_fluent_note_20_regular"
        Switch { id: enabledSwitch; onClicked: if (!page.loading) Backend.setSetting("notesEnabled", checked) }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "启动时显示"
        description: "打开 FlowTodo 后恢复上次可见的便签"
        icon.name: "ic_fluent_pin_20_regular"
        Switch { id: autoShow; onClicked: if (!page.loading) Backend.setSetting("notesAutoShow", checked) }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "默认置顶"
        description: "新建便签显示在其他窗口上方"
        icon.name: "ic_fluent_arrow_sort_up_20_regular"
        Switch { id: topSwitch; onClicked: if (!page.loading) Backend.setSetting("notesAlwaysOnTop", checked) }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "便签透明度"
        description: Math.round(opacitySlider.value * 100) + "%"
        icon.name: "ic_fluent_transparency_square_20_regular"
        RowLayout {
            Layout.preferredWidth: 330
            Slider {
                id: opacitySlider
                Layout.fillWidth: true
                from: 0.45
                to: 1
                stepSize: 0.05
                onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("notesOpacity", value)
            }
            Text { text: Math.round(opacitySlider.value * 100) + "%"; typography: Typography.Caption }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "折叠后贴边叠放"
        description: "胶囊沿屏幕边缘连续排列；展开统一在主应用的便签页操作"
        icon.name: "ic_fluent_stack_20_regular"
        Switch { id: edgeSwitch; onClicked: if (!page.loading) Backend.setSetting("notesEdgeDock", checked) }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "新便签默认尺寸"
        description: Math.round(widthSlider.value) + " × " + Math.round(heightSlider.value)
        icon.name: "ic_fluent_resize_20_regular"
        ColumnLayout {
            Layout.preferredWidth: 340
            RowLayout { Layout.fillWidth: true
                Text { text: "宽度"; typography: Typography.Caption }
                Slider { id: widthSlider; Layout.fillWidth: true; from: 240; to: 560; stepSize: 20; onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("notesDefaultWidth", Math.round(value)) }
                Text { text: Math.round(widthSlider.value); typography: Typography.Caption }
            }
            RowLayout { Layout.fillWidth: true
                Text { text: "高度"; typography: Typography.Caption }
                Slider { id: heightSlider; Layout.fillWidth: true; from: 220; to: 680; stepSize: 20; onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("notesDefaultHeight", Math.round(value)) }
                Text { text: Math.round(heightSlider.value); typography: Typography.Caption }
            }
        }
    }
    SettingCard {
        Layout.fillWidth: true
        title: "胶囊间距"
        description: Math.round(gapSlider.value) + " px"
        icon.name: "ic_fluent_text_spacing_20_regular"
        Slider { id: gapSlider; Layout.preferredWidth: 330; from: 0; to: 20; stepSize: 1; onPressedChanged: if (!pressed && !page.loading) Backend.setSetting("notesCapsuleGap", Math.round(value)) }
    }
    Frame {
        Layout.fillWidth: true
        RowLayout { anchors.fill: parent; spacing: 10
            Icon { name: "ic_fluent_note_add_20_regular"; size: 22; color: Theme.currentTheme.colors.primaryColor }
            Text { Layout.fillWidth: true; text: "便签窗口"; typography: Typography.BodyStrong }
            Button { text: "新建"; highlighted: true; icon.name: "ic_fluent_add_20_regular"; onClicked: Backend.createNote() }
            Button { text: "显示全部"; icon.name: "ic_fluent_eye_20_regular"; onClicked: Backend.showNotes() }
            Button { text: "隐藏全部"; icon.name: "ic_fluent_eye_off_20_regular"; onClicked: Backend.hideNotes() }
        }
    }
}
