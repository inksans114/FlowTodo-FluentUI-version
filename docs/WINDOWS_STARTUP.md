# Windows 登录启动

设置 → 应用与数据 → 开机自动启动。此功能在当前用户的 Windows 启动文件夹创建 `FlowTodo.lnk`，不会复制整个软件。按 `Win + R`，输入 `shell:startup` 可以查看快捷方式。

- 源码版：使用当前 Python 环境的 `pythonw.exe`（没有时使用 `python.exe`），参数为绝对路径的 `app.py`，工作目录为项目目录。
- PyInstaller 版：直接启动 `sys.executable` 指向的软件 EXE。
- Nuitka 版：启动外层软件 EXE，单文件模式也不使用临时解压目录。路径依据 [Nuitka 的路径说明](https://nuitka.net/user-documentation/common-issue-solutions.html)。
- 开启后校验快捷方式的目标、参数和工作目录，并清理旧的 FlowTodo 注册表 Run 项与 `FlowDeck_AutoStart.bat`，避免重复启动。
- 关闭时删除上述属于本软件的启动项；其他软件的启动项不受影响。
- 界面读取实际注册情况，写入失败会提示错误并恢复实际状态。更改其他设置不会重写启动项。

旧版本指向 `main.py` 的启动项需要在更新的软件中重新开启此开关。软件移动目录或源码环境删除后，也需要重新设置。如果在 Windows 设置或任务管理器禁用了此启动项，需要在那里恢复启用。是否在登录时成功运行仍需实际注销或重启验证。

验证：`python -B -m unittest discover -s tests -p test_startup.py -v`；`python -B tools/startup_smoke.py`。真实 COM 快捷方式与 QML 联动测试均使用临时目录和临时用户数据，不更改本机启动项。
