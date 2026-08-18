# FlowTodo RinUI

FlowTodo 的 PySide6 + QML 原生迁移版本。主窗口不再依赖 WebEngine，界面基于
[RinUI](https://github.com/RinLit-233-shiroko/Rin-UI)（Fluent Design 风格 UI 库），
业务逻辑通过 `BackendBridge` / `RinUIBackend` 复用既有 JSON 数据层，保持与旧版本
数据完全兼容。

## 功能

- 今日任务、任务流、项目、专注模式
- 任务流 / 项目编辑器
- 任务流启动准备、项目启动准备、专注进行页
- AI 规划、长期计划预览、账户统计、每日启动页
- RinUI / Class Widgets 主题、系统明暗模式、窗口材质
- AI 接口配置、开机启动、数据目录设置、灵动岛

新旧版本共享 `%LOCALAPPDATA%\FlowTodo\data`，已有 JSON 数据无需转换。

## 技术栈

| 组件 | 说明 |
| --- | --- |
| Python | 3.9+（Windows） |
| PySide6 | Qt 6 官方 Python 绑定，>= 6.11.1 |
| QML | 界面声明语言（`qml/` 目录） |
| RinUI | Fluent Design 风格 QML UI 库（已随仓库 vendored 到 `vendor/RinUI`） |
| darkdetect | 系统明暗模式检测 |
| pywin32 | Windows 平台能力（窗口 / 原生集成） |

## 运行方式

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用
python .\app.py
```

> 说明：`app.py` 会优先从项目内 `vendor/` 目录加载 RinUI（已随仓库提交，
> 保证克隆后开箱即用）。如需改用 pip 安装的 RinUI，可执行
> `pip install "RinUI>=0.4.2"`，或删除 `vendor/` 后以普通方式安装依赖。

## 目录结构

```
FlowTodo_RinUI/
├── app.py               # 入口：加载 vendor/RinUI 并启动 QML 窗口
├── main.py              # 主业务逻辑（任务流 / 项目 / 专注 / AI 规划等）
├── compat_backend.py    # RinUI 后端桥接（QML <-> Python）
├── backend.py           # 业务后端
├── island.py            # 灵动岛逻辑
├── qml/                 # QML 界面
├── vendor/RinUI/        # RinUI 库（运行时依赖，MIT License）
├── requirements.txt     # Python 依赖
└── CLASS_WIDGETS_2_LICENSE.txt  # Class Widgets 2 设计参考的 MIT 许可证
```

## 许可证

- 本项目代码：开源发布（许可证见仓库 LICENSE 说明）。
- 第三方组件：
  - RinUI：MIT License，见 `vendor/LICENSE`（Copyright (c) 2025 RinLit）。
  - Class Widgets 2 设计参考：MIT License，见 `CLASS_WIDGETS_2_LICENSE.txt`。
