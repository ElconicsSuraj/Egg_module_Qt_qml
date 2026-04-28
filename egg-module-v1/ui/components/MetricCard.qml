import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    property string title: ""
    property string value: ""
    property color color1: "#333"
    property color color2: "#111"
    
    property real scaleFactor: 1.0
    
    radius: 20 * scaleFactor
    Layout.preferredHeight: 120 * scaleFactor
    gradient: Gradient {
        GradientStop { position: 0; color: color1 }
        GradientStop { position: 1; color: color2 }
    }
    
    Column {
        anchors.centerIn: parent
        spacing: 6 * scaleFactor
        Text { text: title; color: "white"; font.pixelSize: 16 * scaleFactor }
        Text { text: value; color: "white"; font.pixelSize: 30 * scaleFactor; font.bold: true }
    }
}
