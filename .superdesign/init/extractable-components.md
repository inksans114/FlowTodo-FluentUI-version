# Extractable components

## AppShell

- Source: `qml/Main.qml`
- Category: layout
- Description: FluentWindow shell with navigation stack and desktop integrations.
- Extractable props: active page, navigation items.
- Hardcoded: FlowTodo title, page labels, icons, and RinUI shell.

## MetricCard

- Source: `qml/components/MetricCard.qml`
- Category: basic
- Description: Compact icon/value/label statistic card.
- Extractable props: label, value, iconName, accent.
- Hardcoded: padding, radius, and Fluent typography roles.

## ThemeChoiceCard

- Source: `qml/components/ThemeChoiceCard.qml`
- Category: basic
- Description: Image-backed theme selector with selected border.
- Extractable props: title, themeId, preview, selected.

## DeleteConfirmDialog

- Source: `qml/components/DeleteConfirmDialog.qml`
- Category: basic
- Description: destructive-action confirmation dialog.
- Extractable props: itemType, itemName.

