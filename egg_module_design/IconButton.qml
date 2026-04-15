import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: root
    property string iconSource: ""
    signal clicked()
    
    width: 40; height: 40; radius: 20; color: "transparent"
    border.color: ma.containsMouse ? "#333" : "transparent"
    
    Image {
        id: iconImg
        anchors.fill: parent; anchors.margins: 8
        source: iconSource; fillMode: Image.PreserveAspectFit
        opacity: ma.containsMouse ? 1.0 : 0.6
        visible: status === Image.Ready
    }

    Text {
        anchors.centerIn: parent
        text: "✕"
        color: "white"
        font.pixelSize: 20
        visible: iconImg.status !== Image.Ready
    }
    
    MouseArea { 
        id: ma; anchors.fill: parent; hoverEnabled: true; 
        z: 10
        onClicked: (mouse) => root.clicked()
    }
}
