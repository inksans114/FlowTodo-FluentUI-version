# 关于与更新

设置首页提供「关于 FlowTodo」和「软件更新」入口。版本号直接读取 `version.APP_VERSION`，两个页面共用 `UpdatePanel` 和同一个 `UpdateManager`，不会重复启动下载任务。

自动更新默认开启，沿用 `updateAutoDownload` 设置。开启时在启动和登录后检查并下载更新；关闭后停止后续自动检查与下载，手动检查仍可使用。切换开关不会中断已经开始的网络请求。

下载仅将经过校验的文件暂存到更新缓存，不退出应用。用户点击「安装并重启」并确认后，后台启动更新助手。助手必须先写出就绪回执，主程序才请求退出；进程创建成功本身不代表助手已就绪。启动异常、提前退出或八秒内未确认就绪时保留主程序运行，错误显示在页面，助手输出保存在 `%LOCALAPPDATA%\FlowTodo\updates\installer-launch.log`。

下次打开软件时，之前已下载且匹配当前安装目录的新版本会重新显示为可安装，不会自动安装。Microsoft Store 版本由商店管理更新；源码和非 Windows 版本可检查发布信息，通过发布页获取安装包。

验证：`tests/test_update_controls.py`、`tests/test_updater.py`、`tests/test_i18n.py`，以及 `tools/about_update_smoke.py`。后者使用临时数据测试实际 QML 页面和开关保存，以模拟状态验证进度、安装确认、繁体与英文，不下载或安装真实更新。安装助手的回执逻辑使用模拟进程验证，仍需在最终打包版本上做实际升级验收。
