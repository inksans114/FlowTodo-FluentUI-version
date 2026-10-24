import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"
import "../i18n"

FluentPage {
    id: page
    objectName: "supervisionWorkspace"
    title: I18n.t("监督模式")
    wrapperWidth: 820
    horizontalPadding: 32
    contentSpacing: 18
    property var preferences: Backend.getSetting("supervisionPreferences", ({})) || ({})
    property var devices: []
    property var state: ({})
    property var available: ({})
    property bool showRepair: false
    property var phoneState: JSON.parse(Backend.supervision.phoneCamera.stateJson)
    property var phoneAddresses: JSON.parse(Backend.supervision.phoneCamera.addressesJson)
    property var phoneInterfaces: JSON.parse(Backend.supervision.phoneCamera.interfacesJson)
    property bool showPhoneCheck: false
    function refresh() {
        state = JSON.parse(Backend.supervision.stateJson)
    }
    function refreshSetup() {
        devices = JSON.parse(Backend.supervision.camerasJson)
        available = JSON.parse(Backend.supervision.availabilityJson)
    }
    function start() {
        Backend.startSupervision(JSON.stringify({
            mode: ["homework", "code", "reading", "phone"][mode.currentIndex],
            sensitivity: ["gentle", "normal", "strict"][strength.currentIndex],
            camera: cameraSwitch.checked, screen: screenSwitch.checked,
            cameraSource: cameraSource.currentIndex === 1 ? "phone" : "computer",
            cameraConsent: cameraConsent.checked, screenConsent: screenConsent.checked,
            cameraId: devices.length ? devices[cameras.currentIndex < 0 ? 0 : cameras.currentIndex].id : "",
            blockedKeywords: keywords.text, sound: sound.checked,
            view: small.checked ? "compact" : "full"
        }), duration.value, goal.text)
    }
    Component.onCompleted: { refreshSetup(); refresh() }
    Connections {
        target: Backend.supervision
        function onChanged() { page.refresh() }
        function onSetupChanged() { page.refreshSetup() }
    }

    Text { Layout.fillWidth: true; text: I18n.t("给这一段学习多一点陪伴。检测在本机进行，画面不上传、不录像，也不消耗 AI API。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
    Frame {
        visible: !page.state.active && (!page.available.camera || !page.available.screen)
        Layout.fillWidth: true; padding: 20
        contentItem: ColumnLayout {
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: I18n.t("识别组件还没有准备好"); font.bold: true; wrapMode: Text.Wrap }
                JourneyButton { text: page.showRepair ? I18n.t("收起说明") : I18n.t("查看修复方法"); onClicked: page.showRepair = !page.showRepair }
            }
            Text { Layout.fillWidth: true; text: I18n.t("依赖需要安装在实际启动软件的环境中；装在另一个 Python 里不会生效。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            Text { visible: page.showRepair; Layout.fillWidth: true; text: I18n.t("当前环境：Python ") + (page.available.pythonVersion || "") + "\n" + (page.available.interpreter || ""); wrapMode: Text.WrapAnywhere; font.pixelSize: 12 }
            Text { visible: page.showRepair; Layout.fillWidth: true; text: page.available.repairHint || ""; wrapMode: Text.Wrap; font.pixelSize: 12 }
            JourneyField { visible: page.showRepair && Boolean(page.available.repairCommand); Layout.fillWidth: true; readOnly: true; selectByMouse: true; text: page.available.repairCommand || "" }
        }
    }
    Frame {
        visible: Boolean(page.state.active)
        Layout.fillWidth: true; padding: 22
        contentItem: ColumnLayout {
            spacing: 12
            Text { text: I18n.t("监督模式正在运行"); font.bold: true }
            Text { Layout.fillWidth: true; text: I18n.t("可以切换窗口大小；关闭监督后，已有专注计时会继续。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                JourneyButton { text: I18n.t("停止监督"); onClicked: Backend.stopSupervision() }
                JourneyButton { text: I18n.t("小窗"); onClicked: Backend.presentSupervision("compact") }
                JourneyButton { text: I18n.t("返回全屏"); highlighted: true; onClicked: Backend.presentSupervision("full") }
            }
        }
    }
    Frame {
        visible: !page.state.active
        Layout.fillWidth: true; padding: 24
        contentItem: ColumnLayout {
            spacing: 18
            Text { text: I18n.t("这次准备做什么？"); font.pixelSize: 20; font.weight: Font.Medium }
            JourneyField { id: goal; objectName: "supervisionGoal"; Layout.fillWidth: true; placeholderText: I18n.t("例如：写完物理卷子的选择题"); maximumLength: 200 }
            RowLayout {
                Layout.fillWidth: true
                Text { text: I18n.t("学习方式") }
                Item { Layout.fillWidth: true }
                JourneyCombo { id: mode; objectName: "supervisionMode"; Layout.preferredWidth: 220; model: [I18n.t("纸笔作业"), I18n.t("写代码／电脑工作"), I18n.t("阅读／网课"), I18n.t("用手机学习")]; currentIndex: Math.max(0, ["homework", "code", "reading", "phone"].indexOf(page.preferences.mode || "homework")) }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: I18n.t("专注时长") }
                Item { Layout.fillWidth: true }
                SpinBox { id: duration; from: 1; to: 180; value: 25; editable: true }
                Text { text: I18n.t("分钟") }
            }
            Text { Layout.fillWidth: true; text: I18n.t("已有专注正在进行时，会接入当前计时，不另开一轮。"); font.pixelSize: 12; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
    Frame {
        visible: !page.state.active
        Layout.fillWidth: true; padding: 24
        contentItem: ColumnLayout {
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 5
                    Text { text: I18n.t("摄像头巡查"); font.bold: true }
                    Text { Layout.fillWidth: true; text: I18n.t("识别人、肩膀与手臂；持续离开或疑似持手机时提醒。"); wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.currentTheme.colors.textSecondaryColor }
                }
                Switch { id: cameraSwitch; objectName: "supervisionCamera"; checked: Boolean(page.available.camera) && (cameraSource.currentIndex === 1 || page.devices.length > 0) && Boolean(page.preferences.camera); enabled: Boolean(page.available.camera) && (cameraSource.currentIndex === 1 || page.devices.length > 0); text: !enabled ? I18n.t("不可用") : checked ? I18n.t("开启") : I18n.t("关闭") }
            }
            Text { visible: !page.available.camera || (cameraSource.currentIndex === 0 && !page.devices.length); Layout.fillWidth: true; text: !page.available.camera ? (page.available.cameraReason || I18n.t("正在检查摄像头组件…")) : I18n.t("未发现电脑摄像头，可以改用手机镜头。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            RowLayout {
                Layout.fillWidth: true
                Text { text: I18n.t("镜头来源") }
                Item { Layout.fillWidth: true }
                JourneyCombo { id: cameraSource; objectName: "supervisionCameraSource"; Layout.preferredWidth: 220; model: [I18n.t("电脑摄像头"), I18n.t("手机 · 拍桌面与手部")]; currentIndex: page.preferences.cameraSource === "phone" ? 1 : 0 }
            }
            JourneyCombo { id: cameras; visible: cameraSwitch.checked && cameraSource.currentIndex === 0; Layout.fillWidth: true; model: page.devices.map(function(d) { return d.name }); currentIndex: Math.max(0, page.devices.findIndex(function(d) { return d.id === page.preferences.cameraId })) }
            ColumnLayout {
                visible: cameraSource.currentIndex === 1
                Layout.fillWidth: true; spacing: 12
                Text { Layout.fillWidth: true; text: I18n.t("手机和电脑连同一 Wi-Fi。把手机放在桌面侧上方，让手和作业纸入镜；在手机浏览器允许摄像头。开始监督后才传送画面。"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
                RowLayout {
                    Layout.fillWidth: true
                    JourneyCombo { id: phoneAddress; Layout.fillWidth: true; model: page.phoneInterfaces.length ? page.phoneInterfaces.map(function(row, index) { return row.label + (index === 0 && row.rank < 10 ? I18n.t("（推荐）") : "") }) : [I18n.t("尚未连接局域网")]; currentIndex: 0 }
                    JourneyButton { objectName: "pairPhoneCamera"; text: page.phoneState.phase === "starting" ? I18n.t("正在准备…") : page.phoneState.url ? I18n.t("重新配对") : I18n.t("生成连接二维码"); enabled: Boolean(page.available.camera) && page.phoneAddresses.length > 0 && page.phoneState.phase !== "starting"; onClicked: { page.showPhoneCheck = false; cameraSwitch.checked = true; Backend.supervision.phoneCamera.pair(page.phoneAddresses[phoneAddress.currentIndex]) } }
                    JourneyButton { visible: Boolean(page.phoneState.url); text: I18n.t("断开"); onClicked: Backend.supervision.phoneCamera.close() }
                }
                RowLayout {
                    visible: Boolean(page.phoneState.url); Layout.fillWidth: true; spacing: 18
                    Rectangle { Layout.preferredWidth: 180; Layout.preferredHeight: 180; color: "white"; radius: 12; Image { anchors.fill: parent; anchors.margins: 8; source: page.showPhoneCheck ? page.phoneState.checkQr || "" : page.phoneState.qr || ""; fillMode: Image.PreserveAspectFit } }
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 10
                        Text { text: page.showPhoneCheck ? I18n.t("连通检查二维码 · 不开启镜头") : page.phoneState.phase === "connected" || page.phoneState.phase === "streaming" ? I18n.t("手机已连接") : I18n.t("摄像头连接二维码"); font.bold: true }
                        Text { Layout.fillWidth: true; text: page.showPhoneCheck ? I18n.t("先扫码检查。检查页打不开：核对 Wi-Fi 地址与防火墙；能打开但摄像头页打不开：核对 HTTPS 端口与本地证书。") : I18n.t("使用安卓 Edge 等系统浏览器扫码。首次连接使用本地 HTTPS 证书；网页白屏或一直加载时，切换到下方连通检查。"); wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.currentTheme.colors.textSecondaryColor }
                        JourneyField { Layout.fillWidth: true; readOnly: true; selectByMouse: true; text: (page.showPhoneCheck ? page.phoneState.checkUrl : page.phoneState.url) || "" }
                        Text { Layout.fillWidth: true; text: I18n.t("证书指纹：") + (page.phoneState.fingerprint || ""); wrapMode: Text.WrapAnywhere; font.pixelSize: 10; color: Theme.currentTheme.colors.textSecondaryColor }
                    }
                }
                Text { visible: Boolean(page.phoneState.url); Layout.fillWidth: true; text: page.phoneState.phase === "connected" || page.phoneState.phase === "streaming" ? I18n.t("手机已通过配对验证。") : page.phoneState.httpsSeen ? I18n.t("电脑已收到 HTTPS 页面请求；若手机仍加载，请刷新或重新扫码。") : page.phoneState.networkSeen ? I18n.t("连通检查已到达电脑。若摄像头页面打不开，请查看检查页的证书说明。") : I18n.t("尚未收到手机访问。请选实际 Wi-Fi 地址，不要选 VMware／VPN 虚拟网卡。"); wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.currentTheme.colors.textSecondaryColor }
                RowLayout {
                    visible: Boolean(page.phoneState.url); Layout.fillWidth: true
                    JourneyButton { text: page.showPhoneCheck ? I18n.t("切回摄像头连接") : I18n.t("网页打不开？检查连接"); onClicked: page.showPhoneCheck = !page.showPhoneCheck }
                    Item { Layout.fillWidth: true }
                    JourneyButton { text: I18n.t("允许本次局域网连接…"); onClicked: Backend.supervision.phoneCamera.allowNetwork() }
                }
                Text { visible: Boolean(page.phoneState.url); Layout.fillWidth: true; text: I18n.t("连接放行会请求 Windows 管理员确认：只允许本程序当前两个端口被同一局域网访问；如存在本程序的公用网络阻止规则，会解除该阻止。不会关闭防火墙或更改网络类型。"); wrapMode: Text.Wrap; font.pixelSize: 11; color: Theme.currentTheme.colors.textSecondaryColor }
                Text { visible: Boolean(page.phoneState.error); Layout.fillWidth: true; text: page.phoneState.error || ""; wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            }
            CheckBox { id: cameraConsent; objectName: "supervisionCameraConsent"; visible: cameraSwitch.checked; text: cameraSource.currentIndex === 1 ? I18n.t("本次允许分析手机传来的画面，仅在专注进行时检测") : I18n.t("本次允许读取摄像头，仅在专注进行时检测") }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.currentTheme.colors.controlBorderColor }
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 5
                    Text { text: I18n.t("屏幕巡查"); font.bold: true }
                    Text { Layout.fillWidth: true; text: I18n.t("读取当前窗口，并在本机识别可见文字。关键词只能提示疑似偏离。"); wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.currentTheme.colors.textSecondaryColor }
                }
                Switch { id: screenSwitch; objectName: "supervisionScreen"; checked: Boolean(page.available.screen) && page.preferences.screen !== false; enabled: Boolean(page.available.screen); text: !page.available.screen ? I18n.t("不可用") : checked ? I18n.t("开启") : I18n.t("关闭") }
            }
            Text { visible: !page.available.screen; Layout.fillWidth: true; text: page.available.screenReason || I18n.t("正在检查屏幕识别组件…"); wrapMode: Text.Wrap; color: Theme.currentTheme.colors.textSecondaryColor }
            CheckBox { id: screenConsent; objectName: "supervisionScreenConsent"; visible: screenSwitch.checked; text: I18n.t("本次允许读取前台窗口名称与画面，仅在本机处理") }
            Text { visible: screenSwitch.checked; text: I18n.t("提醒关键词（逗号分隔，可留空）"); font.pixelSize: 12 }
            JourneyField { id: keywords; visible: screenSwitch.checked; Layout.fillWidth: true; maximumLength: 600; text: page.preferences.blockedKeywords === undefined ? "抖音,快手,微博热搜,王者荣耀,原神,英雄联盟,steam" : page.preferences.blockedKeywords; placeholderText: I18n.t("只填写你希望被提醒的内容") }
            Text { Layout.fillWidth: true; text: I18n.t("检测无法判断你是否真正理解了题目或代码；低头、思考和桌上的手机不会直接判为分心。"); wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.currentTheme.colors.textSecondaryColor }
        }
    }
    Frame {
        visible: !page.state.active
        Layout.fillWidth: true; padding: 24
        contentItem: ColumnLayout {
            spacing: 16
            RowLayout {
                Layout.fillWidth: true
                Text { text: I18n.t("提醒强度") }
                Item { Layout.fillWidth: true }
                JourneyCombo { id: strength; Layout.preferredWidth: 220; model: [I18n.t("宽松 · 留更多余地"), I18n.t("适中 · 连续异常才提醒"), I18n.t("严格 · 更快提醒")]; currentIndex: Math.max(0, ["gentle", "normal", "strict"].indexOf(page.preferences.sensitivity || "normal")) }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: I18n.t("提醒音效") }
                Item { Layout.fillWidth: true }
                Switch { id: sound; checked: page.preferences.sound !== false; text: checked ? I18n.t("开启") : I18n.t("关闭") }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: I18n.t("以小窗开始") }
                Item { Layout.fillWidth: true }
                Switch { id: small; checked: !cameraSwitch.checked || mode.currentIndex === 1; text: checked ? I18n.t("小窗") : I18n.t("全屏") }
            }
            Text { Layout.fillWidth: true; text: I18n.t("纸笔学习可用全屏；电脑学习建议小窗，让学习窗口保持在前台。"); wrapMode: Text.Wrap; font.pixelSize: 12; color: Theme.currentTheme.colors.textSecondaryColor }
            JourneyButton {
                objectName: "startSupervision"; Layout.fillWidth: true; implicitHeight: 44
                text: I18n.t("开始监督"); highlighted: true
                enabled: (cameraSwitch.checked || screenSwitch.checked) && (!cameraSwitch.checked || (page.available.camera && cameraConsent.checked && (cameraSource.currentIndex === 0 || Boolean(page.phoneState.url)))) && (!screenSwitch.checked || (page.available.screen && screenConsent.checked))
                onClicked: page.start()
            }
        }
    }
}
