import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    property string title: ""
    property string value: ""
    property color color1: "#333"
    property color color2: "#111"
    
    radius: 20
    Layout.preferredHeight: 120
    gradient: Gradient {
        GradientStop { position: 0; color: color1 }
        GradientStop { position: 1; color: color2 }
    }
    
    Column {
        anchors.centerIn: parent
        spacing: 6
        Text { text: title; color: "white"; font.pixelSize: 16 }
        Text { text: value; color: "white"; font.pixelSize: 30; font.bold: true }
    }
}
