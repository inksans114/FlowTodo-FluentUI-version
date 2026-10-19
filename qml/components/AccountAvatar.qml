import QtQuick
import RinUI
Item {
    id: avatar
    property var account: ({})
    implicitWidth: 24
    implicitHeight: width
    Accessible.role: Accessible.Graphic
    Accessible.name: (account.name || "") + " · 头像"
    Rectangle { anchors.fill: parent; radius: width / 2; color: Qt.alpha(Theme.currentTheme.colors.primaryColor, 0.12); visible: picture.status !== Image.Ready
        Text { anchors.fill: parent; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; lineHeightMode: Text.ProportionalHeight; lineHeight: 1; text: (avatar.account.initials || "FT").slice(0, 1); font.pixelSize: Math.max(10, avatar.width * 0.42); color: Theme.currentTheme.colors.primaryColor }
    }
    Image { id: picture; anchors.fill: parent; source: avatar.account.avatarUrl || ""; asynchronous: true; cache: false; sourceSize.width: 128; sourceSize.height: 128; fillMode: Image.PreserveAspectFit }
}
