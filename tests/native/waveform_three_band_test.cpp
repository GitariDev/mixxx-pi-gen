// Native checks of the three-band main waveforms (R&D, owner 2026-11-23:
// direction A Overlay, as a setting in Settings › Advanced):
// mixxx-waveform-three-band.patch with real Qt timers, controls and files.
//
// usage: waveform-three-band-test MODE DIRECTORY
// Each mode runs in its own process and directory. Built with
// MIXPI_THREE_BAND_BASELINE (the stack without the patch) the setting and the
// main waveforms' height rule are absent and every check about them fails.
#include <QApplication>
#include <QDir>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QFileInfo>
#include <QHash>
#include <QTimer>
#include <cmath>
#include <cstdio>
#include <functional>
#include <memory>
#include <vector>

#include "control/controlobject.h"
#include "preferences/usersettings.h"
#include "waveform/mixpiwaveformgain.h"
#ifndef MIXPI_THREE_BAND_BASELINE
#include "util/mixpiwaveformcolours.h"
#endif

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

// The saved waveform type line in mixxx.cfg, or "" when there is none.
QString savedLine(const QString& path) {
    for (const QByteArray& line : readAll(path).split('\n')) {
        if (line.startsWith("WaveformType ")) {
            return QString::fromLatin1(line);
        }
    }
    return QString();
}

// WaveformWidgetFactory::setWidgetTypeFromHandle, as a recording double: the
// types it was asked for, and whether it can switch (a GL type the card
// cannot draw has no handle and is refused).
std::vector<int> factoryCalls;
bool factoryAccepts = true;

const ConfigKey kColours("[MixPi]", "waveform_colours");

struct App {
    App(const QString& directory, const QByteArray& cfg)
            : path(directory + QStringLiteral("/mixxx.cfg")) {
        writeAll(path, cfg);
        pConfig = UserSettingsPointer(new UserSettings(path, QStringLiteral("/res/"), directory));
        autosave = std::make_unique<mixxx::ConfigAutosave>(pConfig);
        autosave->start();
#ifndef MIXPI_THREE_BAND_BASELINE
        colours = std::make_unique<MixpiWaveformColours>(pConfig, [](int type) {
            factoryCalls.push_back(type);
            return factoryAccepts;
        });
#endif
    }
    QString path;
    UserSettingsPointer pConfig;
    std::unique_ptr<mixxx::ConfigAutosave> autosave;
#ifndef MIXPI_THREE_BAND_BASELINE
    std::unique_ptr<MixpiWaveformColours> colours;
#endif
};

double colours() {
    return ControlObject::exists(kColours) ? ControlObject::get(kColours) : -100.0;
}

void choose(double value) {
    if (ControlObject::exists(kColours)) {
        ControlObject::set(kColours, value);
    }
}

const QByteArray kThreeBandCfg =
        QByteArrayLiteral("\n[Test]\nexisting 1\n\n[Waveform]\nDefaultZoom 3\nWaveformType 19\n");
const QByteArray kRgbCfg = QByteArrayLiteral("\n[Waveform]\nWaveformType 17\n");
const QByteArray kNoTypeCfg = QByteArrayLiteral("\n[Waveform]\nDefaultZoom 3\n");

int setting(const QString& directory) {
    App app(directory, kThreeBandCfg);
    check(ControlObject::exists(kColours), QStringLiteral("[MixPi],waveform_colours exists"));
    check(colours() == 1, QStringLiteral("a saved WaveformType 19 shows as 3-BAND (1)"));

    choose(0);
    check(factoryCalls == std::vector<int>{17},
            QStringLiteral("RGB asks the waveform factory for type 17 (all-shader RGB)"));
    check(colours() == 0, QStringLiteral("RGB is confirmed once the factory has switched"));
    const qint64 savedRgb = waitFor(3000, [&] { return savedLine(app.path) == "WaveformType 17"; });
    measure(QStringLiteral("RGB to WaveformType 17 in mixxx.cfg on disk"), savedRgb);
    check(savedRgb >= 0 && savedRgb < 1000, QStringLiteral("RGB is saved in mixxx.cfg in under 1 s"));
    check(readAll(app.path).contains("existing 1") && readAll(app.path).contains("DefaultZoom 3"),
            QStringLiteral("the rest of mixxx.cfg is kept"));

    choose(1);
    check(factoryCalls == std::vector<int>({17, 19}),
            QStringLiteral("3-BAND asks the waveform factory for type 19 (all-shader Filtered)"));
    check(colours() == 1, QStringLiteral("3-BAND is confirmed"));
    const qint64 savedBand = waitFor(3000, [&] { return savedLine(app.path) == "WaveformType 19"; });
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
    check(ControlObject::exists(kColours) && factoryCalls.empty() && colours() == 1,
            QStringLiteral("values other than 0 and 1 are refused and change nothing"));
    factoryAccepts = false;
    choose(0);
    check(ControlObject::exists(kColours) && factoryCalls == std::vector<int>{17} && colours() == 1,
            QStringLiteral("when the factory cannot switch, the setting stays 3-BAND"));
    spin(1500);
    check(savedLine(app.path) == "WaveformType 19",
            QStringLiteral("and mixxx.cfg keeps WaveformType 19"));
    return failures ? 1 : 0;
}

int start(const QString& directory) {
    {
        App app(directory + QStringLiteral("/rgb"), kRgbCfg);
        check(ControlObject::exists(kColours) && colours() == 0,
                QStringLiteral("a saved WaveformType 17 shows as RGB (0)"));
    }
    {
        App app(directory + QStringLiteral("/none"), kNoTypeCfg);
        check(ControlObject::exists(kColours) && colours() == 0,
                QStringLiteral("no saved WaveformType shows as RGB (0), Mixxx's own choice"));
    }
    check(factoryCalls.empty(), QStringLiteral("starting does not switch the waveforms"));
    return failures ? 1 : 0;
}

// The height the Filtered renderer gives a band at level 255, as a share of
// the half height: getGain(true) x VisualGain_0 (1) x 255 / 255, with m_gain
// from WaveformWidgetRenderer::onPreRender (mixpi::waveformHeightGain).
double filteredBandHeight(bool mainWaveform, double pregain, double totalGain) {
    const double gain = mixpi::waveformHeightGain(mainWaveform, pregain, totalGain);
#ifndef MIXPI_THREE_BAND_BASELINE
    return gain * mixpi::heightCompensation(mainWaveform, true);
#else
    return gain * 2.0;  // stock WaveformWidgetRenderer::getGain(true)
#endif
}

double rgbHeight(bool mainWaveform, double pregain, double totalGain) {
    const double gain = mixpi::waveformHeightGain(mainWaveform, pregain, totalGain);
#ifndef MIXPI_THREE_BAND_BASELINE
    return gain * mixpi::heightCompensation(mainWaveform, false);
#else
    return gain;  // stock getGain(false)
#endif
}

int height(const QString&) {
    const double main = filteredBandHeight(true, 1.0, 0.38);
    std::printf("HEIGHTS main-filtered %.3f main-rgb %.3f loop-filtered %.3f loop-rgb %.3f\n", main,
            rgbHeight(true, 1.0, 0.38), filteredBandHeight(false, 1.0, 0.38),
            rgbHeight(false, 1.0, 0.38));
    check(std::abs(main - mixpi::kMainWaveformGain) < 1e-9,
            QStringLiteral("a main waveform's loudest band stops at kMainWaveformGain (0.90) of the edge in 3-BAND"));
    check(std::abs(main - rgbHeight(true, 1.0, 0.38)) < 1e-9,
            QStringLiteral("3-BAND's loudest band and RGB's loudest outline reach the same height"));
    check(std::abs(filteredBandHeight(true, 0.5, 0.38) - 0.45) < 1e-9,
            QStringLiteral("the pregain knob still scales the 3-BAND height (0.5 to 0.45)"));
    check(std::abs(filteredBandHeight(false, 1.0, 0.38) - 0.76) < 1e-9,
            QStringLiteral("the Loop panel's waveform keeps Mixxx's doubled Filtered height (2 x total_gain)"));
    check(std::abs(rgbHeight(false, 1.0, 0.38) - 0.38) < 1e-9,
            QStringLiteral("the Loop panel's RGB waveform keeps total_gain, as before"));
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
