import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import RinUI

FluentPage {
    id: errorPage

    property string errorMessage: "ERROR_MSG"
    property string page: "page"

    spacing: 4

    Item {
        height: 64
    }

    Text {
        Layout.alignment: Qt.AlignHCenter
        typography: Typography.Subtitle
        text: qsTr("Sorry, something went wrong!")
    }

    Text {
        Layout.preferredWidth: parent.width * 0.8
        Layout.alignment: Qt.AlignHCenter
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        typography: Typography.Body
        text: page + qsTr(" load failed! \n\n Because of ") + errorMessage + qsTr("\nPlease try again later.")
    }

    Item {
        height: 8
    }


    Button {
        Layout.alignment: Qt.AlignHCenter
        id: retryButton
        text: qsTr("Retry")
        // buttonType: "primary"
        onClicked: {
            // 重新加载 Home 页
            safePush(errorPage.page, true)
        }
    }
}
