import QtQuick
import "../i18n"
import QtQuick.Layouts
import RinUI
import "../components"
FluentPage {
    id: page; title: I18n.t("会员个性化"); wrapperWidth: 900; horizontalPadding: 32; contentSpacing: 18
    readonly property var entitlement: { Backend.accountJson; try { return JSON.parse(Backend.appearanceJson) } catch(e) { return ({}) } }
    property var draft: ({})
    property string feedback: ""
    property string mode: "light"
    readonly property var fields: [{key:"accent",label:I18n.t("主色与强调控件")},{key:"surface",label:I18n.t("卡片背景")},{key:"control",label:I18n.t("控件背景")},{key:"list",label:I18n.t("任务列表背景")},{key:"ink",label:I18n.t("主要文字")},{key:"muted",label:I18n.t("次要文字")}]
    readonly property var icons: ["ic_fluent_checkmark_circle_20_regular","ic_fluent_sparkle_20_regular","ic_fluent_leaf_one_20_regular","ic_fluent_book_open_20_regular"]
    function load() { draft=JSON.parse(Backend.appearanceJson); feedback="" }
    function change(key,value) { var next=JSON.parse(JSON.stringify(draft)); next[mode][key]=value; draft=next }
    function setValue(key,value) { var next=JSON.parse(JSON.stringify(draft)); next[key]=value; draft=next }
    function apply() { var next=JSON.parse(JSON.stringify(draft)); delete next.active; delete next.eligible; feedback=Backend.saveCustomAppearance(JSON.stringify(next)) ? I18n.t("已保存，主题已应用到软件。") : I18n.t("未保存，请查看配色提示；文字与背景必须清晰可读。") }
    SettingsBack { Layout.alignment: Qt.AlignLeft }
    Component.onCompleted: load()
    StudioTokens { id: ui; customAllowed: false }
    Text { Layout.fillWidth: true; text: I18n.t("Lite 与 Standard 专属。分别保存浅色、深色配色，调整工作区的装饰文字与图标。布局、功能名称、账号权限与核心设置保持固定。"); wrapMode: Text.Wrap; lineHeightMode: Text.ProportionalHeight; color: ui.muted; font.pixelSize: 13 }
    Frame { Layout.fillWidth: true; padding: 20
        background: Rectangle { color: ui.surface; radius: 16; border.color: ui.stroke }
        contentItem: ColumnLayout { spacing: 14
            RowLayout { Layout.fillWidth: true; Text { Layout.fillWidth: true; text: page.entitlement.eligible ? I18n.t("启用我的主题") : I18n.t("升级 Lite / Standard 后解锁"); color: ui.ink; font.pixelSize: 16; font.weight: Font.DemiBold }
                Switch { checked: Boolean(page.draft.enabled); enabled: page.entitlement.eligible; onClicked: page.setValue("enabled",checked) }
            }
            Text { Layout.fillWidth: true; text: I18n.t("退出账号或会员到期后恢复默认外观，保存的主题不会被删除。配色偏好按账户保存在本机。"); wrapMode: Text.Wrap; lineHeightMode: Text.ProportionalHeight; color: ui.muted; font.pixelSize: 12 }
            ComboBox { model: [I18n.t("浅色配色"),I18n.t("深色配色")]; onActivated: page.mode=currentIndex===0?"light":"dark" }
            GridLayout { Layout.fillWidth: true; columns: page.width<740 ? 1 : 2; columnSpacing: 24; rowSpacing: 14
                Repeater { model: page.fields; delegate: RowLayout { required property var modelData; Layout.fillWidth: true; spacing: 12
                    Text { Layout.fillWidth: true; text: modelData.label; color: ui.ink; font.pixelSize: 13 }
                    Rectangle { width: 20; height: 20; radius: 6; color: page.draft[page.mode] ? page.draft[page.mode][modelData.key] : "#ffffff"; border.color: ui.stroke }
                    TextField { Layout.preferredWidth: 104; enabled: page.entitlement.eligible; text: page.draft[page.mode] ? page.draft[page.mode][modelData.key] : ""; placeholderText: "#RRGGBB"; Accessible.name: modelData.label; onEditingFinished: page.change(modelData.key,text.trim()) }
                } }
            }
            Text { text: I18n.t("工作区装饰"); color: ui.ink; font.pixelSize: 15; font.weight: Font.DemiBold }
            TextField { Layout.fillWidth: true; enabled: page.entitlement.eligible; text: page.draft.workspaceName || ""; placeholderText: I18n.t("工作区名称，留空使用「今日任务」"); maximumLength: 24; Accessible.name: I18n.t("工作区名称"); onEditingFinished: page.setValue("workspaceName",text.trim()) }
            ComboBox { enabled: page.entitlement.eligible; model: [I18n.t("行动 · 勾选"),I18n.t("灵感 · 星光"),I18n.t("自然 · 叶片"),I18n.t("学习 · 书本")]; currentIndex: Math.max(0,page.icons.indexOf(page.draft.workspaceIcon)); onActivated: page.setValue("workspaceIcon",page.icons[currentIndex]) }
            Rectangle { Layout.fillWidth: true; implicitHeight: 112; radius: 14; color: page.draft[page.mode] ? page.draft[page.mode].list : "#ffffff"; border.color: ui.stroke
                ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 9
                    RowLayout { Icon { name: page.draft.workspaceIcon || page.icons[0]; size: 22; color: page.draft[page.mode] ? page.draft[page.mode].accent : ui.accent }
                        Text { text: page.draft.workspaceName || I18n.t("今日任务"); color: page.draft[page.mode] ? page.draft[page.mode].ink : ui.ink; font.pixelSize: 19; font.weight: Font.DemiBold }
                    }
                    Text { text: I18n.t("清晰的文字，让每一步都看得见。"); color: page.draft[page.mode] ? page.draft[page.mode].muted : ui.muted; font.pixelSize: 13 }
                }
            }
            RowLayout { Button { text: I18n.t("保存并应用"); highlighted: true; enabled: page.entitlement.eligible; onClicked: page.apply() }
                Button { text: I18n.t("恢复默认"); onClicked: { Backend.resetCustomAppearance();page.load();page.feedback=I18n.t("已恢复默认主题。") } }
            }
            Text { visible: page.feedback.length>0; text: page.feedback; Layout.fillWidth: true; wrapMode: Text.Wrap; lineHeightMode: Text.ProportionalHeight; color: ui.muted; font.pixelSize: 13 }
        }
    }
}
