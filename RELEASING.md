# FlowTodo 自动更新发布说明

## macOS 测试版

使用 GitHub Actions 的 `Build macOS test app` 手动构建 Apple Silicon `.app` 和 ZIP。触发、下载、支持范围与测试步骤见 [Mac 构建说明](docs/MACOS_BUILD.md)。Mac 测试版尚未公证，不使用 Windows 自动更新安装器。

## PyInstaller 对照打包

运行 `build_pyinstaller.bat` 创建文件夹版，并生成完整 ZIP。输出使用独立的 `dist-pyinstaller/build-时间戳-随机后缀/`，不会覆盖 Nuitka 的 `dist/`。EXE 位于该次输出的 `FlowTodo/FlowTodo.exe`；中间文件和 spec 也留在本次输出目录。脚本不自动启动应用。

可用 `build_pyinstaller.bat --no-zip --no-run` 跳过 ZIP 压缩和结束时暂停，以便单独对比打包耗时；随后手动运行 EXE 对比启动速度。`--check` 仅做预检，不安装依赖或生成产物；首次需要由正式打包步骤安装 PyInstaller 6。保持与 Nuitka 相同的业务资源与监督模型，不打包本机用户数据。

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
2. 可先执行 `build_nuitka.bat --check`，仅检查依赖、源码和资源，不安装、不编译、不启动应用。正式打包执行 `build_nuitka.bat`；不希望打包后启动应用时使用 `build_nuitka.bat --no-run`。
3. 每次构建使用独立的 `dist/build-时间戳-随机后缀/` 目录，并在其中生成 `FlowTodo-Windows-x64-版本号.zip`，保留以前的构建。
4. 创建对应版本的 GitHub Release，可以是正式版本或预发布版本。
5. 上传 ZIP、MSI 或安装 EXE，不要只保留 GitHub 自动生成的源码包。

用户数据位于 `%LOCALAPPDATA%\FlowTodo\data`，不在安装目录内，自动更新不会覆盖该目录。

`build_nuitka.bat` 的 `--include-module` 列表显式收录应用业务模块；新增需要随应用发布的模块时更新此列表。预检会检查这些源码是否存在并解析语法。测试、预览和发布工具无需加入业务模块列表。QML、场景、音频、翻译、监督模型和手机镜头网页仍按资源目录打包。

默认使用两个并行编译进程，兼顾 16 GB 内存设备的编译速度与内存需求；开始前建议关闭不使用的应用。内存仍不足时可手动改为 `--jobs=1` 并加上 `--low-memory`。排除 MediaPipe 测试和应用未使用的 Pillow Tk/Qt 图像适配模块。OCR 模型与配置通过专用 YAML 配置收录，避免重复加入。
