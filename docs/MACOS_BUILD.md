# Mac 测试版构建与下载

当前构建目标是 Apple Silicon（M1/M2/M3/M4 等 M 系列）Mac，最低 macOS 13。Intel Mac 暂不在这个包的支持范围内。

这台开发电脑是 Windows，不能直接生成 Mac `.app`。仓库提供手动触发的 GitHub Actions，在 macOS 上安装依赖、打包、检查应用并上传下载文件。Windows 本地的 `--check` 仅检查源码和资源，不代表已经在 Mac 上运行成功。

## 在 GitHub 上打包

1. 登录 GitHub，将当前应用源码和新增文件推送到仓库默认分支 `master`。除了 `.github/workflows/build-macos.yml`，还需要本次新增的模块、`qml`、`vendor/RinUI`、`focus-studio`、`i18n`、`supervision-web`、模型下载脚本及 Mac 打包文件；只上传 workflow 会打包到旧代码或因为缺文件失败。不要提交本机用户数据、密钥、导出文件或设计工具缓存。
2. 打开仓库 **Actions → Build macOS test app → Run workflow**，选择 `master` 后运行。如果没有这个入口，先确认 workflow 文件已经上传到默认分支，并启用了 Actions。
3. 由你查看构建进度。流程最多运行 45 分钟，不会自动发布 Release，也不会改动源码。若失败，把失败步骤末尾的错误信息发给我即可。
4. 成功后在该次运行页面的 **Artifacts** 下载 `FlowTodo-macOS-arm64-test`。下载结果会保留 14 天。
5. 解压 GitHub 的 artifact 压缩包，再解压其中的 `FlowTodo-macOS-arm64-版本号-test.zip`，得到 `FlowTodo.app`。将它拖入“应用程序”后启动。

这是未公证的测试包：默认使用临时签名，没有 Apple Developer ID 签名和 Apple 公证，macOS 可能提示无法验证开发者。先交给少量 Mac 用户测试；正式广泛分发前补上开发者签名与公证。

## 这个包包含什么

- 待办、AI 助手、保存方案、专注计时、沉浸网页场景、音频和本地监督模型。
- 摄像头与麦克风的系统权限说明；手机摄像头连接使用局域网权限说明。是否能正常使用仍需真实 Mac 验证。
- 数据保存到 `~/Library/Application Support/FlowTodo/data`，界面配置也在该应用支持目录中，不写入 `.app` 内部。
- 系统语音输入提示改为 macOS 听写，不发送 Windows 的 `Win + H` 快捷键。
- Windows 屏幕巡查、应用拦截和开机自启暂不在 Mac 上启用。更新器只提示发布页，避免下载、运行 Windows 安装器。

构建会检查应用架构、资源、Qt WebEngine 子进程、Cocoa 插件、权限说明和签名，并用独立临时数据启动应用后退出。这个启动检查不打开摄像头、麦克风，也不请求 AI。它不能代替真实 Mac 上的交互测试。

## 在 Mac 本机打包

安装原生 ARM64 Python 3.12 后，在仓库目录执行：

```bash
bash build_macos.command
```

脚本创建独立的 `.venv-macos`，安装依赖、校验监督模型并构建到 `dist/macos-时间戳/`，保留以前的构建。仅做源码预检可执行：

```bash
python3 tools/build_macos.py --check
```

预检前模型需已准备好；缺失时执行 `python3 tools/prepare_supervision_models.py`。

真实 Mac 测试时至少确认：首次启动与中文显示、创建并重启后保留待办、AI 方案进入专注、全屏/小窗切换、声音播放，以及授权后的摄像头监督。摄像头和麦克风需要用户主动开启；监督判定效果需要使用者实际校准。
