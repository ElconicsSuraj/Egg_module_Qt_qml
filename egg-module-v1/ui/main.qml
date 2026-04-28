import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia
import "components"

ApplicationWindow {
    id: root
    visible: true
    width: Screen.width
    height: Screen.height
    visibility: Window.FullScreen
    title: "Egg Module Dashboard"
    
    // Responsive Scaling Logic
    property real scaleFactor: Math.min(width / 1920, height / 1080)
    function s(px) { return px * scaleFactor }
    property string currentTime: Qt.formatDateTime(new Date(), "dd MMM yyyy - hh:mm:ss AP")

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: root.currentTime = Qt.formatDateTime(new Date(), "dd MMM yyyy - hh:mm:ss AP")
    }

    //-----------------------------------------
    // BACKGROUND
    //-----------------------------------------
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#0f5a2c" }
            GradientStop { position: 1; color: "#062a15" }
        }
    }

    //-----------------------------------------
    // MAIN CONTAINER
    //-----------------------------------------
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: s(30)
        spacing: s(25)

        //-----------------------------------------
        // SMART USER GUIDE HEADER
        //-----------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: s(80)
            spacing: s(20)

            // Corporate Logo
            Rectangle {
                width: s(70)
                height: s(70)
                radius: s(12)
                color: "black"
                clip: true
                
                Image {
                    anchors.fill: parent
                    anchors.margins: 5
                    source: "assets/AntzLogo.png"
                    fillMode: Image.PreserveAspectFit
                }
            }

            // Dynamic Instruction Column
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: "USER GUIDE"
                    color: "#ffd54f"
                    font.pixelSize: s(14)
                    font.bold: true
                    font.letterSpacing: s(2)
                }

                Item {
                    Layout.fillWidth: true
                    height: s(40)
                    clip: true

                Text {
                    id: guideText
                    anchors.fill: parent
                    text: {
                        if (!antzBackend.cameraConnected) return "Camera Disconnected: Please check appliance connections.";
                        if (!antzBackend.isEggDetected) return "Ready to Measure: Place an egg in the center area.";
                        if (!antzBackend.isCentered)    return "Centering Required: Align the egg with the green guide.";
                        if (!antzBackend.isSettled)     return "Stabilizing: Hold egg still for 2 seconds...";
                        return "Measurement Complete: Data captured and stabilized.";
                    }
                    color: {
                        if (!antzBackend.cameraConnected) return "#ff5252"; // Red
                        if (!antzBackend.isEggDetected) return "#ffd54f"; // Amber
                        if (!antzBackend.isCentered)    return "#ffd54f"; 
                        if (antzBackend.isSettled)      return "#69f0ae"; // Green
                        return "white";
                    }
                    font.pixelSize: s(22)
                    font.bold: true
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                    
                    Behavior on color { ColorAnimation { duration: 300 } }
                }
                }
            }

            // Clock (Live)
            Rectangle {
                width: s(240)
                height: s(50)
                radius: s(10)
                color: "black"

                Text {
                    anchors.centerIn: parent
                    text: root.currentTime
                    color: "white"
                    font.pixelSize: s(16)
                }
            }
        }

        //-----------------------------------------
        // VISION FEED (DYNAMIC AI OVERLAY)
        //-----------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 300

            Rectangle {
                anchors.centerIn: parent
                width: Math.min(parent.width, parent.height * 1.6) // Preserve aspect ratio roughly
                height: width / 1.6
                radius: 20
                clip: true
                color: "#000"
                border.color: "#1a1a1a"
                border.width: 2

                Image {
                    id: visionStream
                    anchors.fill: parent
                    fillMode: Image.PreserveAspectFit
                    cache: false
                    asynchronous: false // Local image provider is fast, disabling async reduces flickering
                    source: "image://vision/feed"
                    
                    property int frameCounter: 0

                    Connections {
                        target: antzBackend
                        function onImageChanged() {
                            visionStream.frameCounter++
                            visionStream.source = "image://vision/feed?id=" + visionStream.frameCounter
                        }
                    }
                }
            }
        }

        //-----------------------------------------
        // METRIC CARDS (DYNAMIC BINDINGS)
        //-----------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: s(20)

            MetricCard {
                Layout.fillWidth: true
                scaleFactor: root.scaleFactor
                title: "Length"
                value: antzBackend.length
                color1: "#0097a7"
                color2: "#004d40"
            }

            MetricCard {
                Layout.fillWidth: true
                scaleFactor: root.scaleFactor
                title: "Width"
                value: antzBackend.breadth
                color1: "#ff9800"
                color2: "#e65100"
            }

            MetricCard {
                Layout.fillWidth: true
                scaleFactor: root.scaleFactor
                title: "Confidence"
                value: antzBackend.confidence
                color1: "#8e24aa"
                color2: "#4a148c"
            }

            MetricCard {
                Layout.fillWidth: true
                scaleFactor: root.scaleFactor
                title: "Weight"
                value: antzBackend.weight.toFixed(1) + " g"
                color1: "#f44336"
                color2: "#b71c1c"
            }
        }

        //-----------------------------------------
        // ACTION BUTTONS
        //-----------------------------------------
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: s(30)
            
            // Tare Button
            Rectangle {
                width: s(200)
                height: s(60)
                radius: s(30)
                gradient: Gradient {
                    GradientStop { position: 0; color: "#ffd54f" }
                    GradientStop { position: 1; color: "#f9a825" }
                }
                Text {
                    anchors.centerIn: parent
                    text: "Tare"
                    font.pixelSize: s(22)
                    font.bold: true
                    color: "black"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: antzBackend.tareScale()
                }
            }

            // Calibrate Button
            Rectangle {
                width: s(200)
                height: s(60)
                radius: s(30)
                gradient: Gradient {
                    GradientStop { position: 0; color: "#4fc3f7" }
                    GradientStop { position: 1; color: "#0288d1" }
                }
                Text {
                    anchors.centerIn: parent
                    text: "Calibration"
                    font.pixelSize: s(22)
                    font.bold: true
                    color: "white"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: calibrationWizard.open()
                }
            }
        }
    }

    //-----------------------------------------
    // CALIBRATION WIZARD OVERLAY
    //-----------------------------------------
    Rectangle {
        id: calibrationWizard
        anchors.fill: parent
        color: "transparent"
        visible: false
        z: 100

        property int step: -1
        property string field: "length"
        property string tempLength: ""
        property string tempWidth: ""
        property string tempTargetCount: "1"
        property string validationMsg: ""

        function open() {
            step = -1
            field = "length"
            tempLength = ""
            tempWidth = ""
            tempTargetCount = "1"
            validationMsg = ""
            visible = true
        }

        // --- AUTOMATIC TRANSITIONS ---
        Connections {
            target: antzBackend
            function onUpdateMetrics() {
                if (calibrationWizard.step === 2) {
                    if (antzBackend.calStatus === "Capture Complete") {
                        calibrationWizard.step = 3
                    } else if (antzBackend.calStatus === "Capture Error") {
                        calibrationWizard.step = 4
                    }
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            enabled: calibrationWizard.step !== 2
            onClicked: calibrationWizard.visible = false
        }

        Rectangle {
            id: wizardBox
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: s(40)
            width: s(480)
            height: s(750)
            radius: s(30)
            color: "#1a1a1a"
            border.color: "#333"
            border.width: s(2)
            
            MouseArea { anchors.fill: parent }

            // CLOSE BUTTON (Top Right)
            IconButton { 
                z: 100
                scaleFactor: root.scaleFactor
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: s(15)
                iconSource: "assets/close.png"
                onClicked: { calibrationWizard.visible = false; calibrationWizard.step = -1 }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: s(35)
                spacing: s(20)

                RowLayout {
                    Layout.fillWidth: true
                    Text { 
                        text: "Calibration Setup"
                        color: "#4fc3f7"; font.pixelSize: s(24); font.bold: true 
                    }
                }

                    // STEP -1: SET TARGET COUNT
                    ColumnLayout {
                        visible: calibrationWizard.step === -1
                        spacing: s(20)
                        Layout.fillWidth: true
                        
                        Text { text: "How many eggs will you measure?"; color: "white"; font.pixelSize: s(20); Layout.alignment: Qt.AlignHCenter }
                        Text { text: "Warning: This session will replace your current library."; color: "#ff5252"; font.pixelSize: s(14); Layout.alignment: Qt.AlignHCenter }
                        
                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: s(15)
                            Repeater {
                                model: [1, 3, 5, 10]
                                delegate: Rectangle {
                                    width: s(80); height: s(80); radius: s(40)
                                    color: calibrationWizard.tempTargetCount === modelData.toString() ? "#4fc3f7" : "#333"
                                    Text { 
                                        anchors.centerIn: parent
                                        text: modelData; color: parent.color === "#333" ? "white" : "black"
                                        font.bold: true; font.pixelSize: s(24) 
                                    }
                                    MouseArea { 
                                        anchors.fill: parent
                                        onClicked: calibrationWizard.tempTargetCount = modelData.toString()
                                    }
                                }
                            }
                        }
                        Item { Layout.preferredHeight: s(40) }
                        Text {
                            text: "Select how many eggs you want to capture in this session."
                            color: "#888"; font.pixelSize: s(14); horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true
                        }
                    }

                    // STEP 0: INPUT
                    ColumnLayout {
                        visible: calibrationWizard.step === 0
                        Layout.fillWidth: true
                        spacing: s(15)
                        
                        Text { 
                            text: "Egg " + (antzBackend.calSessionCount + 1) + " of " + antzBackend.calSessionTarget
                            color: "#4fc3f7"; font.pixelSize: s(18); font.bold: true; Layout.alignment: Qt.AlignHCenter
                        }

                        ColumnLayout {
                            spacing: s(15)
                            Layout.alignment: Qt.AlignHCenter
                            Column {
                                Layout.alignment: Qt.AlignHCenter
                                Text { text: "Length (mm)"; color: "#888"; font.pixelSize: s(14); anchors.horizontalCenter: parent.horizontalCenter }
                                Rectangle {
                                    width: s(220); height: s(65); radius: s(10); color: calibrationWizard.field === "length" ? "#333" : "#222"
                                    border.color: calibrationWizard.field === "length" ? "#4fc3f7" : "transparent"
                                    Text { anchors.centerIn: parent; text: calibrationWizard.tempLength || "0"; color: "white"; font.pixelSize: s(32); font.bold: true }
                                    MouseArea { anchors.fill: parent; onClicked: calibrationWizard.field = "length" }
                                }
                            }
                            Column {
                                Layout.alignment: Qt.AlignHCenter
                                Text { text: "Width (mm)"; color: "#888"; font.pixelSize: s(14); anchors.horizontalCenter: parent.horizontalCenter }
                                Rectangle {
                                    width: s(220); height: s(65); radius: s(10); color: calibrationWizard.field === "width" ? "#333" : "#222"
                                    border.color: calibrationWizard.field === "width" ? "#4fc3f7" : "transparent"
                                    Text { anchors.centerIn: parent; text: calibrationWizard.tempWidth || "0"; color: "white"; font.pixelSize: s(32); font.bold: true }
                                    MouseArea { anchors.fill: parent; onClicked: calibrationWizard.field = "width" }
                                }
                            }
                        }

                        NumericKeypad {
                            id: numPad
                            scaleFactor: root.scaleFactor
                            Layout.alignment: Qt.AlignHCenter
                            onDigitClicked: (digit) => {
                                if (calibrationWizard.field === "length") {
                                    if (calibrationWizard.tempLength.length < 5) calibrationWizard.tempLength += digit
                                } else {
                                    if (calibrationWizard.tempWidth.length < 5) calibrationWizard.tempWidth += digit
                                }
                            }
                            onBackspaceClicked: () => {
                                if (calibrationWizard.field === "length") {
                                    calibrationWizard.tempLength = calibrationWizard.tempLength.slice(0, -1)
                                } else {
                                    calibrationWizard.tempWidth = calibrationWizard.tempWidth.slice(0, -1)
                                }
                            }
                            onEnterClicked: () => {
                                if (calibrationWizard.field === "length") {
                                    calibrationWizard.field = "width"
                                } else if (parseFloat(calibrationWizard.tempLength) > 0 && parseFloat(calibrationWizard.tempWidth) > 0) {
                                    let res = antzBackend.validateCalibration(parseFloat(calibrationWizard.tempLength), parseFloat(calibrationWizard.tempWidth))
                                    if (res === "OK") {
                                        calibrationWizard.step = 2
                                        antzBackend.startAutoCalibration(parseFloat(calibrationWizard.tempLength), parseFloat(calibrationWizard.tempWidth))
                                    } else {
                                        calibrationWizard.validationMsg = res
                                        calibrationWizard.step = 1
                                    }
                                }
                            }
                        }
                    }

                    // STEP 1: VALIDATION
                    ColumnLayout {
                        visible: calibrationWizard.step === 1
                        spacing: s(25)
                        Text { text: "Step 2: Size Verification"; color: "#ffd54f"; font.pixelSize: s(20) }
                        Text {
                            text: calibrationWizard.validationMsg
                            color: "white"; font.pixelSize: s(18); wrapMode: Text.WordWrap; Layout.fillWidth: true
                        }
                    }

                    // STEP 2: CAPTURE
                    ColumnLayout {
                        visible: calibrationWizard.step === 2
                        spacing: s(30)
                        Text { text: "Step 3: Measuring..."; color: "#4fc3f7"; font.pixelSize: s(20) }
                        Text { text: antzBackend.calStatus; color: "white"; font.pixelSize: s(24); font.bold: true; Layout.alignment: Qt.AlignHCenter }
                        Rectangle {
                            Layout.fillWidth: true; height: s(25); radius: s(12); color: "#222"
                            Rectangle {
                                width: (parent.width * antzBackend.calibrationProgress) / 100
                                height: parent.height; radius: s(12); color: "#4fc3f7"
                                Behavior on width { NumberAnimation { duration: 150 } }
                            }
                        }
                    }

                    // STEP 3: EGG SUCCESS
                    ColumnLayout {
                        visible: calibrationWizard.step === 3
                        spacing: s(30)
                        Text { text: "Capture Successful!"; color: "#69f0ae"; font.pixelSize: s(32); font.bold: true; Layout.alignment: Qt.AlignHCenter }
                        Text { text: antzBackend.lastCalResult; color: "white"; font.pixelSize: s(16); horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
                        
                        Item { Layout.fillHeight: true }
                        Text {
                            text: antzBackend.calSessionCount < antzBackend.calSessionTarget ? 
                                  "Ready for the next sample." :
                                  "Target count reached. You can complete the session."
                            color: "#888"; font.pixelSize: s(14); horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true; wrapMode: Text.WordWrap
                        }
                    }

                    // STEP 4: SESSION SUMMARY
                    ColumnLayout {
                        visible: calibrationWizard.step === 4
                        spacing: s(30)
                        Text { 
                            text: antzBackend.calStatus === "Library Updated" ? "Success!" : "Wait!"
                            color: "#4fc3f7"; font.pixelSize: s(32); font.bold: true; Layout.alignment: Qt.AlignHCenter 
                        }
                        Text { 
                            text: calibrationWizard.validationMsg || antzBackend.lastCalResult
                            color: "white"; font.pixelSize: s(18); horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; Layout.fillWidth: true 
                        }
                    }
                
                Item { Layout.fillHeight: true }
                // SPACER TO PUSH FOOTER DOWN
                Item { Layout.fillHeight: true }

                // UNIVERSAL NAVIGATION FOOTER
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: s(60)
                    spacing: s(15)
                    visible: calibrationWizard.step !== 2 && (calibrationWizard.step !== -1 || calibrationWizard.tempTargetCount !== "")

                    // BACK BUTTON
                    Rectangle {
                        Layout.preferredWidth: s(120)
                        Layout.preferredHeight: s(50)
                        radius: s(25); color: "#333"
                        visible: calibrationWizard.step !== -1 && antzBackend.calStatus !== "Library Updated"
                        Text { anchors.centerIn: parent; text: "BACK"; color: "white"; font.bold: true; font.pixelSize: s(16) }
                        MouseArea { 
                            anchors.fill: parent
                            onClicked: {
                                if (calibrationWizard.step === 0) calibrationWizard.step = -1
                                else if (calibrationWizard.step === 1) calibrationWizard.step = 0
                                else if (calibrationWizard.step === 3) {
                                    calibrationWizard.tempLength = ""; calibrationWizard.tempWidth = ""; 
                                    calibrationWizard.field = "length"; calibrationWizard.step = 0
                                }
                                else if (calibrationWizard.step === 4) calibrationWizard.step = 3
                            }
                        }
                    }

                    // MAIN ACTIONS (Right Aligned or Centered)
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignRight
                        spacing: s(15)

                        // FINISH NOW (Secondary)
                        Rectangle {
                            Layout.preferredWidth: s(150)
                            Layout.preferredHeight: s(50)
                            radius: s(25); color: "#444"
                            visible: calibrationWizard.step === 3 && antzBackend.calSessionCount > 0 && antzBackend.calSessionCount < antzBackend.calSessionTarget
                            
                            Text {
                                anchors.centerIn: parent
                                text: "FINISH NOW"
                                color: "white"; font.bold: true; font.pixelSize: s(14)
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    let res = antzBackend.checkSessionProgress()
                                    if (res === "OK") { antzBackend.saveSession(); calibrationWizard.step = 4 }
                                    else { calibrationWizard.validationMsg = res; calibrationWizard.step = 4 }
                                }
                            }
                        }

                        // NEXT / START (Primary)
                        Rectangle {
                            Layout.preferredWidth: s(200)
                            Layout.preferredHeight: s(50)
                            radius: s(25); color: "#4caf50"
                            
                            Text { 
                                id: mainActionText
                                anchors.centerIn: parent
                                text: {
                                    if (calibrationWizard.step === -1) return "START SESSION"
                                    if (calibrationWizard.step === 0) return "START"
                                    if (calibrationWizard.step === 1) return "CONTINUE"
                                    if (calibrationWizard.step === 3) return antzBackend.calSessionCount >= antzBackend.calSessionTarget ? "FINISH SESSION" : "NEXT EGG"
                                    if (calibrationWizard.step === 4) return antzBackend.calStatus === "Library Updated" ? "CLOSE" : "CONFIRM"
                                    return "NEXT"
                                }
                                color: "white"; font.bold: true; font.pixelSize: s(16) 
                            }
                            
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    if (calibrationWizard.step === -1) {
                                        antzBackend.startNewSession(parseInt(calibrationWizard.tempTargetCount))
                                        calibrationWizard.step = 0
                                    }
                                    else if (calibrationWizard.step === 0) {
                                        if (parseFloat(calibrationWizard.tempLength) > 0 && parseFloat(calibrationWizard.tempWidth) > 0) {
                                            let res = antzBackend.validateCalibration(parseFloat(calibrationWizard.tempLength), parseFloat(calibrationWizard.tempWidth))
                                            if (res === "OK") {
                                                antzBackend.startAutoCalibration(parseFloat(calibrationWizard.tempLength), parseFloat(calibrationWizard.tempWidth))
                                                calibrationWizard.step = 2
                                            } else {
                                                calibrationWizard.validationMsg = res
                                                calibrationWizard.step = 1
                                            }
                                        }
                                    }
                                    else if (calibrationWizard.step === 1) {
                                        antzBackend.startAutoCalibration(parseFloat(calibrationWizard.tempLength), parseFloat(calibrationWizard.tempWidth))
                                        calibrationWizard.step = 2
                                    }
                                    else if (calibrationWizard.step === 3) {
                                        if (antzBackend.calSessionCount >= antzBackend.calSessionTarget) {
                                            let res = antzBackend.checkSessionProgress()
                                            if (res === "OK") { antzBackend.saveSession(); calibrationWizard.step = 4 }
                                            else { calibrationWizard.validationMsg = res; calibrationWizard.step = 4 }
                                        } else {
                                            calibrationWizard.tempLength = ""; calibrationWizard.tempWidth = ""; calibrationWizard.field = "length"; calibrationWizard.step = 0
                                        }
                                    }
                                    else if (calibrationWizard.step === 4) {
                                        if (antzBackend.calStatus === "Library Updated") {
                                            calibrationWizard.visible = false; calibrationWizard.step = -1
                                        } else {
                                            antzBackend.saveSession(); calibrationWizard.step = 4
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                
                Item { Layout.fillHeight: true }
            }
        }
    }
}