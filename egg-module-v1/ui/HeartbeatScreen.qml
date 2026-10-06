import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    anchors.fill: parent
    color: "transparent"

    property real scaleFactor: 1.0
    function s(px) { return px * scaleFactor }

    signal backClicked()

    // Automatic start monitoring on screen entry
    Component.onCompleted: {
        antzBackend.startHeartbeatScreening()
    }

    // Always stop monitoring and turn LED OFF when leaving screen
    Component.onDestruction: {
        antzBackend.stopHeartbeatScreening()
    }

    // Gradient Background
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#061826" }
            GradientStop { position: 1; color: "#020b12" }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: s(30)
        spacing: s(25)

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
                    GradientStop { position: 0; color: "#37474f" }
                    GradientStop { position: 1; color: "#263238" }
                }
                border.color: "#546e7a"
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
                    onClicked: {
                        antzBackend.stopHeartbeatScreening()
                        root.backClicked()
                    }
                }
            }

            // Screen Title Column
            ColumnLayout {
                Layout.fillWidth: true
                spacing: s(2)

                Text {
                    text: "EGG VITALITY MONITORING"
                    color: "#80deea"
                    font.pixelSize: s(14)
                    font.bold: true
                    font.letterSpacing: s(2)
                }

                Text {
                    text: "Heartbeat Screening"
                    color: "#00e5ff"
                    font.pixelSize: s(28)
                    font.bold: true
                }
            }

            // Live Signal Status Pill
            Rectangle {
                width: s(220)
                height: s(50)
                radius: s(25)
                color: antzBackend.heartbeatActive ? "#00363a" : "#263238"
                border.color: antzBackend.heartbeatActive ? "#00e5ff" : "#546e7a"
                border.width: s(2)

                RowLayout {
                    anchors.centerIn: parent
                    spacing: s(10)

                    Rectangle {
                        width: s(14)
                        height: s(14)
                        radius: s(7)
                        color: {
                            if (!antzBackend.heartbeatActive) return "#78909c"
                            if (antzBackend.heartbeatSignalStatus === "STRONG") return "#00e676"
                            if (antzBackend.heartbeatSignalStatus === "WEAK") return "#ffd54f"
                            return "#ff5252"
                        }

                        SequentialAnimation on opacity {
                            running: antzBackend.heartbeatActive
                            loops: Animation.Infinite
                            PropertyAnimation { to: 0.3; duration: 600 }
                            PropertyAnimation { to: 1.0; duration: 600 }
                        }
                    }

                    Text {
                        text: antzBackend.heartbeatActive ? antzBackend.heartbeatSignalStatus : "OFFLINE"
                        color: "white"
                        font.pixelSize: s(16)
                        font.bold: true
                    }
                }
            }
        }

        //-----------------------------------------
        // MAIN DISPLAY CONTENT
        //-----------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: s(25)

            // LEFT PANEL: ANIMATED HEART & EKG WAVEFORM VISUALIZER
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: s(24)
                color: "#0a2236"
                border.color: "#1c3b57"
                border.width: s(2)
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: s(25)
                    spacing: s(20)

                    // TOP PULSE HEART ANIMATION AREA
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: s(180)

                        // Pulsing background radial aura
                        Rectangle {
                            anchors.centerIn: parent
                            width: s(160)
                            height: s(160)
                            radius: s(80)
                            color: antzBackend.heartbeatPulseDetected ? "#40ff1744" : "#1000e5ff"

                            Behavior on color { ColorAnimation { duration: 100 } }
                            scale: antzBackend.heartbeatPulseDetected ? 1.25 : 1.0
                            Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                        }

                        // Heart Icon
                        Text {
                            anchors.centerIn: parent
                            text: "💓"
                            font.pixelSize: s(90)
                            scale: antzBackend.heartbeatPulseDetected ? 1.3 : 1.0
                            Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutBack } }
                        }
                    }

                    // HEARTBEAT STATUS TEXT
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: antzBackend.heartbeatStatus
                        color: {
                            if (antzBackend.heartbeatStatus === "Heartbeat Detected") return "#69f0ae"
                            if (antzBackend.heartbeatStatus === "Detecting Signal...") return "#ffd54f"
                            return "#ff5252"
                        }
                        font.pixelSize: s(24)
                        font.bold: true
                    }

                    // REAL-TIME EKG PULSE WAVEFORM CANVAS
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: s(16)
                        color: "#03101c"
                        border.color: "#0f2d47"
                        border.width: s(1)
                        clip: true

                        Canvas {
                            id: waveformCanvas
                            anchors.fill: parent

                            property var points: []
                            property int maxPoints: 120

                            Connections {
                                target: antzBackend
                                function onHeartbeatChanged() {
                                    var sig = antzBackend.heartbeatRawSignal
                                    waveformCanvas.points.push(sig)
                                    if (waveformCanvas.points.length > waveformCanvas.maxPoints) {
                                        waveformCanvas.points.shift()
                                    }
                                    waveformCanvas.requestPaint()
                                }
                            }

                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)

                                // Draw Grid
                                ctx.strokeStyle = "#0d2b45"
                                ctx.lineWidth = 1
                                for (var x = 0; x < width; x += 30) {
                                    ctx.beginPath()
                                    ctx.moveTo(x, 0)
                                    ctx.lineTo(x, height)
                                    ctx.stroke()
                                }
                                for (var y = 0; y < height; y += 30) {
                                    ctx.beginPath()
                                    ctx.moveTo(0, y)
                                    ctx.lineTo(width, y)
                                    ctx.stroke()
                                }

                                if (points.length < 2) return

                                // Draw EKG Signal Curve
                                ctx.beginPath()
                                ctx.strokeStyle = antzBackend.heartbeatPulseDetected ? "#ff1744" : "#00e5ff"
                                ctx.lineWidth = 3

                                var step = width / (maxPoints - 1)
                                var minSig = 150, maxSig = 800
                                var range = maxSig - minSig

                                for (var i = 0; i < points.length; i++) {
                                    var px = i * step
                                    var norm = (points[i] - minSig) / range
                                    norm = Math.max(0, Math.min(1, norm))
                                    var py = height - (norm * (height - 40) + 20)

                                    if (i === 0) ctx.moveTo(px, py)
                                    else ctx.lineTo(px, py)
                                }
                                ctx.stroke()
                            }
                        }
                    }
                }
            }

            // RIGHT PANEL: METRICS, LED INDICATOR & GPIO CONFIGURATION
            Rectangle {
                Layout.preferredWidth: s(480)
                Layout.fillHeight: true
                radius: s(24)
                color: "#0a2236"
                border.color: "#1c3b57"
                border.width: s(2)

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: s(25)
                    spacing: s(20)

                    // BPM METRIC CARD
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: s(150)
                        radius: s(20)
                        gradient: Gradient {
                            GradientStop { position: 0; color: "#006064" }
                            GradientStop { position: 1; color: "#00363a" }
                        }
                        border.color: "#00e5ff"
                        border.width: s(2)

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: s(6)

                            Text {
                                text: "CALCULATED HEART RATE"
                                color: "#80deea"
                                font.pixelSize: s(14)
                                font.bold: true
                                font.letterSpacing: s(1.5)
                                Layout.alignment: Qt.AlignHCenter
                            }

                            Text {
                                text: antzBackend.heartbeatBpm > 0 ? antzBackend.heartbeatBpm.toFixed(0) + " BPM" : "-- BPM"
                                color: "white"
                                font.pixelSize: s(46)
                                font.bold: true
                                Layout.alignment: Qt.AlignHCenter
                            }

                            Text {
                                text: "Egg Embryonic Pulse Rate"
                                color: "#e0f7fa"
                                font.pixelSize: s(13)
                                Layout.alignment: Qt.AlignHCenter
                            }
                        }
                    }

                    // LED INDICATOR CARD
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: s(110)
                        radius: s(18)
                        color: "#0f2d47"
                        border.color: antzBackend.heartbeatPulseDetected ? "#ff1744" : "#1c3b57"
                        border.width: s(2)

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: s(20)
                            spacing: s(15)

                            // Glowing Hardware LED Indicator
                            Rectangle {
                                width: s(46)
                                height: s(46)
                                radius: s(23)
                                color: antzBackend.heartbeatPulseDetected ? "#ff1744" : "#263238"
                                border.color: antzBackend.heartbeatPulseDetected ? "#ff8a80" : "#455a64"
                                border.width: s(3)

                                Text {
                                    anchors.centerIn: parent
                                    text: "💡"
                                    font.pixelSize: s(22)
                                    opacity: antzBackend.heartbeatPulseDetected ? 1.0 : 0.4
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: s(2)

                                Text {
                                    text: "HEARTBEAT INDICATOR LED"
                                    color: "#80deea"
                                    font.pixelSize: s(13)
                                    font.bold: true
                                }

                                Text {
                                    text: antzBackend.heartbeatPulseDetected ? "PULSE TRIGGERED (ON)" : "STANDBY (OFF)"
                                    color: antzBackend.heartbeatPulseDetected ? "#ff8a80" : "#90a4ae"
                                    font.pixelSize: s(16)
                                    font.bold: true
                                }
                            }
                        }
                    }

                    // GPIO CONFIGURATION LOCATION PANEL
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: s(130)
                        radius: s(18)
                        color: "#0a1929"
                        border.color: "#132f4c"
                        border.width: s(1)

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: s(18)
                            spacing: s(10)

                            Text {
                                text: "HARDWARE & GPIO PINOUT"
                                color: "#ffd54f"
                                font.pixelSize: s(13)
                                font.bold: true
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: "Pulse Sensor Signal:"; color: "#90a4ae"; font.pixelSize: s(14) }
                                Item { Layout.fillWidth: true }
                                Text { text: "Raspberry Pi GPIO " + antzBackend.heartbeatSensorPin; color: "#00e5ff"; font.pixelSize: s(14); font.bold: true }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: "Heartbeat LED Output:"; color: "#90a4ae"; font.pixelSize: s(14) }
                                Item { Layout.fillWidth: true }
                                Text { text: "Raspberry Pi GPIO " + antzBackend.heartbeatLedPin; color: "#ff8a80"; font.pixelSize: s(14); font.bold: true }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // START / STOP SCREENING CONTROLLER BUTTON
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: s(60)
                        radius: s(30)
                        gradient: Gradient {
                            GradientStop {
                                position: 0
                                color: antzBackend.heartbeatActive ? "#d32f2f" : "#00c853"
                            }
                            GradientStop {
                                position: 1
                                color: antzBackend.heartbeatActive ? "#b71c1c" : "#008ba3"
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            text: antzBackend.heartbeatActive ? "STOP MONITORING" : "START MONITORING"
                            color: "white"
                            font.pixelSize: s(20)
                            font.bold: true
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                if (antzBackend.heartbeatActive) {
                                    antzBackend.stopHeartbeatScreening()
                                } else {
                                    antzBackend.startHeartbeatScreening()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
