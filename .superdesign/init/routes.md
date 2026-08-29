# Routes

Routing is config-based through `qml/Main.qml`'s `navigationItems` and RinUI navigation stack.

| Entry | Page | Purpose |
|---|---|---|
| 今日任务 | `qml/pages/HomeDashboard.qml` | today's tasks, filters, add task |
| 日程 | `qml/pages/ScheduleWorkspace.qml` | week strip, future task planning, selected-day agenda |
| 任务流 | `qml/pages/GroupsWorkspace.qml` | multi-step focus flows |
| 项目 | `qml/pages/ProjectsWorkspace.qml` | projects and milestones |
| 专注模式 | `qml/pages/FocusWorkspace.qml` | start a task focus session |
| AI 规划 | `qml/pages/AiWorkspace.qml` | AI planning |
| 账户统计 | `qml/pages/AccountOverview.qml` | focus/task/project statistics and achievements |
| 桌面小组件 | `qml/pages/WidgetHub.qml` | desktop widget controls |
| 桌面便签 | `qml/pages/NoteHub.qml` | notes |
| 系统设置 | `qml/pages/SettingsHub.qml` | settings hub |

Additional stack pages include `AchievementsPage.qml`, `TaskCreatePage.qml`, `TaskPrepNative.qml`, `GroupPrepWorkspace.qml`, `ProjectPrepNative.qml`, and `FocusSessionNative.qml`.
