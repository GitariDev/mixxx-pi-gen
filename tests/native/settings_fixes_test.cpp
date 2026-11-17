// Native checks of mixxx-settings-fixes.patch: the shipping
// MixpiPerformanceSettings with the real control framework (staged by
// prepare_performance_settings.py; config, sound, waveform and dialogs are
// the doubles of performance_settings_stubs.h).
//
// usage: settings-fixes-test tempo|bar_late|bar_never|bar_normal
#include <QApplication>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QTimer>
#include <functional>
#include <iostream>
#include <memory>
#include <vector>
#include "performance_settings_stubs.h"
#include "control/controlobject.h"
#include "control/controlproxy.h"
#include "mixpiperformancesettings.h"

namespace {
int failures = 0;

void check(bool ok, const char* name) {
    std::cout << (ok ? "PASS " : "FAIL ") << name << std::endl;
    if (!ok) {
        std::cerr << "FAIL " << name << std::endl;
        ++failures;
    }
}

bool waitFor(const std::function<bool()>& condition, int milliseconds) {
    QElapsedTimer timer;
    timer.start();
    while (!condition() && timer.elapsed() < milliseconds) {
        QCoreApplication::processEvents(QEventLoop::AllEvents, 20);
    }
    return condition();
}

struct Fixture {
    QObject receiver;
    std::vector<std::unique_ptr<ControlObject>> controls;
    UserSettingsPointer config = UserSettingsPointer::create();
    SoundManager sound;
    std::unique_ptr<MixpiPerformanceSettings> settings;
    bool rejectNative = false;
    ControlObject* add(const char* group, const char* item, double value) {
        auto control = std::make_unique<ControlObject>(ConfigKey(group, item));
        control->set(value);
        auto* result = control.get();
        controls.push_back(std::move(control));
        return result;
    }
    explicit Fixture(double startRange = .1) {
        for (const char* group : {"[Channel1]", "[Channel2]"}) {
            auto* range = add(group, "rateRange", startRange);
            range->connectValueChangeRequest(&receiver, [this, range](double v) {
                if (!rejectNative) range->setAndConfirm(v);
            });
        }
        auto* engine = add("[App]", "keylock_engine", 1);
        engine->connectValueChangeRequest(&receiver, [engine](double v) { engine->setAndConfirm(v); });
        add("[App]", "audio_latency_usage", .25);
        add("[App]", "num_decks", 2);
        add("[App]", "num_samplers", 1);
        add("[App]", "num_preview_decks", 1);
        for (const char* group : {"[Channel1]", "[Channel2]", "[Sampler1]", "[PreviewDeck1]"}) {
            add(group, "play", 0);
        }
        add("[Recording]", "status", 0);
        settings = std::make_unique<MixpiPerformanceSettings>(nullptr, config, &sound);
    }
    double get(const char* item) { return ControlObject::get(ConfigKey("[MixPi]", item)); }
    void request(const char* item, double value) { ControlProxy("[MixPi]", item).set(value); }
    int savedRange() {
        return config->values.value(ConfigKey("[Controls]", "RateRangePercent"), -1);
    }
    double deck(const char* group) { return ControlObject::get(ConfigKey(group, "rateRange")); }
};

void tempo() {
    {
        // At start the index and the range follow the decks (which DlgPrefDeck
        // set from RateRangePercent); publishing them writes no config.
        Fixture f(.24);
        check(f.get("tempo_range") == 24 && f.get("tempo_range_index") == 6,
                "at start tempo_range and tempo_range_index follow the decks");
        check(f.config->writes == 0, "publishing the start values writes no config");
    }
    {
        // The decks already use 10 % but the file may say otherwise.
        Fixture f;
        f.request("tempo_range_index", 4);
        check(f.savedRange() == 10, "tempo_range_index for the current range still stores it");
    }
    // The card: decks at 8 %; Settings > Tempo range 10 % is a set-value press on the index.
    Fixture f(.08);
    f.request("tempo_range_index", 4);
    check(f.savedRange() == 10, "tempo_range_index 4 stores [Controls],RateRangePercent 10");
    check(f.deck("[Channel1]") == .10 && f.deck("[Channel2]") == .10, "both decks use 10 %");
    check(f.get("tempo_range") == 10 && f.get("tempo_range_index") == 4,
            "tempo_range and tempo_range_index agree");
    f.request("tempo_range", 16);
    check(f.savedRange() == 16 && f.get("tempo_range_index") == 5,
            "tempo_range 16 stores 16 and moves the index to 5");
    const int writes = f.config->writes;
    f.request("tempo_range", 7);
    f.request("tempo_range_index", 9);
    check(f.config->writes == writes && f.savedRange() == 16, "an invalid range writes nothing");
    f.rejectNative = true;
    f.request("tempo_range", 6);
    check(f.savedRange() == 16 && f.get("tempo_range") == 16,
            "when the decks refuse, the stored range is what they use");
    f.rejectNative = false;
    // A deck changed elsewhere (Preferences): the index follows on refresh.
    for (const char* group : {"[Channel1]", "[Channel2]"}) {
        ControlObject::getControl(ConfigKey(group, "rateRange"))->setAndConfirm(.5);
    }
    waitFor([&] { return f.get("tempo_range_index") == 7; }, 2500);
    check(f.get("tempo_range") == 50 && f.get("tempo_range_index") == 7,
            "a range set on the decks moves tempo_range and the index within 1 s");
}

int helperCalls() {
    QFile calls(qEnvironmentVariable("MIXPI_FAKE_BAR_DIR") + "/calls");
    if (!calls.open(QIODevice::ReadOnly)) return 0;
    return QString::fromUtf8(calls.readAll()).split('\n', Qt::SkipEmptyParts).size();
}

void bar(const QString& mode) {
    Fixture f;
    auto state = [&] { return f.get("desktop_bar"); };
    auto available = [&] { return f.get("desktop_bar_available"); };
    if (!waitFor([&] { return available() == 1 && state() == 0; }, 5000)) {
        check(false, "first status: hidden and available");
        return;
    }
    const int before = helperCalls();
    QMessageBox::warnings = 0;
    QElapsedTimer timer;
    timer.start();
    f.request("desktop_bar", 1);
    if (mode == "bar_never") {
        const bool reported = waitFor([&] { return QMessageBox::warnings > 0; }, 8000);
        std::cout << "OBSERVE failure reported after " << timer.elapsed() << " ms, helper calls "
                  << helperCalls() - before << std::endl;
        check(reported && QMessageBox::warnings == 1,
                "a show that is never confirmed still reports once");
        check(timer.elapsed() < 6000, "the failure is reported within 6 s");
        check(state() == 3 && available() == 0, "then the button reads Top bar unavailable");
        return;
    }
    bool steady = true;
    const bool shown = waitFor([&] {
        steady = steady && (state() == 2 || state() == 1);
        return state() == 1 && available() == 1;
    }, 6000);
    std::cout << "OBSERVE shown after " << timer.elapsed() << " ms, helper calls "
              << helperCalls() - before << std::endl;
    if (mode == "bar_late") {
        check(shown, "a show confirmed late reads Hide top bar");
        check(QMessageBox::warnings == 0, "a show confirmed late raises no Top bar was not confirmed");
        check(steady, "the button reads Checking top bar until the bar is confirmed");
    } else {
        check(shown && timer.elapsed() < 1000, "a show confirmed at once reads Hide top bar within 1 s");
        check(QMessageBox::warnings == 0 && helperCalls() - before == 1,
                "the normal show runs the helper once, no re-check");
    }
}
} // namespace

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    const QString mode = argc > 1 ? argv[1] : "tempo";
    if (mode == "tempo") {
        tempo();
    } else {
        bar(mode);
    }
    std::cout << "FAILURES " << failures << std::endl;
    return failures == 0 ? 0 : 1;
}
