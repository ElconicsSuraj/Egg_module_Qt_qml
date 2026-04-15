import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Rectangle {
    id: root
    width: 600
    height: 350
    color: "#1e1e1e"
    radius: 15
    border.color: "#333"
    border.width: 1

    signal keyClicked(string key)
    signal backspaceClicked()
    signal enterClicked()

    property bool isShifted: false
    property bool isSymbols: false

    property var row1: isSymbols ? ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")"] : ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
    property var row2: isSymbols ? ["-", "_", "=", "+", "[", "]", "{", "}", "\\", "|"] : ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"]
    property var row3: isSymbols ? [";", ":", "'", "\"", ",", ".", "<", ">", "/", "?"] : ["A", "S", "D", "F", "G", "H", "J", "K", "L"]
    property var row4: ["Z", "X", "C", "V", "B", "N", "M"]

    function handleKey(key) {
        if (isSymbols) {
            keyClicked(key)
        } else {
            keyClicked(isShifted ? key.toUpperCase() : key.toLowerCase())
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // Row 1
        RowLayout {
            spacing: 5
            Repeater {
                model: root.row1
                delegate: KeyButton { text: modelData; onClicked: root.handleKey(text) }
            }
        }

        // Row 2
        RowLayout {
            spacing: 5
            Repeater {
                model: root.row2
                delegate: KeyButton { text: modelData; onClicked: root.handleKey(text) }
            }
        }

        // Row 3
        RowLayout {
            spacing: 5
            Layout.leftMargin: 20
            Repeater {
                model: root.row3
                delegate: KeyButton { text: modelData; onClicked: root.handleKey(text) }
            }
        }

        // Row 4
        RowLayout {
            spacing: 5
            KeyButton { 
                text: "⇧"
                width: 70
                color: root.isShifted ? "#4fc3f7" : "#333"
                onClicked: root.isShifted = !root.isShifted
                visible: !root.isSymbols
            }
            Repeater {
                model: root.row4
                delegate: KeyButton { text: modelData; onClicked: root.handleKey(text) }
            }
            KeyButton { 
                text: "⌫"
                width: 70
                color: "#b71c1c"
                onClicked: root.backspaceClicked()
            }
        }

        // Row 5
        RowLayout {
            spacing: 5
            KeyButton { 
                text: root.isSymbols ? "ABC" : "?123"
                width: 100
                onClicked: root.isSymbols = !root.isSymbols
            }
            KeyButton { 
                text: "Space"
                Layout.fillWidth: true
                onClicked: root.keyClicked(" ")
            }
            KeyButton { 
                text: "ENTER"
                width: 120
                color: "#4caf50"
                onClicked: root.enterClicked()
            }
        }
    }

    // Sub-component for buttons
    component KeyButton: Rectangle {
        property string text: ""
        signal clicked()
        
        Layout.preferredWidth: 50
        Layout.preferredHeight: 55
        radius: 8
        color: "#333"
        border.color: "#444"
        
        Text {
            anchors.centerIn: parent
            text: parent.text === "Space" ? "" : (root.isShifted || root.isSymbols ? parent.text : parent.text.toLowerCase())
            color: "white"
            font.pixelSize: 18
            font.bold: true
        }

        MouseArea {
            anchors.fill: parent
            onClicked: parent.clicked()
            onPressed: parent.color = "#444"
            onReleased: parent.color = "#333"
        }
    }
}
