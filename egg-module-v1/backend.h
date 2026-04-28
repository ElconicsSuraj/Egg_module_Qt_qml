#ifndef BACKEND_H
#define BACKEND_H

#include <QObject>
#include <QProcess>
#include <QDebug>

class Backend : public QObject
{
    Q_OBJECT
   Q_PROPERTY(float weight READ weight NOTIFY weightChanged)

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

public slots:
    void tareScale()
    {
        process->write("tare\n");
    }

signals:
    void weightChanged();

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
};

#endif
