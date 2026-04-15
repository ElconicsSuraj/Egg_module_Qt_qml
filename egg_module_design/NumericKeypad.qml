import QtQuick 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    width: 300
    height: 380
    signal digitClicked(string digit)
    signal backspaceClicked()
    signal enterClicked()

    focus: true
    Keys.onPressed: (event) => {
        if (event.key >= Qt.Key_0 && event.key <= Qt.Key_9) { digitClicked(event.text) }
        else if (event.key === Qt.Key_Backspace) { backspaceClicked() }
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) { enterClicked() }
        else if (event.key === Qt.Key_Period) { digitClicked(".") }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        GridLayout {
            Layout.fillWidth: true
            columns: 3; columnSpacing: 8; rowSpacing: 8

            Repeater {
                model: ["1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "0", "⇐"]
                delegate: Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 60; radius: 10
                    color: modelData === "⇐" ? "#b71c1c" : "#333"
                    Text { anchors.centerIn: parent; text: modelData; color: "white"; font.pixelSize: 22; font.bold: true }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            if (modelData === "⇐") backspaceClicked()
                            else digitClicked(modelData)
                        }
                    }
                }
            }
        }
        
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 60; radius: 10
            color: "#4fc3f7"
            Text { anchors.centerIn: parent; text: "START"; color: "black"; font.pixelSize: 18; font.bold: true }
            MouseArea { anchors.fill: parent; onClicked: enterClicked() }
        }
    }
}
