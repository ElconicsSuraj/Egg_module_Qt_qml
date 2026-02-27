import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    visible: true
    width: 1280
    height: 720
    color: "#0b3d1f"
    title: "Egg Module Dashboard"

    //-----------------------------------------
    // BACKGROUND GRADIENT
    //-----------------------------------------
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#0f5a2c" }
            GradientStop { position: 1; color: "#062a15" }
        }
    }

    //-----------------------------------------
    // HEADER
    //-----------------------------------------
    Row {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 30
        spacing: 20

        Text {
            text: "Egg Module Dashboard"
            color: "white"
            font.pixelSize: 40
            font.bold: true
        }

        Item { Layout.fillWidth: true }

        Rectangle {
            width: 280
            height: 50
            radius: 10
            color: "black"

            Text {
                anchors.centerIn: parent
                text: Qt.formatDateTime(new Date(), "dd MMM yyyy - hh:mm AP")
                color: "white"
            }
        }
    }

    //-----------------------------------------
    // MAIN CONTENT
    //-----------------------------------------
    Column {
        anchors.top: parent.top
        anchors.topMargin: 120
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 30

        //-----------------------------------------
        // CAMERA + TRAY
        //-----------------------------------------
        Row {
            spacing: 40

            // Camera View
            Rectangle {
                width: 500
                height: 280
                radius: 20
                color: "#1e1e1e"

                Image {
                    anchors.fill: parent
                    source: "assets/camera.jpg"
                    fillMode: Image.PreserveAspectCrop
                }

                Rectangle {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: 10
                    width: 80
                    height: 30
                    radius: 15
                    color: "red"

                    Text {
                        anchors.centerIn: parent
                        text: "LIVE"
                        color: "white"
                        font.bold: true
                    }
                }
            }

            // Egg Tray Image
            Rectangle {
                width: 400
                height: 280
                radius: 20
                color: "#1e1e1e"

                Image {
                    anchors.fill: parent
                    source: "assets/eggs.png"
                    fillMode: Image.PreserveAspectFit
                }
            }
        }

        //-----------------------------------------
        // METRIC CARDS
        //-----------------------------------------
        Row {
            spacing: 30

            MetricCard { title: "Length"; value: "85"; color1:"#0097a7"; color2:"#004d40" }
            MetricCard { title: "Breadth"; value: "70"; color1:"#ff9800"; color2:"#e65100" }
            MetricCard { title: "Confidence"; value: "95%"; color1:"#8e24aa"; color2:"#4a148c" }
            MetricCard { title: "Weight"; value: "68"; color1:"#f44336"; color2:"#b71c1c" }
        }

        //-----------------------------------------
        // TARE BUTTON
        //-----------------------------------------
        Rectangle {
            width: 300
            height: 70
            radius: 35

            gradient: Gradient {
                GradientStop { position: 0; color: "#ffd54f" }
                GradientStop { position: 1; color: "#f9a825" }
            }

            Text {
                anchors.centerIn: parent
                text: "Tare Eggs"
                font.pixelSize: 26
                font.bold: true
            }

            MouseArea {
                anchors.fill: parent
                onClicked: console.log("Tare clicked")
            }
        }
    }

    //-----------------------------------------
    // REUSABLE METRIC CARD COMPONENT
    //-----------------------------------------
    component MetricCard : Rectangle {
        property string title: ""
        property string value: ""
        property color color1: "blue"
        property color color2: "black"

        width: 250
        height: 150
        radius: 20

        gradient: Gradient {
            GradientStop { position: 0; color: color1 }
            GradientStop { position: 1; color: color2 }
        }

        Column {
            anchors.centerIn: parent
            spacing: 10

            Text {
                text: title
                color: "white"
                font.pixelSize: 20
            }

            Text {
                text: value
                color: "white"
                font.pixelSize: 48
                font.bold: true
            }
        }
    }
}