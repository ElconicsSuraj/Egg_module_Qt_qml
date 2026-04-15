QT += core gui quick qml multimedia quickcontrols2
HEADERS += backend.h
QT += core gui quick qml multimedia quickcontrols2 widgets
CONFIG += c++17

TARGET = egg_module_design
TEMPLATE = app

SOURCES += \
    main.cpp

RESOURCES += qml.qrc

# Additional import path used to resolve QML modules
QML_IMPORT_PATH =
QML_DESIGNER_IMPORT_PATH =

# Deployment rules
qnx: target.path = /tmp/$${TARGET}/bin
else: unix:!android: target.path = /opt/$${TARGET}/bin

!isEmpty(target.path): INSTALLS += target
