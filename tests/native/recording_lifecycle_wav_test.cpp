#include "recording_lifecycle_doubles.h"
#include "engine/sidechain/enginerecord.h"
#include "encoder/encoderwave.h"
#include "encoder/encoderwavesettings.h"
#include "recording/defs_recording.h"
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <csignal>
#include <iostream>
#include <sys/resource.h>
#include <vector>

EncoderFactory::EncoderFactory() = default;
const EncoderFactory& EncoderFactory::getFactory() {
    static EncoderFactory factory;
    return factory;
}
Encoder::Format EncoderFactory::getSelectedFormat(UserSettingsPointer) const {
    return {"WAV", ENCODING_WAVE, true, "wav"};
}
EncoderPointer EncoderFactory::createRecordingEncoder(
        const Encoder::Format&, UserSettingsPointer config, EncoderCallback* callback) const {
    auto encoder = std::make_shared<EncoderWave>(callback);
    EncoderWaveSettings settings(config, ENCODING_WAVE);
    encoder->setEncoderSettings(settings);
    return encoder;
}

int main(int argc, char** argv) {
    QCoreApplication application(argc, argv);
    if (argc != 3) { return 2; }
    const QString mode = QString::fromLocal8Bit(argv[1]);
    const QString directory = QString::fromLocal8Bit(argv[2]);
    const bool holdout = mode == "holdout";
    recordingLifecycleSampleRate = holdout ? 44100 : 48000;
    auto config = UserSettingsPointer::create();
    config->values["[Recording]WAV_BITS"] = holdout ? "1" : "0";
    config->values["[Recording]Title"] = "Synthetic lifecycle qualification";
    auto select = [&](const QString& name) { config->values["[Recording]Path"] = directory + '/' + name + ".wav"; };
    select("first");
    std::vector<CSAMPLE> signal(holdout ? 2050 : 4096);
    for (std::size_t index = 0; index < signal.size(); ++index) {
        signal[index] = index % 2 == 0 ? 0.25f : -0.5f;
    }
    QJsonArray notifications;
    qint64 claimedBytes = 0;
    auto recorder = std::make_unique<EngineRecord>(config);
    QObject::connect(recorder.get(), &EngineRecord::isRecording, [&](bool active, bool error) {
        notifications.append(QJsonObject{{"recording", active}, {"error", error}});
    });
    QObject::connect(recorder.get(), &EngineRecord::bytesRecorded, [&](int bytes) { claimedBytes += bytes; });
    auto process = [&] { recorder->process(signal.data(), static_cast<int>(signal.size())); };
    auto start = [&] { recordingLifecycleStatus = RECORD_READY; process(); };
    auto stop = [&] { recordingLifecycleStatus = RECORD_OFF; process(); };
    struct rlimit previous;
    if (getrlimit(RLIMIT_FSIZE, &previous) != 0) { return 3; }
    auto restrictOutput = [&] {
        struct rlimit limited = previous;
        limited.rlim_cur = (mode == "stop-failure" || mode == "split-stop-failure") ? 1 : (holdout ? 350 : 4096);
        std::signal(SIGXFSZ, SIG_IGN);
        if (setrlimit(RLIMIT_FSIZE, &limited) != 0) { std::exit(4); }
    };
    QJsonObject result{{"mode", mode}, {"encoder", "production EncoderWave/libsndfile"},
            {"sndfile", sf_version_string()}, {"qt", qVersion()}, {"samplesPerBlock", int(signal.size())}};
    if (mode == "invalid-destination") {
        config->values["[Recording]Path"] = directory + "/absent/file.wav";
    }
    start();
    result["initialStatus"] = recordingLifecycleStatus;
    result["initialLength"] = recorder->filelen();
    if (mode == "write-failure" || holdout) {
        restrictOutput();
        process();
        process();
        result["failureStatus"] = recordingLifecycleStatus;
        result["failureNotifications"] = notifications;
        stop();
    } else if (mode == "stop-failure" || mode == "split-stop-failure") {
        restrictOutput();
        if (mode == "split-stop-failure") {
            select("failed-split");
            recordingLifecycleStatus = RECORD_SPLIT_CONTINUE;
            process();
        } else {
            stop();
        }
        result["failureStatus"] = recordingLifecycleStatus;
    } else if (mode == "seek-failure") {
        recorder->seek(-1);
        process();
        result["failureStatus"] = recordingLifecycleStatus;
    } else if (mode == "destructor") {
        recorder.reset();
    } else if (mode == "invalid-destination") {
        result["failureStatus"] = recordingLifecycleStatus;
    } else {
        process();
        result["grownLength"] = recorder->filelen();
        if (mode == "split") {
            select("split");
            recordingLifecycleStatus = RECORD_SPLIT_CONTINUE;
            process();
        }
        stop();
    }
    result["stopNotifications"] = notifications;
    result["claimedBytes"] = claimedBytes;
    if (setrlimit(RLIMIT_FSIZE, &previous) != 0) { return 5; }
    if (recorder) {
        select("recovery");
        start();
        stop();
        result["recoveryStatus"] = recordingLifecycleStatus;
    }
    result["notifications"] = notifications;
    std::cout << QJsonDocument(result).toJson(QJsonDocument::Compact).constData() << std::endl;
}
