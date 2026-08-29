# Shared UI components

Framework: PySide6 + QtQuick/QML. RinUI is vendored in `vendor/RinUI` and exposes Fluent controls (`Frame`, `Button`, `TextField`, `Segmented`, `SettingCard`, `Icon`, `FluentPage`). There is no web frontend or CSS framework.

## qml/components/MetricCard.qml

Reusable statistic card used by dashboard and account pages.

```qml
import QtQuick
import QtQuick.Layouts
import RinUI

Frame {
    id: root
    property string label: ""
    property string value: "0"
    property string iconName: "ic_fluent_info_20_regular"
    property color accent: Theme.currentTheme.colors.primaryColor
    Layout.fillWidth: true
    Layout.preferredHeight: 104
    leftPadding: 18; rightPadding: 18; topPadding: 16; bottomPadding: 16
    RowLayout { anchors.fill: parent; spacing: 14
        Rectangle { width: 42; height: 42; radius: 8; color: Qt.alpha(root.accent, 0.14)
            IconWidget { anchors.centerIn: parent; icon: root.iconName; size: 22; color: root.accent }
        }
        ColumnLayout { Layout.fillWidth: true; spacing: 2
            Text { text: root.value; typography: Typography.Subtitle; color: Theme.currentTheme.colors.textColor }
            Text { text: root.label; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
}
```

## qml/components/ThemeChoiceCard.qml

Selectable theme preview card. Props: `title`, `themeId`, `preview`, `selected`; signal `chosen`.

## qml/components/DeleteConfirmDialog.qml

RinUI dialog for destructive actions. Props: `itemType`, `itemName`; signal `deleteConfirmed`.

