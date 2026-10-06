import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

Rectangle {
    id: root
    anchors.fill: parent
    color: "transparent"

    property real scaleFactor: 1.0
    function s(px) { return px * scaleFactor }

    signal backClicked()

    // Background Gradient
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#1c1402" }
            GradientStop { position: 1; color: "#080500" }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: s(30)
        spacing: s(20)

        //-----------------------------------------
        // HEADER BAR WITH BACK BUTTON
        //-----------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: s(80)
            spacing: s(20)

            // Back Button
            Rectangle {
                width: s(140)
                height: s(60)
                radius: s(30)
                gradient: Gradient {
                    GradientStop { position: 0; color: "#423214" }
                    GradientStop { position: 1; color: "#21190a" }
                }
                border.color: "#6e5421"
                border.width: s(2)

                RowLayout {
                    anchors.centerIn: parent
                    spacing: s(8)

                    Text {
                        text: "◀"
                        color: "white"
                        font.pixelSize: s(18)
                    }
                    Text {
                        text: "BACK"
                        color: "white"
                        font.pixelSize: s(18)
                        font.bold: true
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: root.backClicked()
                }
            }

            // Title Column
            ColumnLayout {
                Layout.fillWidth: true
                spacing: s(2)

                Text {
                    text: "OPTICAL INSPECTION & INTERNAL CANDLING"
                    color: "#ffe082"
                    font.pixelSize: s(14)
                    font.bold: true
                    font.letterSpacing: s(2)
                }

                Text {
                    text: "Egg Candling View"
                    color: "#ffb300"
                    font.pixelSize: s(28)
                    font.bold: true
                }
            }

            // Light Status Pill
            Rectangle {
                width: s(220)
                height: s(50)
                radius: s(25)
                color: antzBackend.candlingState ? "#4a3b00" : "#262626"
                border.color: antzBackend.candlingState ? "#ffb300" : "#616161"
                border.width: s(2)

                RowLayout {
                    anchors.centerIn: parent
                    spacing: s(10)

                    Text {
                        text: "💡"
                        font.pixelSize: s(20)
                    }

                    Text {
                        text: antzBackend.candlingState ? "CANDLING LIGHT ON" : "LIGHT OFF"
                        color: antzBackend.candlingState ? "#ffe082" : "#9e9e9e"
                        font.pixelSize: s(16)
                        font.bold: true
                    }
                }
            }
        }

        //-----------------------------------------
        // LIVE CAMERA VIEWPORT (HORIZONTAL LAYOUT)
        //-----------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Rectangle {
                anchors.centerIn: parent
                // Horizontal orientation & aspect ratio preservation (16:9 landscape)
                width: Math.min(parent.width, parent.height * 1.777)
                height: width / 1.777
                radius: s(20)
                clip: true
                color: "#000000"
                border.color: antzBackend.candlingState ? "#ffb300" : "#333333"
                border.width: s(3)

                // Reuses existing connected camera pipeline (image://vision/feed)
                Image {
                    id: candlingStream
                    anchors.fill: parent
                    fillMode: Image.PreserveAspectFit
                    cache: false
                    asynchronous: false
                    source: "image://vision/feed"

                    property int frameCounter: 0

                    Connections {
                        target: antzBackend
                        function onImageChanged() {
                            candlingStream.frameCounter++
                            candlingStream.source = "image://vision/feed?id=" + candlingStream.frameCounter
                        }
                    }
                }

                // Subtitle Overlay Tag
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.margins: s(15)
                    width: s(360)
                    height: s(40)
                    radius: s(20)
                    color: "#cc000000"

                    Text {
                        anchors.centerIn: parent
                        text: "Horizontal Framing • Camera Aspect Ratio Preserved"
                        color: "#ffecb3"
                        font.pixelSize: s(13)
                    }
                }
            }
        }

        //-----------------------------------------
        // CONTROLS & SNAPSHOT METRICS BAR
        //-----------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: s(100)
            spacing: s(20)

            // Candling Light Toggle Button (Touchscreen Large Target)
            Rectangle {
                Layout.preferredWidth: s(300)
                Layout.fillHeight: true
                radius: s(25)
                gradient: Gradient {
                    GradientStop {
                        position: 0
                        color: antzBackend.candlingState ? "#ffe082" : "#424242"
                    }
                    GradientStop {
                        position: 1
                        color: antzBackend.candlingState ? "#ffb300" : "#212121"
                    }
                }
                border.color: antzBackend.candlingState ? "#fff59d" : "#616161"
                border.width: s(3)

                RowLayout {
                    anchors.centerIn: parent
                    spacing: s(12)

                    Text {
                        text: "💡"
                        font.pixelSize: s(32)
                    }

                    Text {
                        text: antzBackend.candlingState ? "TURN LIGHT OFF" : "TOGGLE CANDLING LIGHT"
                        font.pixelSize: s(20)
                        font.bold: true
                        color: antzBackend.candlingState ? "#000000" : "#ffffff"
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: antzBackend.toggleCandling()
                }
            }

            // Quick Snapshot Metric Cards
            MetricCard {
                Layout.fillWidth: true
                scaleFactor: root.scaleFactor
                title: "Horizontal Length"
                value: antzBackend.length
                color1: "#00838f"
                color2: "#004d40"
            }

            MetricCard {
                Layout.fillWidth: true
                scaleFactor: root.scaleFactor
                title: "Horizontal Breadth"
                value: antzBackend.breadth
                color1: "#d84315"
                color2: "#bf360c"
            }
        }
    }
}
