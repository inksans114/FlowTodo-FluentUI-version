# FlowTodo 自动更新发布说明

应用启动后会在后台检查：

`https://github.com/inksans114/FlowTodo-FluentUI-version/releases`

当前应用版本在 `version.py` 的 `APP_VERSION` 中维护。发布新版本前必须先修改该值，
例如从 `1.0` 改为 `1.1`，并使用相同版本号创建 GitHub Release 标签。

## Windows 更新资产

每个新 Release 至少上传一个可执行的 Windows 资产。推荐上传完整 Nuitka 独立目录的 ZIP：

`FlowTodo-Windows-x64-1.1.zip`

ZIP 可以直接包含 `app.dist` 目录，也可以直接包含 `FlowTodo.exe`、PySide6 和其他运行文件。
更新器会识别单一顶层目录，并在 FlowTodo 退出后替换旧安装目录、重新启动应用。

也支持以下安装资产：

- `FlowTodo-Setup-1.1.exe`
- `FlowTodo-Windows-x64-1.1.msi`

普通源码 ZIP、GitHub 自动生成的 Source code 压缩包以及不带安装标识的单文件 EXE
不会被自动安装。

## 发布检查

1. 更新 `version.py`。
2. 执行 `build_nuitka.bat`。
3. 构建脚本会自动生成 `dist/FlowTodo-Windows-x64-版本号.zip`。
4. 创建对应版本的 GitHub Release，可以是正式版本或预发布版本。
5. 上传 ZIP、MSI 或安装 EXE，不要只保留 GitHub 自动生成的源码包。

用户数据位于 `%LOCALAPPDATA%\FlowTodo\data`，不在安装目录内，自动更新不会覆盖该目录。
