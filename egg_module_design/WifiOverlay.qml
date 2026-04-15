import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    width: 650
    height: 700
    color: "#121212"
    radius: 25
    border.color: "#333"
    border.width: 2
    clip: true

    property string selectedSsid: ""
    property string selectedAuthentication: ""
    property string selectedEncryption: ""
    property bool selectedOpenNetwork: false
    property string password: ""
    property int viewIndex: 0 // 0: List, 1: Password
    required property var antzBackend

    signal closed()

    Rectangle {
        id: header
        width: parent.width
        height: 70
        color: "#1a1a1a"

        Text {
            anchors.centerIn: parent
            text: root.viewIndex === 0 ? "Select Wi-Fi Network" : "Connect to " + root.selectedSsid
            color: "#4fc3f7"
            font.pixelSize: 22
            font.bold: true
        }

        IconButton {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.rightMargin: 15
            iconSource: "assets/close.png"
            onClicked: root.closed()
        }
    }

    Item {
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        width: parent.width

        ColumnLayout {
            visible: root.viewIndex === 0
            anchors.fill: parent
            anchors.margins: 20
            spacing: 15

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "Available Networks"
                    color: "white"
                    font.pixelSize: 16
                    opacity: 0.7
                }
                Item { Layout.fillWidth: true }
                Button {
                    text: antzBackend.wifiStatus === "Scanning" ? "Scanning..." : "Refresh"
                    enabled: antzBackend.wifiStatus !== "Scanning"
                    onClicked: antzBackend.scanWifi()
                }
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: antzBackend.wifiList
                spacing: 10
                clip: true

                delegate: Rectangle {
                    width: parent.width
                    height: 72
                    radius: 12
                    color: itemMa.containsMouse ? "#222" : "#1a1a1a"
                    border.color: (typeof modelData === "object" && modelData.connected) ? "#4caf50" : "#333"
                    border.width: 1

                    property string dSsid: (typeof modelData === "object" && modelData.ssid !== undefined) ? modelData.ssid : modelData
                    property string dAuth: (typeof modelData === "object" && modelData.authentication !== undefined) ? modelData.authentication : "Unknown"
                    property string dEnc: (typeof modelData === "object" && modelData.encryption !== undefined) ? modelData.encryption : "Unknown"
                    property int dSignal: (typeof modelData === "object" && modelData.signal !== undefined) ? modelData.signal : 0
                    property bool dOpen: (typeof modelData === "object" && modelData.openNetwork !== undefined) ? modelData.openNetwork : false
                    property bool dConnected: (typeof modelData === "object" && modelData.connected !== undefined) ? modelData.connected : false

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 12

                        Text {
                            text: dSignal >= 75 ? "Strong" : (dSignal >= 40 ? "Medium" : "Weak")
                            color: "#8ab4f8"
                            font.pixelSize: 12
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: dSsid
                                color: "white"
                                font.pixelSize: 18
                                font.bold: true
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            Text {
                                text: (dOpen ? "Open" : dAuth) + "  |  Signal " + dSignal + "%"
                                color: "#b0b0b0"
                                font.pixelSize: 12
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        Rectangle {
                            visible: dConnected
                            color: "#4caf50"
                            radius: 8
                            implicitWidth: 84
                            implicitHeight: 24

                            Text {
                                anchors.centerIn: parent
                                text: "Connected"
                                color: "white"
                                font.pixelSize: 12
                            }
                        }

                        Text {
                            text: dOpen ? "Open" : "Secured"
                            color: dOpen ? "#81c784" : "#ffcc80"
                            font.pixelSize: 12
                        }
                    }

                    MouseArea {
                        id: itemMa
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            if (!dSsid || dSsid === "")
                                return

                            root.selectedSsid = dSsid
                            root.selectedAuthentication = dAuth
                            root.selectedEncryption = dEnc
                            root.selectedOpenNetwork = dOpen
                            root.password = ""

                            if (dOpen) {
                                antzBackend.connectToWifi(root.selectedSsid, "")
                            } else {
                                root.viewIndex = 1
                            }
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    text: "No networks found.\nClick Refresh to scan."
                    color: "#666"
                    horizontalAlignment: Text.AlignHCenter
                    visible: antzBackend.wifiList.length === 0 && antzBackend.wifiStatus !== "Scanning"
                }

                BusyIndicator {
                    anchors.centerIn: parent
                    running: antzBackend.wifiStatus === "Scanning"
                }
            }
        }

        ColumnLayout {
            visible: root.viewIndex === 1
            anchors.fill: parent
            anchors.margins: 20
            spacing: 20

            Rectangle {
                Layout.fillWidth: true
                height: 60
                color: "#1a1a1a"
                radius: 10
                border.color: "#4fc3f7"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 15

                    Text {
                        text: root.password ? root.password.replace(/./g, "*") : "Enter Password"
                        color: root.password ? "white" : "#555"
                        font.pixelSize: 22
                        Layout.fillWidth: true
                    }

                    Button {
                        text: "Clear"
                        flat: true
                        onClicked: root.password = ""
                        visible: root.password.length > 0
                    }
                }
            }

            Keyboard {
                Layout.fillWidth: true
                Layout.preferredHeight: 350
                onKeyClicked: (key) => root.password += key
                onBackspaceClicked: root.password = root.password.slice(0, -1)
                onEnterClicked: antzBackend.connectToWifi(root.selectedSsid, root.password)
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 20

                Text {
                    text: antzBackend.wifiStatus
                    color: antzBackend.wifiStatus.indexOf("Error") !== -1 ? "#ff5252" : "#69f0ae"
                    font.pixelSize: 16
                    Layout.fillWidth: true
                    visible: antzBackend.wifiStatus !== "Idle" && antzBackend.wifiStatus !== "Scanning"
                }

                Button {
                    text: "Back"
                    onClicked: root.viewIndex = 0
                }

                Rectangle {
                    width: 150
                    height: 50
                    radius: 25
                    color: root.password.length >= 4 ? "#4caf50" : "#333"
                    opacity: root.password.length >= 4 ? 1.0 : 0.5

                    Text {
                        anchors.centerIn: parent
                        text: "Connect"
                        color: "white"
                        font.bold: true
                    }

                    MouseArea {
                        anchors.fill: parent
                        enabled: root.password.length >= 4 && antzBackend.wifiStatus !== "Connecting"
                        onClicked: antzBackend.connectToWifi(root.selectedSsid, root.password)
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }

    Connections {
        target: antzBackend
        function onWifiStatusChanged() {
            if (antzBackend.wifiStatus === "Connected") {
                root.viewIndex = 0
                root.selectedSsid = ""
                root.password = ""
                successTimer.start()
            }
        }
    }

    Timer {
        id: successTimer
        interval: 1000
        onTriggered: root.closed()
    }
}
