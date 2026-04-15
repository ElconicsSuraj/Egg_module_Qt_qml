import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

ApplicationWindow {
    id: root
    visible: true
    width: 1920
    height:1080
    title: "Egg Module Dashboard"
    required property var antzBackend
    property string currentTime: Qt.formatDateTime(new Date(), "dd MMM yyyy - hh:mm:ss AP")
    property string theme: "dark"
    property bool isLight: theme === "light"
    property color pageBg1: isLight ? "#f2f2f2" : "#0f5a2c"
    property color pageBg2: isLight ? "#dcdcdc" : "#062a15"
    property color primaryPanel: isLight ? "#ffffff" : "#121212"
    property color secondaryPanel: isLight ? "#f5f5f5" : "#1b1b1b"
    property color panelBorder: isLight ? "#d3d3d3" : "#333"
    property color textPrimary: isLight ? "#111111" : "#ffffff"
    property color textSecondary: isLight ? "#4d4d4d" : "#cccccc"
    property color accent: isLight ? "#00695c" : "#4fc3f7"
    property color danger: isLight ? "#c62828" : "#ff5252"
    property color success: isLight ? "#2e7d32" : "#69f0ae"
    property color buttonBg: isLight ? "#eeeeee" : "#333333"
    property color buttonText: isLight ? "#111111" : "#ffffff"
    property color panelBg: isLight ? "#ffffff" : "#111111"
    property color panelAccent: isLight ? "#00796b" : "#4fc3f7"
    property string themeLabel: theme === "dark" ? "Light Mode" : "Dark Mode"


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
            GradientStop { position: 0; color: root.pageBg1 }
            GradientStop { position: 1; color: root.pageBg2 }
        }
    }

    //-----------------------------------------
    // MAIN CONTAINER
    //-----------------------------------------

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 30
        spacing: 25

        //-----------------------------------------
        // SMART USER GUIDE HEADER
        //-----------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 80
            spacing: 20

            // Corporate Logo
            Rectangle {
                width: 70
                height: 70
                radius: 12
                color: "black"
                clip: true
                
                Image {
                    anchors.fill: parent
                    anchors.margins: 5
                    source: "ai_engine/media/AntzLogo.png"
                    fillMode: Image.PreserveAspectFit
                }
            }

            // Dynamic Instruction Column
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: "USER GUIDE"
                    color: root.accent
                    font.pixelSize: 14
                    font.bold: true
                    font.letterSpacing: 2
                }

                Item {
                    Layout.fillWidth: true
                    height: 40
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
                        if (!antzBackend.cameraConnected) return root.danger;
                        if (!antzBackend.isEggDetected) return root.accent;
                        if (!antzBackend.isCentered)    return root.accent;
                        if (antzBackend.isSettled)      return root.success;
                        return root.textPrimary;
                    }
                    font.pixelSize: 22
                    font.bold: true
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                    
                    Behavior on color { ColorAnimation { duration: 300 } }
                }
                }
            }

            // Clock (Live)
            Rectangle {
                width: 240
                height: 50
                radius: 10
                color: root.buttonBg
                border.color: root.panelBorder
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: root.currentTime
                    color: root.buttonText
                    font.pixelSize: 16
                }
            }

            // Theme Toggle Icon
            Rectangle {
                width: 50
                height: 50
                radius: 25
                color: themeMouseArea.containsMouse ? root.buttonBg : "transparent"
                border.color: themeMouseArea.containsMouse ? root.panelBorder : "transparent"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: root.theme === "dark" ? "\u2600" : "\uD83C\uDF19" // Sun for dark mode (to switch to light), Moon for light mode
                    font.pixelSize: 24
                    color: root.textPrimary
                }

                MouseArea {
                    id: themeMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: root.theme = root.theme === "dark" ? "light" : "dark"
                }
            }

            // Internet Connectivity Icon
            Rectangle {
                width: 50
                height: 50
                radius: 25
                color: wifiMouseArea.containsMouse ? root.buttonBg : "transparent"
                border.color: wifiMouseArea.containsMouse ? root.panelBorder : "transparent"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: antzBackend.wifiStatus === "Connected" ? "\uD83D\uDCF6" : 
                          (antzBackend.wifiStatus === "Idle" || antzBackend.wifiStatus === "Scanning") ? "\uD83D\uDEDC" : "\u26A0\uFE0F"
                    font.pixelSize: 22
                    color: antzBackend.wifiStatus === "Connected" ? root.success : root.textPrimary
                    opacity: antzBackend.wifiStatus === "Connected" ? 1.0 : 0.5
                }

                MouseArea {
                    id: wifiMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        wifiSettingsOverlay.visible = true
                        antzBackend.scanWifi()
                    }
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
                color: root.secondaryPanel
                border.color: root.panelBorder
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
            spacing: 20

            MetricCard {
                Layout.fillWidth: true
                title: "Length"
                value: antzBackend.length
                color1: "#0097a7"
                color2: "#004d40"
            }

            MetricCard {
                Layout.fillWidth: true
                title: "Width"
                value: antzBackend.breadth
                color1: "#ff9800"
                color2: "#e65100"
            }

            MetricCard {
                Layout.fillWidth: true
                title: "Confidence"
                value: antzBackend.confidence
                color1: "#8e24aa"
                color2: "#4a148c"
            }

            MetricCard {
                Layout.fillWidth: true
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
            spacing: 30
            
            // Tare Button
            Rectangle {
                width: 200
                height: 60
                radius: 30
                gradient: Gradient {
                    GradientStop { position: 0; color: "#ffd54f" }
                    GradientStop { position: 1; color: "#f9a825" }
                }
                Text {
                    anchors.centerIn: parent
                    text: "Tare"
                    font.pixelSize: 22
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
                width: 200
                height: 60
                radius: 30
                gradient: Gradient {
                    GradientStop { position: 0; color: "#4fc3f7" }
                    GradientStop { position: 1; color: "#0288d1" }
                }
                Text {
                    anchors.centerIn: parent
                    text: "Calibration"
                    font.pixelSize: 22
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
            anchors.margins: 40
            width: 480
            height: 750
            radius: 30
            color: root.secondaryPanel
            border.color: root.panelBorder
            border.width: 2

            MouseArea { anchors.fill: parent }

            // CLOSE BUTTON (Top Right)
            IconButton {
                z: 100
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 15
                iconSource: "assets/close.png"
                onClicked: { calibrationWizard.visible = false; calibrationWizard.step = -1 }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 35
                spacing: 20

                RowLayout {
                    Layout.fillWidth: true
                    Text { 
                        text: "Calibration Setup"
                        color: "#4fc3f7"; font.pixelSize: 24; font.bold: true 
                    }
                }

                    // STEP -1: SET TARGET COUNT
                    ColumnLayout {
                        visible: calibrationWizard.step === -1
                        spacing: 20
                        Layout.fillWidth: true
                        
                        Text { text: "How many eggs will you measure?"; color: "white"; font.pixelSize: 20; Layout.alignment: Qt.AlignHCenter }
                        Text { text: "Warning: This session will replace your current library."; color: "#ff5252"; font.pixelSize: 14; Layout.alignment: Qt.AlignHCenter }
                        
                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: 15
                            Repeater {
                                model: [1, 3, 5, 10]
                                delegate: Rectangle {
                                    width: 80; height: 80; radius: 40
                                    color: calibrationWizard.tempTargetCount === modelData.toString() ? "#4fc3f7" : "#333"
                                    Text { 
                                        anchors.centerIn: parent
                                        text: modelData; color: parent.color === "#333" ? "white" : "black"
                                        font.bold: true; font.pixelSize: 24 
                                    }
                                    MouseArea { 
                                        anchors.fill: parent
                                        onClicked: calibrationWizard.tempTargetCount = modelData.toString()
                                    }
                                }
                            }
                        }
                        Item { Layout.preferredHeight: 40 }
                        Text {
                            text: "Select how many eggs you want to capture in this session."
                            color: "#888"; font.pixelSize: 14; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true
                        }
                    }

                    // STEP 0: INPUT
                    ColumnLayout {
                        visible: calibrationWizard.step === 0
                        Layout.fillWidth: true
                        spacing: 15
                        
                        Text { 
                            text: "Egg " + (antzBackend.calSessionCount + 1) + " of " + antzBackend.calSessionTarget
                            color: "#4fc3f7"; font.pixelSize: 18; font.bold: true; Layout.alignment: Qt.AlignHCenter
                        }

                        ColumnLayout {
                            spacing: 15
                            Layout.alignment: Qt.AlignHCenter
                            Column {
                                Layout.alignment: Qt.AlignHCenter
                                Text { text: "Length (mm)"; color: "#888"; font.pixelSize: 14; anchors.horizontalCenter: parent.horizontalCenter }
                                Rectangle {
                                    width: 220; height: 65; radius: 10; color: calibrationWizard.field === "length" ? "#333" : "#222"
                                    border.color: calibrationWizard.field === "length" ? "#4fc3f7" : "transparent"
                                    Text { anchors.centerIn: parent; text: calibrationWizard.tempLength || "0"; color: "white"; font.pixelSize: 32; font.bold: true }
                                    MouseArea { anchors.fill: parent; onClicked: calibrationWizard.field = "length" }
                                }
                            }
                            Column {
                                Layout.alignment: Qt.AlignHCenter
                                Text { text: "Width (mm)"; color: "#888"; font.pixelSize: 14; anchors.horizontalCenter: parent.horizontalCenter }
                                Rectangle {
                                    width: 220; height: 65; radius: 10; color: calibrationWizard.field === "width" ? "#333" : "#222"
                                    border.color: calibrationWizard.field === "width" ? "#4fc3f7" : "transparent"
                                    Text { anchors.centerIn: parent; text: calibrationWizard.tempWidth || "0"; color: "white"; font.pixelSize: 32; font.bold: true }
                                    MouseArea { anchors.fill: parent; onClicked: calibrationWizard.field = "width" }
                                }
                            }
                        }

                        NumericKeypad {
                            id: numPad
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
                        spacing: 25
                        Text { text: "Step 2: Size Verification"; color: "#ffd54f"; font.pixelSize: 20 }
                        Text {
                            text: calibrationWizard.validationMsg
                            color: "white"; font.pixelSize: 18; wrapMode: Text.WordWrap; Layout.fillWidth: true
                        }
                    }

                    // STEP 2: CAPTURE
                    ColumnLayout {
                        visible: calibrationWizard.step === 2
                        spacing: 30
                        Text { text: "Step 3: Measuring..."; color: "#4fc3f7"; font.pixelSize: 20 }
                        Text { text: antzBackend.calStatus; color: "white"; font.pixelSize: 24; font.bold: true; Layout.alignment: Qt.AlignHCenter }
                        Rectangle {
                            Layout.fillWidth: true; height: 25; radius: 12; color: "#222"
                            Rectangle {
                                width: (parent.width * antzBackend.calibrationProgress) / 100
                                height: parent.height; radius: 12; color: "#4fc3f7"
                                Behavior on width { NumberAnimation { duration: 150 } }
                            }
                        }
                    }

                    // STEP 3: EGG SUCCESS
                    ColumnLayout {
                        visible: calibrationWizard.step === 3
                        spacing: 30
                        Text { text: "Capture Successful!"; color: "#69f0ae"; font.pixelSize: 32; font.bold: true; Layout.alignment: Qt.AlignHCenter }
                        Text { text: antzBackend.lastCalResult; color: "white"; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
                        
                        Item { Layout.fillHeight: true }
                        Text {
                            text: antzBackend.calSessionCount < antzBackend.calSessionTarget ? 
                                  "Ready for the next sample." :
                                  "Target count reached. You can complete the session."
                            color: "#888"; font.pixelSize: 14; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true; wrapMode: Text.WordWrap
                        }
                    }

                    // STEP 4: SESSION SUMMARY
                    ColumnLayout {
                        visible: calibrationWizard.step === 4
                        spacing: 30
                        Text { 
                            text: antzBackend.calStatus === "Library Updated" ? "Success!" : "Wait!"
                            color: "#4fc3f7"; font.pixelSize: 32; font.bold: true; Layout.alignment: Qt.AlignHCenter 
                        }
                        Text { 
                            text: calibrationWizard.validationMsg || antzBackend.lastCalResult
                            color: "white"; font.pixelSize: 18; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; Layout.fillWidth: true 
                        }
                    }
                
                Item { Layout.fillHeight: true }
                // SPACER TO PUSH FOOTER DOWN
                Item { Layout.fillHeight: true }

                // UNIVERSAL NAVIGATION FOOTER
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 60
                    spacing: 15
                    visible: calibrationWizard.step !== 2 && (calibrationWizard.step !== -1 || calibrationWizard.tempTargetCount !== "")

                    // BACK BUTTON
                    Rectangle {
                        Layout.preferredWidth: 120
                        Layout.preferredHeight: 50
                        radius: 25; color: "#333"
                        visible: calibrationWizard.step !== -1 && antzBackend.calStatus !== "Library Updated"
                        Text { anchors.centerIn: parent; text: "BACK"; color: "white"; font.bold: true; font.pixelSize: 16 }
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
                        spacing: 15

                        // FINISH NOW (Secondary)
                        Rectangle {
                            Layout.preferredWidth: 150
                            Layout.preferredHeight: 50
                            radius: 25; color: "#444"
                            visible: calibrationWizard.step === 3 && antzBackend.calSessionCount > 0 && antzBackend.calSessionCount < antzBackend.calSessionTarget
                            
                            Text {
                                anchors.centerIn: parent
                                text: "FINISH NOW"
                                color: "white"; font.bold: true; font.pixelSize: 14
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
                            Layout.preferredWidth: 200
                            Layout.preferredHeight: 50
                            radius: 25; color: "#4caf50"
                            
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
                                color: "white"; font.bold: true; font.pixelSize: 16 
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

    //-----------------------------------------
    // WIFI SETTINGS OVERLAY
    //-----------------------------------------
    WifiOverlay {
        id: wifiSettingsOverlay
        antzBackend: root.antzBackend
        anchors.centerIn: parent
        visible: false
        z: 100
        onClosed: visible = false
    }
}

