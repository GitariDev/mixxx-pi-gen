// Native checks of the three-band main waveforms (R&D, owner 2026-11-23:
// direction A Overlay, as a setting in Settings › Advanced):
// mixxx-waveform-three-band.patch with real Qt threads, timers, controls and
// files, Mixxx's own config parser and the real WaveformWidgetRenderer::getGain.
//
// usage: waveform-three-band-test MODE DIRECTORY
// Each mode runs in its own process and directory. Built with
// MIXPI_THREE_BAND_BASELINE (the stack without the patch) the setting, the
// default, the availability control and the three-band height rule (main
// rows and the Loop panel) are absent and every check about them fails.
#include <QApplication>
#include <QDir>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QFileInfo>
#include <QHash>
#include <QThread>
#include <QTimer>
#include <cmath>
#include <cstdio>
#include <functional>
#include <memory>
#include <set>
#include <vector>

#include "control/controlobject.h"
#include "mixpi_filtered_choice.h"
#include "preferences/usersettings.h"
#include "waveform/mixpiwaveformgain.h"
#include "waveform/renderers/waveformwidgetrenderer.h"
#ifndef MIXPI_THREE_BAND_BASELINE
#include "util/mixpiwaveformcolours.h"
#endif

// The three members of WaveformWidgetRenderer that are not in its header
// (waveformwidgetrenderer.cpp needs the whole waveform stack). getGain, the
// main-row flag and m_gain are the shipped header's.
WaveformWidgetRenderer::WaveformWidgetRenderer(const QString& group)
        : m_group(group),
          m_mixpiMainWaveform(false),
          m_gain(1.0) {
}
WaveformWidgetRenderer::~WaveformWidgetRenderer() = default;
void WaveformWidgetRenderer::resizeRenderer(int, int, float) {
}

namespace {
int failures = 0;
QElapsedTimer runClock;

void check(bool ok, const QString& name) {
    std::printf("%s %s\n", ok ? "PASS" : "FAIL", qPrintable(name));
    std::fflush(stdout);
    if (!ok) {
        std::fprintf(stderr, "FAIL %s\n", qPrintable(name));
        ++failures;
    }
}

void measure(const QString& what, qint64 value) {
    std::printf("MEASURE %s ms: %lld\n", qPrintable(what), static_cast<long long>(value));
    std::fflush(stdout);
}

void handler(QtMsgType, const QMessageLogContext&, const QString& message) {
    std::fprintf(stderr, "LOG %lld %s\n", static_cast<long long>(runClock.elapsed()),
            message.toLocal8Bit().constData());
}

void spin(int ms) {
    QEventLoop loop;
    QTimer::singleShot(ms, &loop, &QEventLoop::quit);
    loop.exec();
}

qint64 waitFor(int maxMs, const std::function<bool()>& condition) {
    QElapsedTimer timer;
    timer.start();
    while (!condition()) {
        if (timer.elapsed() > maxMs) {
            return -1;
        }
        spin(5);
    }
    return timer.elapsed();
}

QByteArray readAll(const QString& path) {
    QFile file(path);
    return file.open(QIODevice::ReadOnly) ? file.readAll() : QByteArray();
}

void writeAll(const QString& path, const QByteArray& bytes) {
    QDir().mkpath(QFileInfo(path).absolutePath());
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size()) {
        qFatal("cannot write %s", qPrintable(path));
    }
}

// Every line of mixxx.cfg that starts with the key, trimmed, joined by "|".
QString savedLines(const QString& path, const char* key) {
    QStringList lines;
    for (const QByteArray& line : readAll(path).split('\n')) {
        if (line.trimmed().startsWith(key)) {
            lines.append(QString::fromLatin1(line.trimmed()));
        }
    }
    return lines.join(QLatin1Char('|'));
}

QString savedType(const QString& path) {
    return savedLines(path, "WaveformType ");
}

const ConfigKey kColours("[MixPi]", "waveform_colours");
const ConfigKey kAvailable("[MixPi]", "waveform_three_band_available");
const ConfigKey kTypeKey("[Waveform]", "WaveformType");
// A type Mixxx picks by itself when the saved one cannot be drawn.
constexpr int kFallbackType = 6;

// WaveformWidgetFactory as the setting sees it (mixpiAppliedType and
// mixpiSwitchTo), as a recording double. Like the real one it is the only
// writer of [Waveform],WaveformType.
struct Factory {
    UserSettingsPointer pConfig;
    // Types this start can draw (they have a handle).
    std::set<int> drawable = {17, 19, kFallbackType};
    // Types whose widget fails to start and falls back to the empty waveform.
    std::set<int> failing;
    int applied = 0;
    std::vector<int> calls;
    int callsOffGuiThread = 0;

    // WaveformWidgetFactory::setConfig: the saved type, or Mixxx's own choice.
    void setConfig(UserSettingsPointer pSettings) {
        pConfig = pSettings;
        bool ok = false;
        const int type = pConfig->getValueString(kTypeKey).toInt(&ok);
        applied = ok && drawable.count(type) ? type : kFallbackType;
        pConfig->setValue(kTypeKey, applied);
    }

    int appliedType() const {
        return applied;
    }

    // The main window's third call: findHandleIndexFromType(type) >= 0.
    bool canDraw(int type) const {
        return drawable.count(type) > 0;
    }

    bool switchTo(int type) {
        calls.push_back(type);
        if (QThread::currentThread() != QCoreApplication::instance()->thread()) {
            ++callsOffGuiThread;
        }
        if (!drawable.count(type)) {
            return false;
        }
        pConfig->setValue(kTypeKey, type);
        applied = failing.count(type) ? 0 : type;
        return applied == type;
    }
};

// Mixxx's start, in its order: the config is read (CoreServices), the default
// is applied once, the factory takes the type (MixxxMainWindow::initialize),
// then the setting is made.
struct App {
    App(const QString& directory, const QByteArray& cfg, std::set<int> drawable = {17, 19, kFallbackType})
            : path(directory + QStringLiteral("/mixxx.cfg")) {
        if (!cfg.isNull()) {
            writeAll(path, cfg);
        }
        pConfig = UserSettingsPointer(new UserSettings(path, QStringLiteral("/res/"), directory));
        autosave = std::make_unique<mixxx::ConfigAutosave>(pConfig);
        autosave->start();
        factory.drawable = std::move(drawable);
#ifndef MIXPI_THREE_BAND_BASELINE
        MixpiWaveformColours::defaultOnce(pConfig);
#endif
        factory.setConfig(pConfig);
#ifndef MIXPI_THREE_BAND_BASELINE
        MixpiWaveformColours::Waveforms waveforms;
        waveforms.appliedType = [this] { return factory.appliedType(); };
        waveforms.switchTo = [this](int type) { return factory.switchTo(type); };
        waveforms.canDraw = [this](int type) { return factory.canDraw(type); };
        colours = std::make_unique<MixpiWaveformColours>(pConfig, std::move(waveforms));
#endif
    }
    void sync() {
#ifndef MIXPI_THREE_BAND_BASELINE
        colours->sync();
#endif
    }
    QString path;
    UserSettingsPointer pConfig;
    std::unique_ptr<mixxx::ConfigAutosave> autosave;
    Factory factory;
#ifndef MIXPI_THREE_BAND_BASELINE
    std::unique_ptr<MixpiWaveformColours> colours;
#endif
};

double colours() {
    return ControlObject::exists(kColours) ? ControlObject::get(kColours) : -100.0;
}

// [MixPi],waveform_three_band_available, the 3-BAND button's enabled state.
double available() {
    return ControlObject::exists(kAvailable) ? ControlObject::get(kAvailable) : -100.0;
}

void choose(double value) {
    if (ControlObject::exists(kColours)) {
        ControlObject::set(kColours, value);
    }
}

// Writes the values from a worker thread, in order, as a controller script
// does, and returns when the thread has ended. The GUI thread's event loop
// has not run in between.
void chooseFromWorker(const std::vector<double>& values) {
    std::unique_ptr<QThread> worker(QThread::create([values] {
        for (const double value : values) {
            choose(value);
        }
    }));
    worker->start();
    worker->wait();
}

const QByteArray kDone = QByteArrayLiteral("\n[MixPi]\nThreeBandDefault 1\n");
const QByteArray kThreeBandCfg = QByteArrayLiteral(
                                         "\n[Test]\nexisting 1\n\n[Waveform]\nDefaultZoom 3\nWaveformType 19\n") +
        kDone;
const QByteArray kRgbCfg = QByteArrayLiteral("\n[Waveform]\nWaveformType 17\n") + kDone;

int setting(const QString& directory) {
    App app(directory, kThreeBandCfg);
    check(ControlObject::exists(kColours), QStringLiteral("[MixPi],waveform_colours exists"));
    check(colours() == 1, QStringLiteral("waveforms running type 19 show as 3-BAND (1)"));
    check(available() == 1,
            QStringLiteral("[MixPi],waveform_three_band_available is 1 when the factory has a handle for type 19"));

    choose(0);
    check(app.factory.calls == std::vector<int>{17},
            QStringLiteral("RGB asks the waveform factory for type 17 (all-shader RGB)"));
    check(colours() == 0, QStringLiteral("RGB is confirmed once the factory runs type 17"));
    check(available() == 1, QStringLiteral("3-BAND stays available while the waveforms run RGB"));
    const qint64 savedRgb = waitFor(3000, [&] { return savedType(app.path) == "WaveformType 17"; });
    measure(QStringLiteral("RGB to WaveformType 17 in mixxx.cfg on disk"), savedRgb);
    check(savedRgb >= 0 && savedRgb < 1000, QStringLiteral("RGB is saved in mixxx.cfg in under 1 s"));
    check(readAll(app.path).contains("existing 1") && readAll(app.path).contains("DefaultZoom 3"),
            QStringLiteral("the rest of mixxx.cfg is kept"));

    choose(1);
    check(app.factory.calls == std::vector<int>({17, 19}),
            QStringLiteral("3-BAND asks the waveform factory for type 19 (all-shader Filtered)"));
    check(colours() == 1, QStringLiteral("3-BAND is confirmed"));
    const qint64 savedBand = waitFor(3000, [&] { return savedType(app.path) == "WaveformType 19"; });
    measure(QStringLiteral("3-BAND to WaveformType 19 in mixxx.cfg on disk"), savedBand);
    // After RGB was saved, so the line really changed back.
    check(savedRgb >= 0 && savedBand >= 0 && savedBand < 1000,
            QStringLiteral("3-BAND is saved in mixxx.cfg in under 1 s"));
    return failures ? 1 : 0;
}

int refused(const QString& directory) {
    App app(directory, kThreeBandCfg);
    for (const double value : {2.0, -1.0, 0.5, 17.0}) {
        choose(value);
    }
    check(ControlObject::exists(kColours) && app.factory.calls.empty() && colours() == 1,
            QStringLiteral("values other than 0 and 1 are refused and change nothing"));

    // The control is read-only: only the setting writes it.
    if (ControlObject::exists(kAvailable)) {
        ControlObject::set(kAvailable, 0);
    }
    check(available() == 1 && app.factory.calls.empty(),
            QStringLiteral("a write to [MixPi],waveform_three_band_available is ignored (read-only)"));

    // This start has no handle for the RGB type.
    app.factory.drawable = {19, kFallbackType};
    choose(0);
    check(ControlObject::exists(kColours) && app.factory.calls == std::vector<int>{17} &&
                    colours() == 1 && app.factory.applied == 19,
            QStringLiteral("when the factory cannot draw the type, the setting stays 3-BAND"));
    check(available() == 1,
            QStringLiteral("a missing RGB handle does not make 3-BAND unavailable"));

    // The type has a handle but its widget falls back to the empty waveform.
    app.factory.drawable = {17, 19, kFallbackType};
    app.factory.failing = {17};
    choose(0);
    check(ControlObject::exists(kColours) && app.factory.calls == std::vector<int>({17, 17, 19}),
            QStringLiteral("when a waveform falls back to empty, the type from before is asked for again"));
    check(colours() == 1 && app.factory.applied == 19,
            QStringLiteral("and the setting shows what the waveforms run, 3-BAND, not what was asked"));
    check(available() == 1,
            QStringLiteral("a widget that fell back to empty leaves 3-BAND available (it has a handle)"));
    spin(1500);
    check(ControlObject::exists(kColours) && savedType(app.path) == "WaveformType 19",
            QStringLiteral("and mixxx.cfg keeps WaveformType 19"));
    return failures ? 1 : 0;
}

int start(const QString& directory) {
    {
        App app(directory + QStringLiteral("/rgb"), kRgbCfg);
        check(ControlObject::exists(kColours) && colours() == 0,
                QStringLiteral("waveforms running type 17 show as RGB (0)"));
        check(app.factory.calls.empty(), QStringLiteral("starting does not switch the waveforms"));
    }
    {
        // Saved 19, but this start cannot draw it: Mixxx picks its own type.
        App app(directory + QStringLiteral("/fallback"), kThreeBandCfg, {17, kFallbackType});
        check(ControlObject::exists(kColours) && app.factory.applied == kFallbackType && colours() == 0,
                QStringLiteral("a saved 19 the factory could not apply does not show as 3-BAND"));
        check(available() == 0,
                QStringLiteral("[MixPi],waveform_three_band_available is 0 when the factory has no handle for type 19"));
        choose(1);
        check(ControlObject::exists(kColours) && app.factory.calls == std::vector<int>{19} &&
                        colours() == 0 && available() == 0 && app.factory.applied == kFallbackType,
                QStringLiteral("a 3-BAND request is still refused then, and RGB stays lit"));
        // The control follows the factory's handles at every sync.
        app.factory.drawable = {17, 19, kFallbackType};
        app.sync();
        check(available() == 1,
                QStringLiteral("the availability follows the factory's handle for type 19 (sync)"));
        // Mixxx's own Preferences picks a type; the factory says so.
        app.factory.applied = 19;
        app.sync();
        check(colours() == 1, QStringLiteral("a type picked in Mixxx's Preferences is followed (sync)"));
        app.factory.applied = 0;
        app.sync();
        check(ControlObject::exists(kColours) && colours() == 0,
                QStringLiteral("empty waveforms do not show as 3-BAND"));
    }
    return failures ? 1 : 0;
}

// The one-time default, with the file Mixxx's own parser read.
bool defaultedOnce(const QString& directory, const QByteArray& cfg) {
    App app(directory, cfg);
    const bool applied = app.factory.applied == 19 && colours() == 1;
    const qint64 saved = waitFor(3000, [&] {
        return savedType(app.path) == "WaveformType 19" &&
                savedLines(app.path, "ThreeBandDefault ") == "ThreeBandDefault 1";
    });
    return applied && saved >= 0;
}

int defaultOnce(const QString& directory) {
    check(defaultedOnce(directory + QStringLiteral("/new"), QByteArray()),
            QStringLiteral("a start with no mixxx.cfg runs 3-BAND and saves type 19 and the marker"));
    check(defaultedOnce(directory + QStringLiteral("/no-type"),
                  QByteArrayLiteral("\n[Waveform]\nDefaultZoom 3\n")),
            QStringLiteral("a config without a waveform type gets 3-BAND once"));
    check(defaultedOnce(directory + QStringLiteral("/twice"),
                  QByteArrayLiteral("\n[Waveform]\nWaveformType 17\nWaveformType 17\n")),
            QStringLiteral("a repeated WaveformType key ends as one line with 19"));
    check(defaultedOnce(directory + QStringLiteral("/indented"),
                  QByteArrayLiteral("\n[Waveform]\n  WaveformType 17\n")),
            QStringLiteral("an indented WaveformType key ends as one line with 19"));
    check(defaultedOnce(directory + QStringLiteral("/sections"),
                  QByteArrayLiteral("\n[Waveform]\nWaveformType 17\n\n[MixPi]\nRamCacheMB 1024\n\n"
                                    "[Waveform]\nWaveformType 17\n\n[MixPi]\nOther 1\n")),
            QStringLiteral("repeated [Waveform] and [MixPi] sections still start and get 3-BAND once"));
    check(defaultedOnce(directory + QStringLiteral("/malformed"),
                  QByteArrayLiteral("garbage before any section\n[Waveform\nWaveformType\n\n[Waveform]\n"
                                    "WaveformType seventeen\n=\n")),
            QStringLiteral("a malformed config still starts and gets 3-BAND once"));

    // The update: a saved RGB becomes 3-BAND once; a later RGB choice is kept.
    const QString update = directory + QStringLiteral("/update");
    {
        App app(update, QByteArrayLiteral("\n[MixPi]\nRamCacheMB 1024\n\n[Waveform]\nDefaultZoom 3\nWaveformType 17\n"));
        check(app.factory.applied == 19 && colours() == 1,
                QStringLiteral("the update switches a saved RGB to 3-BAND"));
        check(app.factory.calls.empty(),
                QStringLiteral("the default is set before the factory reads the type, with no switch"));
        choose(0);
        check(ControlObject::exists(kColours) && colours() == 0 &&
                        waitFor(3000, [&] {
                            return savedType(app.path) == "WaveformType 17" &&
                                    savedLines(app.path, "ThreeBandDefault ") == "ThreeBandDefault 1";
                        }) >= 0 &&
                        readAll(app.path).contains("RamCacheMB 1024") &&
                        readAll(app.path).contains("DefaultZoom 3"),
                QStringLiteral("choosing RGB saves type 17 beside the marker and the other settings"));
    }
    for (int restart = 1; restart <= 2; ++restart) {
        App app(update, QByteArray());
        spin(1200);
        check(ControlObject::exists(kColours) && app.factory.applied == 17 && colours() == 0 &&
                        savedType(app.path) == "WaveformType 17",
                QStringLiteral("the RGB choice is kept at restart %1").arg(restart));
    }

    // A start that cannot draw type 19 does not use the default up.
    const QString later = directory + QStringLiteral("/later");
    {
        App app(later, QByteArrayLiteral("\n[Waveform]\nWaveformType 17\n"), {17, kFallbackType});
        spin(1200);
        check(ControlObject::exists(kColours) && colours() == 0 &&
                        savedLines(app.path, "ThreeBandDefault ").isEmpty(),
                QStringLiteral("a start that cannot draw 3-BAND shows RGB and leaves the default for later"));
    }
    check(defaultedOnce(later, QByteArray()),
            QStringLiteral("and the next start that can draw it gets 3-BAND"));
    return failures ? 1 : 0;
}

int thread(const QString& directory) {
    {
        App app(directory + QStringLiteral("/one"), kThreeBandCfg);
        chooseFromWorker({0});
        check(ControlObject::exists(kColours) && app.factory.calls.empty() && colours() == 1,
                QStringLiteral("a write from a worker thread does not switch the waveforms on that thread"));
        const qint64 applied = waitFor(3000, [&] { return !app.factory.calls.empty(); });
        check(applied >= 0 && app.factory.calls == std::vector<int>{17} &&
                        app.factory.callsOffGuiThread == 0,
                QStringLiteral("it reaches the waveform factory on the GUI thread"));
        check(colours() == 0 && app.factory.applied == 17,
                QStringLiteral("and is confirmed there"));

        const std::vector<double> writes = {1, 0, 1, 0, 1, 0, 1, 0, 1};
        chooseFromWorker(writes);
        check(app.factory.calls == std::vector<int>{17},
                QStringLiteral("rapid opposing writes from a worker thread wait for the GUI thread"));
        spin(300);
        check(app.factory.callsOffGuiThread == 0,
                QStringLiteral("rapid opposing writes from a worker thread all run on the GUI thread"));
        check(ControlObject::exists(kColours) && colours() == 1 && app.factory.applied == 19 &&
                        app.factory.calls == std::vector<int>({17, 19, 17, 19, 17, 19, 17, 19, 17, 19}),
                QStringLiteral("rapid opposing writes from a worker thread run in the order written and end in the last value"));
        check(waitFor(3000, [&] { return savedType(app.path) == "WaveformType 19"; }) >= 0,
                QStringLiteral("and that value is the one saved"));
    }
    {
        // A write still queued when the main window ends the setting.
        auto app = std::make_unique<App>(directory + QStringLiteral("/quit"), kThreeBandCfg);
        chooseFromWorker({0});
        const bool existed = ControlObject::exists(kColours);
        Factory* pFactory = &app->factory;
        const bool untouched = pFactory->calls.empty();
#ifndef MIXPI_THREE_BAND_BASELINE
        app->colours.reset();
#endif
        spin(200);
        check(existed && untouched && pFactory->calls.empty(),
                QStringLiteral("a write still queued at quit is dropped with the setting"));
        check(existed && !ControlObject::exists(kColours) && !ControlObject::exists(kAvailable),
                QStringLiteral("the controls end with the setting, before the factory"));
    }
    return failures ? 1 : 0;
}

// A waveform as WaveformWidgetFactory::createWaveformWidget leaves it (the
// main-row flag) and WaveformWidgetRenderer::onPreRender (m_gain).
struct Renderer : WaveformWidgetRenderer {
    Renderer(bool mainWaveform, double pregain, double totalGain)
            : WaveformWidgetRenderer(QStringLiteral("[Channel1]")) {
        setMixpiMainWaveform(mainWaveform);
        m_gain = mixpi::waveformHeightGain(isMixpiMainWaveform(), pregain, totalGain);
    }
};

// allshader::WaveformRendererFiltered's call, with the argument cut out of the
// stack's waveformrendererfiltered.cpp (MIXPI_FILTERED_ASKS names these two
// members): the height of a band at level 255, as a share of the half height,
// at VisualGain 1.
struct FilteredRenderer {
    const WaveformWidgetRenderer* m_waveformRenderer;
    bool m_bRgbStacked;
    double height() const {
        return m_waveformRenderer->getGain(MIXPI_FILTERED_ASKS);
    }
};

double filtered(bool mainWaveform, double pregain, double totalGain, bool stacked = false) {
    const Renderer renderer(mainWaveform, pregain, totalGain);
    return FilteredRenderer{&renderer, stacked}.height();
}

// allshader::WaveformRendererRGB asks getGains(&allGain, false, ...); the
// software and textured RGB renderers ask for true
// (tests/test_waveform_three_band.py checks both lines in the source).
double rgb(bool mainWaveform, double pregain, double totalGain, bool compensated = false) {
    return Renderer(mainWaveform, pregain, totalGain).getGain(compensated);
}

int height(const QString&) {
    const double main = filtered(true, 1.0, 0.38);
    std::printf("HEIGHTS main-filtered %.3f main-rgb %.3f loop-filtered %.3f loop-rgb %.3f\n", main,
            rgb(true, 1.0, 0.38), filtered(false, 1.0, 0.38), rgb(false, 1.0, 0.38));
    check(std::abs(main - mixpi::kMainWaveformGain) < 1e-9,
            QStringLiteral("a main waveform's loudest band stops at kMainWaveformGain (0.90) of the edge in 3-BAND"));
    check(std::abs(main - rgb(true, 1.0, 0.38)) < 1e-9,
            QStringLiteral("3-BAND's loudest band and RGB's loudest outline reach the same height"));
    check(std::abs(filtered(true, 0.5, 0.38) - 0.45) < 1e-9,
            QStringLiteral("the pregain knob still scales the 3-BAND height (0.5 to 0.45)"));
    // Owner, 2026-11-23: "Same height as RGB".
    check(std::abs(filtered(false, 1.0, 0.38) - 0.38) < 1e-9,
            QStringLiteral("the Loop panel's 3-BAND waveform draws at total_gain (0.38), not Mixxx's doubled 0.76"));
    check(std::abs(filtered(false, 1.0, 0.38) - rgb(false, 1.0, 0.38)) < 1e-9,
            QStringLiteral("the Loop panel's 3-BAND and RGB waveforms reach the same height"));
    check(std::abs(filtered(false, 2.0, 0.19) - 0.19) < 1e-9,
            QStringLiteral("the Loop panel's 3-BAND height still follows total_gain, not the pregain alone"));
    check(std::abs(rgb(false, 1.0, 0.38) - 0.38) < 1e-9,
            QStringLiteral("the Loop panel's RGB waveform keeps total_gain, as before"));
    // The rule is the Filtered renderer's alone (review, Sol 7).
    check(std::abs(rgb(true, 1.0, 0.38, true) - 1.80) < 1e-9 &&
                    std::abs(rgb(false, 1.0, 0.38, true) - 0.76) < 1e-9,
            QStringLiteral("renderers that ask getGain for the doubled height still get it on a main row"));
    check(std::abs(filtered(true, 1.0, 0.38, true) - 1.80) < 1e-9 &&
                    std::abs(filtered(false, 1.0, 0.38, true) - 0.76) < 1e-9,
            QStringLiteral("the Stacked type (the same renderer class) keeps Mixxx's doubled height"));
    return failures ? 1 : 0;
}

} // namespace

int main(int argc, char** argv) {
    runClock.start();
    qInstallMessageHandler(handler);
    QApplication application(argc, argv);
    if (argc != 3) {
        std::fprintf(stderr, "usage: %s MODE DIRECTORY\n", argv[0]);
        return 2;
    }
    const QString mode = QString::fromLocal8Bit(argv[1]);
    const QString directory = QString::fromLocal8Bit(argv[2]);
    const QHash<QString, std::function<int(const QString&)>> modes = {
            {QStringLiteral("setting"), setting},
            {QStringLiteral("refused"), refused},
            {QStringLiteral("start"), start},
            {QStringLiteral("default"), defaultOnce},
            {QStringLiteral("thread"), thread},
            {QStringLiteral("height"), height},
    };
    if (!modes.contains(mode)) {
        std::fprintf(stderr, "unknown mode %s\n", argv[1]);
        return 2;
    }
    const int result = modes.value(mode)(directory);
    std::printf("OK %d\n", failures);
    return result;
}
