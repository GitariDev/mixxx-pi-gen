#include <QCoreApplication>
#include <QEventLoop>
#include <QTimer>
#include <iostream>
#include <limits>
#include <memory>
#include <vector>
#include "performance_settings_stubs.h"
#include "control/controlobject.h"
#include "control/controlproxy.h"
#include "mixpiperformancesettings.h"

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

struct Fixture {
    QObject receiver;
    std::vector<std::unique_ptr<ControlObject>> controls;
    UserSettingsPointer config = UserSettingsPointer::create();
    SoundManager sound;
    std::unique_ptr<MixpiPerformanceSettings> settings;
    int rangeWrites[2] = {0, 0}, engineWrites = 0;
    bool rejectNative = false;
    ControlObject* add(const char* group, const char* item, double value) {
        auto control = std::make_unique<ControlObject>(ConfigKey(group, item));
        control->set(value);
        auto* result = control.get();
        controls.push_back(std::move(control));
        return result;
    }
    Fixture() {
        WaveformWidgetFactory::instance()->writes = 0;
        WaveformWidgetFactory::instance()->fps = 45;
        for (int i = 0; i != 2; ++i) {
            auto* range = add(i == 0 ? "[Channel1]" : "[Channel2]", "rateRange", .1);
            range->connectValueChangeRequest(&receiver, [this, range, i](double v) {
                if (++rangeWrites[i] > 32) throw std::runtime_error("recursive range setter");
                if (!rejectNative) range->setAndConfirm(v);
            });
        }
        auto* engine = add("[App]", "keylock_engine", 1);
        engine->connectValueChangeRequest(&receiver, [this, engine](double v) {
            if (++engineWrites > 32) throw std::runtime_error("recursive engine setter");
            if (!rejectNative) engine->setAndConfirm(v);
        });
        add("[App]", "audio_latency_usage", .25);
        add("[App]", "num_decks", 2);
        add("[App]", "num_samplers", 1);
        add("[App]", "num_preview_decks", 1);
        add("[Channel1]", "play", 0);
        add("[Channel2]", "play", 0);
        add("[Sampler1]", "play", 0);
        add("[PreviewDeck1]", "play", 0);
        add("[Recording]", "status", 0);
        settings = std::make_unique<MixpiPerformanceSettings>(nullptr, config, &sound);
    }
    double get(const char* item) { return ControlObject::get(ConfigKey("[MixPi]", item)); }
    void request(const char* item, double value) { ControlProxy("[MixPi]", item).set(value); }
    void refresh() {
        auto* timer = settings->findChild<QTimer*>();
        require(timer && QMetaObject::invokeMethod(timer, "timeout", Qt::DirectConnection), "timer refresh");
    }
    void unchangedSetters() {
        require(rangeWrites[0] == 0 && rangeWrites[1] == 0 && engineWrites == 0 &&
                WaveformWidgetFactory::instance()->writes == 0 && sound.writes == 0 &&
                config->writes == 0 && QMessageBox::prompts == 0, "publication invoked a setter");
    }
};

void semantics() {
    QObject receiver;
    ControlObject owner(ConfigKey("[Test]", "request"));
    ControlProxy writer("[Test]", "request");
    int requests = 0, changes = 0;
    owner.connectValueChangeRequest(&receiver, [&](double) { ++requests; });
    writer.connectValueChanged(&receiver, [&](double) { ++changes; });
    owner.set(0);
    writer.set(12);
    require(requests == 2 && owner.get() == 0 && changes == 0, "set must request even unchanged values");
    owner.setAndConfirm(12);
    require(requests == 2 && owner.get() == 12 && writer.get() == 12 && changes == 1, "confirmation must publish to writer");
    owner.setAndConfirm(12);
    require(changes == 1, "confirmed no-op must suppress notification");
}

void requests(Fixture& f) {
    QObject receiver;
    for (auto name : {"waveform_fps", "tempo_range", "keylock_engine", "read_ahead", "cache_mb"}) {
        ControlProxy writer("[MixPi]", name);
        int changes = 0;
        writer.connectValueChanged(&receiver, [&](double) { ++changes; });
        const double next = QString(name) == "waveform_fps" ? 60 :
                QString(name) == "tempo_range" ? 16 : QString(name) == "keylock_engine" ? 2 :
                QString(name) == "read_ahead" ? 24 : 512;
        writer.set(next);
        require(writer.get() == next && changes == 1, "accepted request must publish once to requester");
    }
    require(WaveformWidgetFactory::instance()->writes == 1 && f.rangeWrites[0] == 1 &&
            f.rangeWrites[1] == 1 && f.engineWrites == 1 && f.config->writes == 3,
            "accepted requests must apply once");
    require(f.config->getValue(ConfigKey("[MixPi]", "ReadAheadChunks"), 0) == 24 &&
            f.config->getValue(ConfigKey("[MixPi]", "RamCacheMB"), 0) == 512,
            "next-launch configuration must persist");
    for (auto fps : {30, 45, 60}) { f.request("waveform_fps", fps); require(f.get("waveform_fps") == fps, "FPS choice"); }
    for (auto range : {4, 6, 8, 10, 16, 24, 50, 90}) { f.request("tempo_range", range); require(f.get("tempo_range") == range, "range choice"); }
    const int ranges[] = {4, 6, 8, 10, 16, 24, 50, 90};
    for (int index = 1; index <= 8; ++index) {
        f.request("tempo_range_index", index);
        require(f.get("tempo_range") == ranges[index - 1] &&
                f.get("tempo_range_index") == index, "native indexed tempo choice");
    }
    const int writesBeforeEcho = f.rangeWrites[0];
    f.request("tempo_range_index", 8);
    require(f.rangeWrites[0] == writesBeforeEcho, "combo publication must not rewrite tempo");
    for (auto engine : {0, 1, 2}) { f.request("keylock_engine", engine); require(f.get("keylock_engine") == engine, "engine choice"); }
    f.rejectNative = true;
    f.request("tempo_range", 6);
    f.request("keylock_engine", 0);
    require(f.get("tempo_range") == 90 && f.get("keylock_engine") == 2, "publish actual native values after rejection");
    ControlObject::getControl("[Channel2]", "rateRange")->setAndConfirm(.06);
    f.refresh();
    require(f.get("tempo_range") == -1, "mixed deck ranges must remain visible");
}

void invalid(Fixture& f) {
    for (auto name : {"waveform_fps", "tempo_range", "tempo_range_index", "settings_advanced", "keylock_engine", "read_ahead", "cache_mb", "buffer_frames"}) {
        const double previous = f.get(name);
        for (double value : {-1., 3.5, 9999., std::numeric_limits<double>::infinity(), std::numeric_limits<double>::quiet_NaN()}) {
            f.request(name, value);
            require(f.get(name) == previous, "invalid request changed published state");
        }
    }
    EngineBuffer::available[2] = false;
    f.request("keylock_engine", 2);
    require(f.get("keylock_engine") == 1, "unavailable keylock accepted");
    f.unchangedSetters();
    f.request("settings_advanced", 1);
    f.refresh();
    require(f.get("settings_advanced") == 1, "refresh must retain Advanced page");
    f.request("settings_advanced", 0);
    require(f.get("settings_advanced") == 0, "Back must restore basic settings");
}

void buffer(Fixture& f) {
    const auto blocked = [&](const char* group, const char* item, double value) {
        ControlObject::set(ConfigKey(group, item), value);
        f.refresh();
        require(f.get("buffer_available") == 0, "buffer admission must be unavailable");
        const int prompts = QMessageBox::prompts;
        f.request("buffer_frames", 512);
        require(QMessageBox::prompts == prompts && f.sound.writes == 0, "blocked buffer prompted/applied");
        ControlObject::set(ConfigKey(group, item), 0);
    };
    for (auto group : {"[Channel1]", "[Channel2]", "[Sampler1]", "[PreviewDeck1]"}) blocked(group, "play", 1);
    blocked("[Recording]", "status", 1);
    blocked("[App]", "num_decks", 65);
    ControlObject::set(ConfigKey("[App]", "num_decks"), 2);
    f.sound.cfg.api = "Other";
    f.request("buffer_frames", 512);
    require(QMessageBox::prompts == 0, "unsupported backend prompted");
    f.sound.cfg.api = "ALSA";
    f.request("buffer_frames", 256);
    require(QMessageBox::prompts == 0, "same buffer prompted");
    f.request("buffer_frames", 512);
    require(QMessageBox::prompts == 1 && f.sound.writes == 0 && f.get("buffer_frames") == 256, "cancel changed buffer");
    QMessageBox::answer = QMessageBox::Ok;
    QMessageBox::during = [&] {
        f.refresh();
        require(f.get("buffer_available") == 0, "modal admission remained enabled");
        f.request("buffer_frames", 1024);
        ControlObject::set(ConfigKey("[Recording]", "status"), 1);
    };
    f.request("buffer_frames", 512);
    require(QMessageBox::prompts == 2 && QMessageBox::infos == 1 && f.sound.writes == 0, "modal recheck failed");
    ControlObject::set(ConfigKey("[Recording]", "status"), 0);
    QMessageBox::during = [&] { f.sound.cfg.index = 5; };
    f.request("buffer_frames", 512);
    require(f.sound.writes == 0 && f.get("buffer_frames") == 1024 && QMessageBox::infos == 2, "new audio configuration overwritten");
    QMessageBox::during = {};
    f.request("buffer_frames", 256);
    require(f.sound.writes == 1 && f.get("buffer_frames") == 256 && SoundManagerConfig::diskWrites == 1, "accepted buffer not applied once");
    f.sound.failures = 1;
    f.request("buffer_frames", 512);
    require(f.sound.writes == 3 && f.get("buffer_frames") == 256 && QMessageBox::warnings == 1 && SoundManagerConfig::diskWrites == 1, "failed buffer rollback/publication");
}

void bufferMapping(Fixture& fixture) {
    const std::vector<std::pair<double, unsigned>> rates = {
            {32000, 32}, {32999, 32}, {33000, 64}, {44100, 64},
            {48000, 64}, {64000, 64}, {64999, 64}, {65000, 128}, {96000, 128}};
    for (const auto& [sampleRate, firstFrames] : rates) {
        fixture.sound.cfg.rate.value = sampleRate;
        for (unsigned index = 1; index <= 7; ++index) {
            fixture.sound.cfg.setAudioBufferSizeIndex(index);
            fixture.refresh();
            require(fixture.get("buffer_frames") == (firstFrames << (index - 1)),
                    "sample-rate/index mapping differs from pinned production");
        }
    }
    fixture.sound.cfg.rate.value = 48000;
    fixture.sound.cfg.setAudioBufferSizeIndex(0);
    require(fixture.sound.cfg.index == 1 && fixture.sound.cfg.getFramesPerBuffer() == 64,
            "zero index must clamp to first size");
    fixture.sound.cfg.setAudioBufferSizeIndex(8);
    require(fixture.sound.cfg.index == 7 && fixture.sound.cfg.getFramesPerBuffer() == 4096,
            "oversized index must clamp to last size");
    fixture.sound.cfg.index = 0;
    require(fixture.sound.cfg.getFramesPerBuffer() == 1024, "invalid stored index fallback");
    for (unsigned invalidIndex : {0u, 8u}) {
        fixture.sound.cfg.index = invalidIndex;
        fixture.refresh();
        require(fixture.get("buffer_frames") == 0,
                "invalid stored index must not publish a buffer choice");
    }
    fixture.sound.cfg.api = "JACK";
    for (unsigned index : {5u, 6u, 7u}) {
        fixture.sound.cfg.setAudioBufferSizeIndex(index);
        require(fixture.sound.cfg.getFramesPerBuffer() == (1024u << (index - 5)),
                "JACK mapping must be sample-rate independent");
    }
    fixture.unchangedSetters();
}

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    const QString scenario = argc > 1 ? argv[1] : "initial";
    try {
        if (scenario == "semantics") {
            semantics();
        } else {
            qputenv("MIXPI_READAHEAD_CHUNKS", "8");
            qputenv("MIXPI_RAM_CACHE_MAX_MB", "1024");
            Fixture f;
            if (scenario == "initial") {
                require(f.get("settings_available") == 1 && f.get("waveform_fps") == 45 &&
                        f.get("tempo_range") == 10 && f.get("keylock_engine") == 1 &&
                        f.get("buffer_frames") == 256 && f.get("audio_load_percent") == 25 &&
                        f.get("read_ahead") == 8 && f.get("cache_mb") == 1024, "initial values");
                f.unchangedSetters();
            } else if (scenario == "periodic") {
                for (int i = 0; i != 100; ++i) f.refresh();
                QEventLoop loop;
                QTimer::singleShot(1100, &loop, &QEventLoop::quit);
                loop.exec();
                f.unchangedSetters();
            } else if (scenario == "requests") {
                requests(f);
            } else if (scenario == "invalid") {
                invalid(f);
            } else if (scenario == "buffer") {
                buffer(f);
            } else if (scenario == "buffer_mapping") {
                bufferMapping(f);
            } else if (scenario == "startup") {
                for (auto value : {2, 8, 24}) f.request("read_ahead", value);
                for (auto value : {0, 512, 1024}) f.request("cache_mb", value);
                require(f.config->writes == 6 && f.get("read_ahead") == 24 && f.get("cache_mb") == 1024, "startup requests must apply exactly once");
                require(qEnvironmentVariableIntValue("MIXPI_READAHEAD_CHUNKS") == 8 &&
                        qEnvironmentVariableIntValue("MIXPI_RAM_CACHE_MAX_MB") == 1024, "startup setting changed current process environment");
            } else {
                throw std::runtime_error("unknown scenario");
            }
        }
        std::cout << "PASS " << scenario.toStdString() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << scenario.toStdString() << ": " << error.what() << '\n';
        return 1;
    }
}
