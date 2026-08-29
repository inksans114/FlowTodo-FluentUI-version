# Shared layouts

## qml/Main.qml

The application shell is a `FluentWindow` with RinUI's built-in `navigationView` and a stacked page host. It uses a 1180x760 default window, 900x620 minimum, a 224px expanded navigation rail, and positions widget/note/settings items at the bottom. The shell owns the tray/widget bridge, appearance application, settings route, and focus preparation routes.

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

FluentWindow {
    id: window
    visible: true
    title: "FlowTodo"
    width: 1180
    height: 760
    minimumWidth: 900
    minimumHeight: 620
    navigationView.navMinimumExpandWidth: 960
    navigationView.navExpandWidth: 224
    navigationItems: [
        { title: "今日任务", page: Qt.resolvedUrl("pages/HomeDashboard.qml"), icon: "ic_fluent_checkmark_circle_20_regular" },
        { title: "任务流", page: Qt.resolvedUrl("pages/GroupsWorkspace.qml"), icon: "ic_fluent_flow_20_regular" },
        { title: "项目", page: Qt.resolvedUrl("pages/ProjectsWorkspace.qml"), icon: "ic_fluent_board_20_regular" },
        { title: "专注模式", page: Qt.resolvedUrl("pages/FocusWorkspace.qml"), icon: "ic_fluent_timer_20_regular" },
        { title: "AI 规划", page: Qt.resolvedUrl("pages/AiWorkspace.qml"), icon: "ic_fluent_sparkle_20_regular" },
        { title: "账户统计", page: Qt.resolvedUrl("pages/AccountOverview.qml"), icon: "ic_fluent_person_20_regular" },
        { title: "桌面小组件", page: Qt.resolvedUrl("pages/WidgetHub.qml"), icon: "ic_fluent_apps_list_detail_20_regular", position: Position.Bottom },
        { title: "桌面便签", page: Qt.resolvedUrl("pages/NoteHub.qml"), icon: "ic_fluent_note_20_regular", position: Position.Bottom },
        { title: "系统设置", page: Qt.resolvedUrl("pages/SettingsHub.qml"), icon: "ic_fluent_settings_20_regular", position: Position.Bottom }
    ]
}
```

