import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    visible: true
    width: 1280
    height: 720
    title: "Egg Module Dashboard"
    color: "black"

    //-------------------------------------------------
    // SCALE CONTAINER (Maintains 16:9 Ratio)
    //-------------------------------------------------
    Item {
        id: scaledRoot
        width: 1280
        height: 720

        anchors.centerIn: parent

        scale: Math.min(parent.width / 1280,
                        parent.height / 720)

        //-------------------------------------------------
        // BACKGROUND
        //-------------------------------------------------
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: "#0f5a2c" }
                GradientStop { position: 1; color: "#062a15" }
            }
        }

        //-------------------------------------------------
        // HEADER
        //-------------------------------------------------
        Item {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 100
            anchors.margins: 30

            Text {
                text: "Egg Module Dashboard"
                color: "white"
                font.pixelSize: 38
                font.bold: true
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
            }

            Rectangle {
                width: 300
                height: 50
                radius: 10
                color: "black"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter

                Text {
                    id: dateTimeText
                    anchors.centerIn: parent
                    color: "white"
                    font.pixelSize: 16
                    text: Qt.formatDateTime(new Date(),
                                             "dd MMM yyyy - hh:mm:ss AP")
                }
            }
        }

        //-------------------------------------------------
        // LIVE CLOCK
        //-------------------------------------------------
        Timer {
            interval: 1000
            running: true
            repeat: true
            onTriggered: {
                dateTimeText.text =
                        Qt.formatDateTime(new Date(),
                                          "dd MMM yyyy - hh:mm:ss AP")
            }
        }

        //-------------------------------------------------
        // MAIN CONTENT (Below Header)
        //-------------------------------------------------
        Column {
            anchors.top: parent.top
            anchors.topMargin: 140
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 40

            //-------------------------------------------------
            // CAMERA VIEW
            //-------------------------------------------------
            Rectangle {
                width: 600
                height: 300
                radius: 20
                clip: true
                color: "#000000"

                Image {
                    anchors.fill: parent
                    source: "qrc:/assets/camera.jpg"
                    fillMode: Image.PreserveAspectCrop
                }

                Rectangle {
                    width: 80
                    height: 35
                    radius: 18
                    color: "red"
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: 15

                    Text {
                        anchors.centerIn: parent
                        text: "LIVE"
                        color: "white"
                        font.bold: true
                    }
                }
            }

            //-------------------------------------------------
            // METRIC CARDS
            //-------------------------------------------------
            Row {
                spacing: 30
                anchors.horizontalCenter: parent.horizontalCenter

                MetricCard { title: "Length"; value: "80 mm"; color1:"#0097a7"; color2:"#004d40" }
                MetricCard { title: "Breadth"; value: "75 mm"; color1:"#ff9800"; color2:"#e65100" }
                MetricCard { title: "Confidence"; value: "96%"; color1:"#8e24aa"; color2:"#4a148c" }
                MetricCard { title: "Weight"; value: "68 g"; color1:"#f44336"; color2:"#b71c1c" }
            }

            //-------------------------------------------------
            // TARE BUTTON
            //-------------------------------------------------
            Rectangle {
                width: 280
                height: 70
                radius: 35
                anchors.horizontalCenter: parent.horizontalCenter

                gradient: Gradient {
                    GradientStop { position: 0; color: "#ffd54f" }
                    GradientStop { position: 1; color: "#f9a825" }
                }

                Text {
                    anchors.centerIn: parent
                    text: "Tare Eggs"
                    font.pixelSize: 24
                    font.bold: true
                    color: "black"
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: console.log("Tare Clicked")
                }
            }
        }

        //-------------------------------------------------
        // REUSABLE METRIC CARD
        //-------------------------------------------------
        component MetricCard : Rectangle {
            property string title: ""
            property string value: ""
            property color color1: "#333"
            property color color2: "#111"

            width: 220
            height: 140
            radius: 20

            gradient: Gradient {
                GradientStop { position: 0; color: color1 }
                GradientStop { position: 1; color: color2 }
            }

            Column {
                anchors.centerIn: parent
                spacing: 8

                Text {
                    text: title
                    color: "white"
                    font.pixelSize: 18
                }

                Text {
                    text: value
                    color: "white"
                    font.pixelSize: 36
                    font.bold: true
                }
            }
        }
    }
}
