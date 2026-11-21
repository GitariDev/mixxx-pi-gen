// Native checks of wave J9, Settings › Interface, Zoom (spec 2f):
// mixxx-zoom-setting.patch with real Qt timers, threads, controls and files.
//
// usage: zoom-setting-test MODE DIRECTORY
// Each mode runs in its own process and directory. Built with
// MIXPI_ZOOM_BASELINE (the stack without the patch) the Zoom controls are
// absent and every check about them fails.
#include <QApplication>
#include <QDir>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QFileInfo>
#include <QHash>
#include <QMutex>
#include <QStringList>
#include <QTimer>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <functional>
#include <memory>
#include <vector>

#include "control/controlobject.h"
#include "control/controlpushbutton.h"
#include "preferences/usersettings.h"
#ifndef MIXPI_ZOOM_BASELINE
#include "util/mixpizoomsetting.h"
#endif

namespace {
int failures = 0;
QMutex messagesMutex;
int configSaves = 0;
QElapsedTimer runClock;

// WaveformWidgetRenderer's zoom limits and default (checked against Mixxx
// by tests/test_zoom_setting.py).
constexpr double kMinZoom = 1.0;
constexpr double kMaxZoom = 10.0;
constexpr double kDefaultZoom = 3.0;

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
    QMutexLocker locker(&messagesMutex);
    if (message.startsWith(QStringLiteral("ConfigAutosave: saved"))) {
        ++configSaves;
    }
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

// The saved zoom line in mixxx.cfg, or "" when there is none.
QString savedLine(const QString& path) {
    for (const QByteArray& line : readAll(path).split('\n')) {
        if (line.startsWith("DefaultZoom ")) {
            return QString::fromLatin1(line);
        }
    }
    return QString();
}

// A deck's waveform controls, with the rules of BaseTrackPlayerImpl:
// waveform_zoom takes only 1-10; waveform_zoom_up adds 1 and
// waveform_zoom_down takes 1 off (the Loop panel's − and +).
class Deck : public QObject {
  public:
    explicit Deck(const QString& group)
            : m_zoom(ConfigKey(group, QStringLiteral("waveform_zoom"))),
              m_up(ConfigKey(group, QStringLiteral("waveform_zoom_up"))),
              m_down(ConfigKey(group, QStringLiteral("waveform_zoom_down"))) {
        m_zoom.connectValueChangeRequest(this, [this](double value) {
            if (value <= kMaxZoom && value >= kMinZoom) {
                m_zoom.setAndConfirm(value);
            }
        }, Qt::DirectConnection);
        m_zoom.set(1.0);
        connect(&m_up, &ControlObject::valueChanged, this, [this](double pressed) {
            if (pressed > 0.0) {
                m_zoom.set(m_zoom.get() + 1.0);
            }
        });
        connect(&m_down, &ControlObject::valueChanged, this, [this](double pressed) {
            if (pressed > 0.0) {
                m_zoom.set(m_zoom.get() - 1.0);
            }
        });
    }
    double zoom() const {
        return m_zoom.get();
    }
    // WaveformWidgetFactory::createWaveformWidget: viewer->setZoom(m_defaultZoom).
    void start(double defaultZoom) {
        m_zoom.set(defaultZoom);
    }
    // The skin's button writes from outside the control object (a control
    // object does not signal its own sets).
    void loopPlus() {
        ControlObject::set(m_down.getKey(), 1.0);
        ControlObject::set(m_down.getKey(), 0.0);
    }
    void loopMinus() {
        ControlObject::set(m_up.getKey(), 1.0);
        ControlObject::set(m_up.getKey(), 0.0);
    }

  private:
    ControlObject m_zoom;
    ControlPushButton m_up;
    ControlPushButton m_down;
};

// WaveformWidgetFactory::setConfig: the DefaultZoom it starts every waveform at.
double factoryDefaultZoom(const UserSettingsPointer& pConfig) {
    bool ok = false;
    const double value = pConfig->getValueString(ConfigKey("[Waveform]", "DefaultZoom")).toDouble(&ok);
    return ok ? std::clamp(value, kMinZoom, kMaxZoom) : kDefaultZoom;
}

// The waveform factory double: what setDefaultZoom was called with.
std::vector<double> factoryCalls;

struct App {
    explicit App(const QString& directory, const QByteArray& cfg)
            : path(directory + QStringLiteral("/mixxx.cfg")) {
        if (!cfg.isNull()) {
            writeAll(path, cfg);
        }
        pConfig = UserSettingsPointer(new UserSettings(path, QStringLiteral("/res/"), directory));
        autosave = std::make_unique<mixxx::ConfigAutosave>(pConfig);
        autosave->start();
        deck1 = std::make_unique<Deck>(QStringLiteral("[Channel1]"));
        deck2 = std::make_unique<Deck>(QStringLiteral("[Channel2]"));
#ifndef MIXPI_ZOOM_BASELINE
        zoom = std::make_unique<MixpiZoomSetting>(pConfig, [](double value) {
            factoryCalls.push_back(value);
        });
#endif
        // The skin is built after CoreServices; its waveforms start at the default.
        const double start = factoryDefaultZoom(pConfig);
        deck1->start(start);
        deck2->start(start);
    }
    QString path;
    UserSettingsPointer pConfig;
    std::unique_ptr<mixxx::ConfigAutosave> autosave;
    std::unique_ptr<Deck> deck1;
    std::unique_ptr<Deck> deck2;
#ifndef MIXPI_ZOOM_BASELINE
    std::unique_ptr<MixpiZoomSetting> zoom;
#endif
    bool both(double value) const {
        return deck1->zoom() == value && deck2->zoom() == value;
    }
    QString decks() const {
        return QStringLiteral(" (deck 1 %1, deck 2 %2)").arg(deck1->zoom()).arg(deck2->zoom());
    }
};

const ConfigKey kZoomIn("[MixPi]", "waveform_zoom_in");
const ConfigKey kZoomOut("[MixPi]", "waveform_zoom_out");

// A tap on the Interface row's button: the skin writes 1, then 0.
void tap(const ConfigKey& key) {
    if (!ControlObject::exists(key)) {
        return;
    }
    ControlObject::set(key, 1.0);
    ControlObject::set(key, 0.0);
}

const QByteArray kStartCfg = QByteArrayLiteral("\n[Test]\nexisting 1\n\n[Waveform]\nDefaultZoom 3\n");

// ---------------------------------------------------------------------------

int steps(const QString& directory) {
    App app(directory, kStartCfg);
    check(app.both(3), QStringLiteral("both decks start at the saved zoom 3") + app.decks());
    check(ControlObject::exists(kZoomIn) && ControlObject::exists(kZoomOut),
            QStringLiteral("[MixPi],waveform_zoom_in (+) and [MixPi],waveform_zoom_out (−) exist"));

    tap(kZoomIn);
    check(app.both(2), QStringLiteral("+ zooms both decks in by one step (3 to 2)") + app.decks());
    check(!factoryCalls.empty() && factoryCalls.back() == 2,
            QStringLiteral("+ sets the waveform factory's default zoom to 2"));
    const qint64 saved = waitFor(3000, [&] { return savedLine(app.path) == "DefaultZoom 2"; });
    measure(QStringLiteral("+ to DefaultZoom 2 in mixxx.cfg on disk"), saved);
    check(saved >= 0 && saved < 1000, QStringLiteral("the zoom is saved in mixxx.cfg in under 1 s"));
    check(readAll(app.path).contains("existing 1"), QStringLiteral("the rest of mixxx.cfg is kept"));

    const size_t calls = factoryCalls.size();
    ControlObject::set(kZoomIn, 0.0);
    check(factoryCalls.size() == calls && app.both(2), QStringLiteral("a release alone changes nothing"));

    tap(kZoomOut);
    check(app.both(3), QStringLiteral("− zooms both decks out by one step (2 to 3)") + app.decks());
    tap(kZoomOut);
    check(app.both(4), QStringLiteral("− again: both decks at 4") + app.decks());
    const qint64 savedOut = waitFor(3000, [&] { return savedLine(app.path) == "DefaultZoom 4"; });
    measure(QStringLiteral("− − to DefaultZoom 4 in mixxx.cfg on disk"), savedOut);
    check(savedOut >= 0 && savedOut < 1000, QStringLiteral("each change is saved in under 1 s"));
    return failures ? 1 : 0;
}

int ends(const QString& directory) {
    App app(directory, kStartCfg);
    // The Loop panel's buttons on a third deck, from the same start.
    Deck reference(QStringLiteral("[ChannelLoop]"));
    reference.start(3);
    QList<double> setting, panel;
    for (int i = 0; i < 4; ++i) {
        tap(kZoomIn);
        reference.loopPlus();
        setting.append(app.deck1->zoom());
        panel.append(reference.zoom());
    }
    check(setting == panel && app.both(kMinZoom),
            QStringLiteral("+ stops at 1, step for step as the Loop panel's + (2 1 1 1)") + app.decks());
    for (int i = 0; i < 11; ++i) {
        tap(kZoomOut);
        reference.loopMinus();
        setting.append(app.deck2->zoom());
        panel.append(reference.zoom());
    }
    check(setting == panel && app.both(kMaxZoom),
            QStringLiteral("− stops at 10, step for step as the Loop panel's −") + app.decks());
    QStringList text;
    for (const double value : std::as_const(setting)) {
        text.append(QString::number(value));
    }
    std::printf("STEPS %s\n", qPrintable(text.join(' ')));
    check(waitFor(3000, [&] { return savedLine(app.path) == "DefaultZoom 10"; }) >= 0,
            QStringLiteral("the saved zoom stops at 10 too"));
    return failures ? 1 : 0;
}

int loop(const QString& directory) {
    App app(directory, kStartCfg);
    app.deck1->loopPlus();
    check(app.deck1->zoom() == 2 && app.deck2->zoom() == 3,
            QStringLiteral("the Loop panel's + zooms only its deck, as before") + app.decks());
    spin(1500);
    check(savedLine(app.path) == "DefaultZoom 3",
            QStringLiteral("a Loop panel zoom does not change the saved setting"));
    tap(kZoomOut);
    check(app.both(4),
            QStringLiteral("then − on the Interface row sets both decks to the setting's next step (3 to 4)") +
                    app.decks());
    check(waitFor(3000, [&] { return savedLine(app.path) == "DefaultZoom 4"; }) >= 0,
            QStringLiteral("and saves it"));
    return failures ? 1 : 0;
}

// Press + on a saved 3, then wait to be killed.
int kill(const QString& directory) {
    App app(directory, kStartCfg);
    tap(kZoomIn);
    std::printf("SET\n");
    std::fflush(stdout);
    spin(60000);
    return 1;
}

// A new process on the killed one's mixxx.cfg: Mixxx starting again.
int restart(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    check(savedLine(path) == "DefaultZoom 2",
            QStringLiteral("after SIGKILL 1 s after + mixxx.cfg holds DefaultZoom 2"));
    App app(directory, QByteArray());
    check(app.both(2), QStringLiteral("after the restart both decks start at the saved zoom 2") + app.decks());
    tap(kZoomIn);
    check(app.both(1), QStringLiteral("and + carries on from it (2 to 1)") + app.decks());
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
            {QStringLiteral("steps"), steps},
            {QStringLiteral("ends"), ends},
            {QStringLiteral("loop"), loop},
            {QStringLiteral("kill"), kill},
            {QStringLiteral("restart"), restart},
    };
    if (!modes.contains(mode)) {
        std::fprintf(stderr, "unknown mode %s\n", argv[1]);
        return 2;
    }
    const int result = modes.value(mode)(directory);
    std::printf("OK %d\n", failures);
    return result;
}
