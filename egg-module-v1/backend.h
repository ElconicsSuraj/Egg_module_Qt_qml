#ifndef BACKEND_H
#define BACKEND_H

#include <QObject>
#include <QProcess>
#include <QDebug>
#include <QString>

class Backend : public QObject
{
    Q_OBJECT
    Q_PROPERTY(float weight READ weight NOTIFY weightChanged)
    Q_PROPERTY(bool candlingState READ candlingState NOTIFY candlingChanged)
    Q_PROPERTY(bool heartbeatActive READ heartbeatActive NOTIFY heartbeatChanged)
    Q_PROPERTY(float heartbeatBpm READ heartbeatBpm NOTIFY heartbeatChanged)
    Q_PROPERTY(QString heartbeatStatus READ heartbeatStatus NOTIFY heartbeatChanged)
    Q_PROPERTY(QString heartbeatSignalStatus READ heartbeatSignalStatus NOTIFY heartbeatChanged)
    Q_PROPERTY(bool heartbeatPulseDetected READ heartbeatPulseDetected NOTIFY heartbeatChanged)
    Q_PROPERTY(float heartbeatRawSignal READ heartbeatRawSignal NOTIFY heartbeatChanged)
    Q_PROPERTY(int heartbeatSensorPin READ heartbeatSensorPin CONSTANT)
    Q_PROPERTY(int heartbeatLedPin READ heartbeatLedPin CONSTANT)

public:
    explicit Backend(QObject *parent = nullptr) : QObject(parent)
    {
        process = new QProcess(this);

        connect(process, &QProcess::readyReadStandardOutput,
                this, &Backend::readWeight);

        // Run python unbuffered so Qt receives output immediately
        process->start("python3", QStringList()
                       << "-u"
                       << "/home/raspberrypi/eggmodule_qt/Egg_module_Qt_qml/egg_module_design/weight_reader.py");
    }

    float weight() const { return m_weight; }
    bool candlingState() const { return m_candlingState; }
    bool heartbeatActive() const { return m_heartbeatActive; }
    float heartbeatBpm() const { return m_heartbeatBpm; }
    QString heartbeatStatus() const { return m_heartbeatStatus; }
    QString heartbeatSignalStatus() const { return m_heartbeatSignalStatus; }
    bool heartbeatPulseDetected() const { return m_heartbeatPulseDetected; }
    float heartbeatRawSignal() const { return m_heartbeatRawSignal; }
    int heartbeatSensorPin() const { return 22; }
    int heartbeatLedPin() const { return 27; }

public slots:
    void tareScale()
    {
        process->write("tare\n");
    }

    void toggleCandling()
    {
        m_candlingState = !m_candlingState;
        emit candlingChanged();
    }

    void startHeartbeatScreening()
    {
        m_heartbeatActive = true;
        m_heartbeatStatus = "Detecting Signal...";
        m_heartbeatSignalStatus = "WEAK";
        emit heartbeatChanged();
    }

    void stopHeartbeatScreening()
    {
        m_heartbeatActive = false;
        m_heartbeatPulseDetected = false;
        m_heartbeatStatus = "Stopped";
        m_heartbeatSignalStatus = "DISCONNECTED";
        emit heartbeatChanged();
    }

signals:
    void weightChanged();
    void candlingChanged();
    void heartbeatChanged();

private slots:
    void readWeight()
    {
        QByteArray data = process->readAllStandardOutput();
        QList<QByteArray> lines = data.split('\n');

        for (auto &line : lines) {
            bool ok;
            float value = line.trimmed().toFloat(&ok);

            if (ok) {
                m_weight = value;
                emit weightChanged();
                qDebug() << "Weight received:" << m_weight;
            }
        }
    }

private:
    QProcess *process;
    float m_weight = 0;
    bool m_candlingState = false;
    bool m_heartbeatActive = false;
    float m_heartbeatBpm = 0.0f;
    QString m_heartbeatStatus = "Stopped";
    QString m_heartbeatSignalStatus = "DISCONNECTED";
    bool m_heartbeatPulseDetected = false;
    float m_heartbeatRawSignal = 0.0f;
};

#endif

