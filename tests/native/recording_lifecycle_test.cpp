#include "recording_lifecycle_doubles.h"
#include "engine/sidechain/enginerecord.h"
#include "recording/defs_recording.h"

#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTemporaryDir>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <sys/resource.h>
#include <unistd.h>
#include <vector>

class RawExternalEncoderDouble final : public Encoder {
  public:
    explicit RawExternalEncoderDouble(EncoderCallback* callback) : m_callback(callback) {}
    ~RawExternalEncoderDouble() override { ++recordingLifecycleDestructors; }
    int initEncoder(mixxx::audio::SampleRate, QString*) override {
        return recordingLifecycleInitFailure ? -1 : 0;
    }
    void encodeBuffer(const CSAMPLE* samples, int size) override {
        m_callback->write(nullptr, reinterpret_cast<const unsigned char*>(samples),
                0, size * static_cast<int>(sizeof(CSAMPLE)));
    }
    void updateMetaData(const QString&, const QString&, const QString&) override {}
    void flush() override { ++recordingLifecycleFlushes; }
    void setEncoderSettings(const EncoderSettings&) override {}
  private:
    EncoderCallback* m_callback;
};

EncoderFactory::EncoderFactory() = default;
const EncoderFactory& EncoderFactory::getFactory() {
    static EncoderFactory factory;
    return factory;
}
Encoder::Format EncoderFactory::getSelectedFormat(UserSettingsPointer) const {
    return {"RAW TEST DOUBLE - NOT WAV", "RAW", true, "raw"};
}
EncoderPointer EncoderFactory::createRecordingEncoder(
        const Encoder::Format&, UserSettingsPointer, EncoderCallback* callback) const {
    return std::make_shared<RawExternalEncoderDouble>(callback);
}

void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAIL " << message << std::endl;
        std::exit(1);
    }
}

QByteArray readOnly(const QString& path) {
    QFile input(path);
    require(input.open(QIODevice::ReadOnly), "reopen synthetic raw output read-only");
    return input.readAll();
}

int main(int argc, char** argv) {
    QCoreApplication application(argc, argv);
    require(argc == 3, "mode and isolated output directory required");
    const QString mode = QString::fromLocal8Bit(argv[1]);
    const QString directory = QString::fromLocal8Bit(argv[2]);
    auto config = UserSettingsPointer::create();
    auto select = [&](const QString& name) {
        config->values["[Recording]Path"] = directory + '/' + name + ".raw";
    };
    select(mode);
    std::vector<CSAMPLE> signal(4096);
    for (std::size_t index = 0; index < signal.size(); ++index) {
        signal[index] = index % 2 == 0 ? 0.25f : -0.5f;
    }
    const QByteArray expected(reinterpret_cast<const char*>(signal.data()),
            static_cast<qsizetype>(signal.size() * sizeof(CSAMPLE)));
    QJsonArray notifications;
    qint64 claimedBytes = 0;
    auto recorder = std::make_unique<EngineRecord>(config);
    QObject::connect(recorder.get(), &EngineRecord::isRecording,
            [&](bool recording, bool error) {
                notifications.append(QJsonObject{{"recording", recording}, {"error", error}});
            });
    QObject::connect(recorder.get(), &EngineRecord::bytesRecorded,
            [&](int bytes) { claimedBytes += bytes; });
    auto process = [&] { recorder->process(signal.data(), static_cast<int>(signal.size())); };
    auto start = [&] { recordingLifecycleStatus = RECORD_READY; process(); };
    auto stop = [&] { recordingLifecycleStatus = RECORD_OFF; process(); };
    QJsonObject result{{"mode", mode}, {"encoder", "raw external double; NOT production WAV"},
            {"qt", qVersion()}};

    if (mode == "qdatastream-recovery") {
        QFile file(directory + "/qt-stream.raw");
        QDataStream stream(&file);
        require(file.open(QIODevice::WriteOnly), "open Qt diagnostic file");
        struct rlimit previous;
        require(getrlimit(RLIMIT_FSIZE, &previous) == 0, "get Qt diagnostic limit");
        struct rlimit limited = previous;
        limited.rlim_cur = 4096;
        std::signal(SIGXFSZ, SIG_IGN);
        require(setrlimit(RLIMIT_FSIZE, &limited) == 0, "set Qt diagnostic limit");
        const int firstWrite = stream.writeRawData(expected.constData(), expected.size());
        file.flush();
        const int secondWrite = stream.writeRawData(expected.constData(), expected.size());
        result["failedWriteReturn"] = secondWrite;
        result["streamStatusAfterFailure"] = static_cast<int>(stream.status());
        result["fileError"] = file.errorString();
        result["firstWriteReturn"] = firstWrite;
        file.close();
        require(setrlimit(RLIMIT_FSIZE, &previous) == 0, "restore Qt diagnostic limit");
        require(file.open(QIODevice::WriteOnly), "reopen Qt diagnostic file");
        stream.setDevice(&file);
        result["withoutResetReturn"] = stream.writeRawData(expected.constData(), expected.size());
        stream.resetStatus();
        result["withResetReturn"] = stream.writeRawData(expected.constData(), expected.size());
        file.close();
        result["resetRecoversPayload"] = readOnly(file.fileName()) == expected;
        require(result["resetRecoversPayload"].toBool(), "explicit stream reset recovers raw payload");
    } else if (mode == "invalid-destination") {
        config->values["[Recording]Path"] = directory + "/missing-parent/output.raw";
        start();
        require(recordingLifecycleStatus == RECORD_OFF && !recorder->fileOpen(), "invalid path fails closed");
        require(notifications.last().toObject().value("error").toBool(), "invalid path reports error");
        select("recovery");
        start();
        stop();
        require(readOnly(config->values["[Recording]Path"]) == expected, "invalid path recovery payload");
    } else if (mode == "encoder-failure") {
        recordingLifecycleInitFailure = true;
        start();
        require(recordingLifecycleStatus == RECORD_OFF && !recorder->fileOpen(), "init failure fails closed");
        require(recordingLifecycleDialogs == 1, "init failure requests native dialog");
        recordingLifecycleInitFailure = false;
        start();
        stop();
        require(readOnly(config->values["[Recording]Path"]) == expected, "init recovery payload");
    } else if (mode == "write-failure") {
        struct rlimit previous;
        require(getrlimit(RLIMIT_FSIZE, &previous) == 0, "get file-size limit");
        struct rlimit limited = previous;
        limited.rlim_cur = 4096;
        std::signal(SIGXFSZ, SIG_IGN);
        require(setrlimit(RLIMIT_FSIZE, &limited) == 0, "set task-local file-size limit");
        start();
        process();
        process();
        const double statusDuringFailure = recordingLifecycleStatus;
        stop();
        const auto actualBytes = QFileInfo(config->values["[Recording]Path"]).size();
        require(setrlimit(RLIMIT_FSIZE, &previous) == 0, "restore task-local limit");
        result["claimedBytes"] = claimedBytes;
        result["actualBytes"] = actualBytes;
        result["statusDuringWriteFailure"] = statusDuringFailure;
        result["honestWriteFailure"] = statusDuringFailure == RECORD_OFF &&
                notifications.last().toObject().value("error").toBool();
        result["failureNotifications"] = notifications;
        require(actualBytes <= 4096, "real QFile rejects restricted writes");
        select("after-write-failure");
        start();
        stop();
        const auto recoveryPayload = readOnly(config->values["[Recording]Path"]);
        result["recoveryPayloadValid"] = recoveryPayload == expected;
        result["recoveryBytes"] = recoveryPayload.size();
    } else if (mode == "lease-denial") {
        auto drain = mixxx::media::registry().beginDrain("synthetic-unmounted-generation");
        require(bool(drain), "begin isolated in-memory drain");
        start();
        require(recordingLifecycleStatus == RECORD_OFF && !recorder->fileOpen(), "drain denies recording");
        require(notifications.last().toObject().value("error").toBool(), "drain reports denial");
        drain.cancel();
        start();
        stop();
        require(readOnly(config->values["[Recording]Path"]) == expected, "drain cancellation recovery");
    } else if (mode == "split-init-failure") {
        start();
        const QString firstPath = config->values["[Recording]Path"];
        select("failed-split");
        recordingLifecycleInitFailure = true;
        recordingLifecycleStatus = RECORD_SPLIT_CONTINUE;
        process();
        require(recordingLifecycleStatus == RECORD_OFF && !recorder->fileOpen(), "split init fails closed");
        require(notifications.last().toObject().value("error").toBool(), "split failure reports error");
        require(readOnly(firstPath) == expected, "split failure preserves preceding raw payload");
        recordingLifecycleInitFailure = false;
        select("split-recovery");
        start();
        stop();
        require(readOnly(config->values["[Recording]Path"]) == expected, "split failure recovery");
    } else if (mode == "shutdown") {
        start();
        recorder->shutdown();
        result["shutdownClosesFile"] = !recorder->fileOpen();
        result["statusAfterShutdown"] = recordingLifecycleStatus;
        recorder.reset();
        require(readOnly(config->values["[Recording]Path"]) == expected, "destructor closes raw output");
    } else if (mode == "interruption") {
        start();
        process();
        result["note"] = "_exit skips production recorder destructor; raw double cannot test WAV headers";
        std::cout << QJsonDocument(result).toJson(QJsonDocument::Compact).constData() << std::endl;
        _exit(0);
    } else {
        start();
        require(recordingLifecycleStatus == RECORD_ON && recorder->fileOpen(), "start enters ON");
        const int firstLength = recorder->filelen();
        process();
        require(recorder->filelen() > firstLength, "output grows while ON");
        const QString firstPath = config->values["[Recording]Path"];
        if (mode == "split") {
            select("split-next");
            recordingLifecycleStatus = RECORD_SPLIT_CONTINUE;
            process();
            require(recordingLifecycleStatus == RECORD_ON, "split continues ON");
            require(readOnly(firstPath) == expected + expected, "split closes first output");
            stop();
            require(readOnly(config->values["[Recording]Path"]) == expected, "split output payload");
        } else {
            stop();
            require(!recorder->fileOpen(), "stop closes output");
            require(readOnly(firstPath) == expected + expected, "stopped raw payload exact");
            select("restart");
            start();
            stop();
            require(readOnly(config->values["[Recording]Path"]) == expected, "restart payload exact");
        }
        require(recordingLifecycleFlushes == 2 && recordingLifecycleDestructors == 2,
                "normal stop and split flush and destroy encoder");
    }
    result["notifications"] = notifications;
    result["claimedBytesTotal"] = claimedBytes;
    result["flushes"] = recordingLifecycleFlushes;
    result["encoderDestructors"] = recordingLifecycleDestructors;
    result["diagnosticCompleted"] = true;
    std::cout << QJsonDocument(result).toJson(QJsonDocument::Compact).constData() << std::endl;
}
