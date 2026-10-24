import QtQuick
import "../i18n"
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: panel
    property bool compact: false
    property var hostWindow
    property var state: JSON.parse(Backend.supervision.stateJson)
    property var session: JSON.parse(Backend.focusSessionJson)
    property var studio: JSON.parse(Backend.focusStudioStateJson)
    property bool showCalibration: false
    objectName: "supervisionPanel"
    readonly property var calibration: state.calibration || ({})
    readonly property string postureLabel: calibration.reason === "unstable" ? I18n.t("姿态不稳定") : calibration.reason === "unmatched" ? I18n.t("姿态偏离学习参考") : I18n.t("非学习姿态")
    readonly property var alert: state.alert || ({})
    readonly property color ink: "#e5ece8"
    readonly property color muted: "#9dacaa"
    function clock(v) { var s = Math.max(0, Math.floor(Number(v) || 0)); return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0") }
    function cameraLabel() {
        return ({off:I18n.t("摄像头未开启"), loading:I18n.t("正在加载本地模型…"), ready:I18n.t("调整镜头，让手和作业进入画面"), hands:I18n.t("手部已入镜 · ") + Number(state.handCount || 0) + I18n.t(" 只手"), tracking:I18n.t("看到上半身，但手部没有入镜；只能确认人在镜头前"), partial:I18n.t("看到人，但镜头范围不足，不能判断学习动作"), absent:I18n.t("暂未看到人，持续缺席才提醒"), unknown:I18n.t("画面过暗或不清晰，暂不判断"), deskUnknown:I18n.t("桌面没有清晰手部线索，暂不判断是否离开"), waitingPhone:I18n.t("等待手机画面，请在手机页面开启摄像头"), error:I18n.t("摄像头暂不可用"), paused:I18n.t("暂停／休息中，画面传送与检测已暂停")})[state.cameraStatus] || I18n.t("等待检测")
    }
    component Action: Button {
        property bool primary: false
        implicitHeight: 38
        leftPadding: 15; rightPadding: 15
        background: Rectangle { radius: 10; color: parent.down ? "#456457" : parent.primary ? "#c7dbba" : parent.hovered ? "#32473e" : "#24372f"; border.color: "#3b5146" }
        contentItem: Text { text: parent.text; color: parent.primary ? "#193325" : panel.ink; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
    }
    Rectangle { anchors.fill: parent; color: "#13251f"; radius: panel.compact ? 18 : 0; border.color: panel.compact ? "#425a4c" : "transparent" }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: panel.compact ? 18 : 32
        spacing: panel.compact ? 12 : 24
        RowLayout {
            Layout.fillWidth: true
            Rectangle { width: 8; height: 8; radius: 4; color: panel.state.paused ? "#d3b88a" : "#b5d3a2" }
            Text { text: I18n.t("FlowTodo · 监督模式"); color: panel.ink; font.pixelSize: 14 }
            Item { Layout.fillWidth: true
                MouseArea { anchors.fill: parent; enabled: panel.compact; onPressed: panel.hostWindow.startSystemMove() }
            }
            Action { visible: panel.state.cameraStatus !== "off"; text: I18n.t("姿态校准"); onClicked: panel.showCalibration = !panel.showCalibration }
            Action { objectName: "supervisionResize"; text: panel.compact ? I18n.t("全屏") : I18n.t("小窗"); onClicked: Backend.presentSupervision(panel.compact ? "full" : "compact") }
            Action { text: I18n.t("返回"); onClicked: Backend.stopSupervision() }
        }
        Item { visible: !panel.compact; Layout.fillHeight: true }
        RowLayout {
            Layout.fillWidth: true
            Layout.maximumWidth: 1120
            Layout.alignment: Qt.AlignHCenter
            spacing: 32
            ColumnLayout {
                Layout.fillWidth: true
                spacing: panel.compact ? 6 : 20
                Text { text: panel.state.paused ? I18n.t("先休息，回来接着做") : I18n.t("只照顾好眼前这一段"); color: panel.muted; font.pixelSize: panel.compact ? 12 : 16 }
                Text { objectName: "supervisionClock"; text: panel.clock(panel.session.remaining); color: panel.ink; font.pixelSize: panel.compact ? 48 : 100; font.weight: Font.Light; font.family: "Segoe UI"; font.features: {"tnum": 1} }
                Text { Layout.fillWidth: true; text: String(panel.studio.goal || panel.session.title || I18n.t("做好眼前这一件事")); color: panel.ink; font.pixelSize: panel.compact ? 16 : 24; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight }
                Text { visible: !panel.compact; Layout.fillWidth: true; text: I18n.t("思考和短暂停顿也属于学习。连续异常才提醒，你随时可以纠正判断。"); color: panel.muted; wrapMode: Text.Wrap; font.pixelSize: 14 }
            }
            Rectangle {
                visible: !panel.compact && panel.state.cameraStatus !== "off"
                Layout.preferredWidth: Math.min(460, panel.width * .4)
                Layout.preferredHeight: width * .75
                color: "#0b1813"; radius: 16; clip: true
                Image { id: cameraImage; anchors.fill: parent; source: Backend.supervision.cameraPreview; fillMode: Image.PreserveAspectFit; cache: false; asynchronous: true; retainWhileLoading: true; onStatusChanged: if (status === Image.Ready) skeleton.requestPaint() }
                Canvas {
                    id: skeleton; anchors.fill: cameraImage
                    property var points: panel.state.points || []
                    property var boxes: panel.state.boxes || []
                    onPointsChanged: requestPaint()
                    onBoxesChanged: requestPaint()
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onPaint: {
                        var c = getContext("2d"); c.reset()
                        if (!cameraImage.source.toString().length) return
                        var w = cameraImage.paintedWidth, h = cameraImage.paintedHeight, x = (width - w) / 2, y = (height - h) / 2
                        c.lineWidth = 2; c.strokeStyle = "#c7edb6"; c.fillStyle = "#c7edb6"
                        var indexed = ({})
                        points.forEach(function(p) { indexed[p.index] = p })
                        var connections = [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[3033,3159],[3159,3133],[3133,3145],[3145,3033],[3362,3386],[3386,3263],[3263,3374],[3374,3362]]
                        ;[100,121].forEach(function(base) {
                            ;[[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[0,17],[17,18],[18,19],[19,20]].forEach(function(pair) { connections.push([base+pair[0],base+pair[1]]) })
                        })
                        connections.forEach(function(pair) {
                            var a = indexed[pair[0]], b = indexed[pair[1]]
                            if (a && b) { c.beginPath(); c.moveTo(x + a.x*w, y + a.y*h); c.lineTo(x + b.x*w, y + b.y*h); c.stroke() }
                        })
                        points.forEach(function(p) { c.beginPath(); c.arc(x + p.x*w, y + p.y*h, 3, 0, 2*Math.PI); c.fill() })
                        boxes.forEach(function(b) { c.strokeStyle = b.label === "person" ? "#c7edb6" : "#f4c27e"; c.strokeRect(x+b.x*w,y+b.y*h,b.w*w,b.h*h) })
                    }
                }
                Text { anchors.centerIn: parent; width: parent.width - 40; visible: !cameraImage.source.toString().length; text: panel.cameraLabel(); color: panel.muted; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; font.pixelSize: 14 }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.maximumWidth: 1120
            Layout.alignment: Qt.AlignHCenter
            spacing: 8
            Text { Layout.fillWidth: true; visible: panel.state.cameraStatus !== "off"; text: panel.state.cameraError || panel.cameraLabel(); color: panel.muted; wrapMode: Text.Wrap; maximumLineCount: panel.compact ? 2 : 4; elide: Text.ElideRight; font.pixelSize: 12 }
            Text { Layout.fillWidth: true; visible: !panel.compact && panel.state.cameraStatus !== "off" && !panel.state.paused; text: ({front:I18n.t("眼部辅助：目光大致朝前"), side:I18n.t("眼部辅助：目光可能朝侧边，思考或查资料都很正常"), down:I18n.t("眼部辅助：低头看向下方，写作业时很常见"), unknown:I18n.t("眼部未清晰入镜，不使用眼神判断")})[panel.state.eyeDirection || "unknown"] + I18n.t(" · 这些线索不能证明是否在认真学习"); wrapMode: Text.Wrap; color: panel.muted; font.pixelSize: 12 }
            Text { Layout.fillWidth: true; visible: Boolean(panel.state.heldPhone); text: panel.state.mode === "phone" ? I18n.t("手机学习已允许") : I18n.t("疑似持手机，持续一段时间后才提醒"); color: "#d8c596"; wrapMode: Text.Wrap; font.pixelSize: 12 }
            Text { Layout.fillWidth: true; visible: panel.state.screenStatus !== "off"; text: panel.state.screenError || (panel.state.paused ? I18n.t("屏幕巡查已暂停") : panel.state.screenStatus === "loading" ? I18n.t("正在加载本地文字识别…") : String(panel.state.screenLabel || I18n.t("等待屏幕巡查"))); color: panel.muted; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; font.pixelSize: 12 }
            Text { visible: !panel.compact && String(panel.state.screenTitle || "").length > 0; Layout.fillWidth: true; text: I18n.t("当前窗口 · ") + String(panel.state.screenTitle || ""); color: panel.muted; elide: Text.ElideRight; font.pixelSize: 12 }
            Text { visible: Boolean(panel.calibration.ready); Layout.fillWidth: true; text: I18n.t("个人姿态参考 · ") + (panel.calibration.verdict === "other" ? panel.state.paused ? I18n.t("检测已暂停") : panel.calibration.alarmExempt ? I18n.t("姿态提醒已暂时豁免") : panel.alert.kind === "posture" ? I18n.t("已按非学习状态触发提醒") : panel.postureLabel + I18n.t("，按非学习状态计时 · 剩余 ") + Number(panel.calibration.alarmRemaining === undefined ? 5 : panel.calibration.alarmRemaining) + I18n.t(" 秒报警") : ({learning:I18n.t("更接近你记录的学习姿势"),unknown:I18n.t("姿态线索不足，等待有效画面")})[panel.calibration.verdict || "unknown"]); color: panel.calibration.verdict === "other" ? "#f4c27e" : panel.muted; wrapMode: Text.Wrap; font.pixelSize: 12 }
        }
        Rectangle {
            visible: panel.showCalibration && panel.state.cameraStatus !== "off"
            Layout.fillWidth: true; Layout.maximumWidth: 1120; Layout.alignment: Qt.AlignHCenter
            implicitHeight: calibrationContent.implicitHeight + 28
            radius: 14; color: "#20362b"; border.color: "#425a4c"
            ColumnLayout {
                id: calibrationContent; anchors.fill: parent; anchors.margins: 14; spacing: 10
                Text { text: I18n.t("让监督认识你的习惯"); color: panel.ink; font.bold: true }
                Text { Layout.fillWidth: true; text: panel.calibration.message || I18n.t("先记录学习姿态，再记录非学习姿态"); color: panel.muted; wrapMode: Text.Wrap; font.pixelSize: 12 }
                Text { visible: panel.calibration.phase === "learning" || panel.calibration.phase === "other"; text: I18n.t("有效样本 ") + Number(panel.calibration.count || 0) + " / " + Number(panel.calibration.target || 10); color: panel.ink; font.pixelSize: 12 }
                Flow {
                    Layout.fillWidth: true; spacing: 8
                    Action { text: I18n.t("1 · 记录学习姿态"); enabled: !panel.state.paused && panel.calibration.phase !== "learning" && panel.calibration.phase !== "other"; onClicked: Backend.supervision.calibrate("learning") }
                    Action { text: I18n.t("2 · 记录非学习姿态"); enabled: !panel.state.paused && Boolean(panel.calibration.hasLearning) && panel.calibration.phase !== "learning" && panel.calibration.phase !== "other"; onClicked: Backend.supervision.calibrate("other") }
                    Action { visible: panel.calibration.phase === "learning" || panel.calibration.phase === "other"; text: I18n.t("取消"); onClicked: Backend.supervision.calibrate("cancel") }
                }
                Text { Layout.fillWidth: true; text: I18n.t("只保存本次的姿态特征，不存画面。移动镜头后重做校准；姿势相似时不强行判断。"); color: panel.muted; wrapMode: Text.Wrap; font.pixelSize: 11 }
            }
        }
        Rectangle {
            objectName: "supervisionAlert"
            visible: Boolean(panel.state.alert)
            Layout.fillWidth: true
            Layout.maximumWidth: 1120
            Layout.alignment: Qt.AlignHCenter
            implicitHeight: alertContent.implicitHeight + 28
            radius: 14; color: "#394033"; border.color: "#8b956d"
            ColumnLayout {
                id: alertContent; anchors.fill: parent; anchors.margins: 14; spacing: 10
                Text { Layout.fillWidth: true; text: String(panel.alert.title || ""); color: "#f0e4c6"; font.pixelSize: panel.compact ? 14 : 18; wrapMode: Text.Wrap }
                Text { visible: !panel.compact; Layout.fillWidth: true; text: String(panel.alert.detail || ""); color: "#c4c4ab"; wrapMode: Text.Wrap; font.pixelSize: 12 }
                Flow {
                    Layout.fillWidth: true; spacing: 8
                    Action { text: I18n.t("回到任务"); primary: true; onClicked: Backend.supervision.resolveAlert(String(panel.alert.id), "back") }
                    Action { text: I18n.t("正在查资料"); onClicked: Backend.supervision.resolveAlert(String(panel.alert.id), "allow") }
                    Action { text: I18n.t("误判"); onClicked: Backend.supervision.resolveAlert(String(panel.alert.id), "wrong") }
                    Action { text: I18n.t("休息一下"); onClicked: Backend.supervision.resolveAlert(String(panel.alert.id), "rest") }
                }
            }
        }
        Item { visible: !panel.compact; Layout.fillHeight: true }
        RowLayout {
            Layout.fillWidth: true
            Text { text: I18n.t("已提醒 ") + Number(panel.state.count || 0) + I18n.t(" 次"); color: panel.muted; font.pixelSize: 12 }
            Item { Layout.fillWidth: true }
            Action { visible: Boolean(panel.session.guidedWaiting); text: I18n.t("回到 AI 引导"); primary: true; onClicked: Backend.returnAiFromSupervision() }
            Action { objectName: "supervisionPause"; visible: !panel.session.guidedWaiting; text: panel.state.paused ? I18n.t("继续") : I18n.t("暂停"); primary: true; onClicked: Backend.toggleSupervisionPause() }
            Action { text: I18n.t("结束本轮"); onClicked: Backend.finishSupervision() }
        }
    }
}
