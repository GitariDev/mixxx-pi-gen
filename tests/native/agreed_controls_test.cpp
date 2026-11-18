// Native checks of the wave C2 controls: mixxx-effects-save.patch,
// mixxx-save-within-second.patch and mixxx-agreed-controls.patch, with real
// Qt timers, threads, controls and files.
//
// usage: agreed-controls-test MODE DIRECTORY
// Each mode runs in its own process and directory.
#include <sys/stat.h>
#include <unistd.h>

#include <QApplication>
#include <QDir>
#include <QDomDocument>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QFileInfo>
#include <QMutex>
#include <QStringList>
#include <QThread>
#include <QTimer>
#include <algorithm>
#include <array>
#include <cstdio>
#include <functional>
#include <memory>
#include <vector>

#include "control/controlobject.h"
#include "control/controlproxy.h"
#include "control/controlpushbutton.h"
#include "effects/effectsautosave.h"
#include "mixer/mixpisamplerclear.h"
#include "preferences/usersettings.h"
#include "util/mixpidisplaycontrols.h"

namespace {
int failures = 0;
QMutex messagesMutex;
QStringList messages;
int configSaves = 0;
int effectsSaves = 0;
QElapsedTimer runClock;

void check(bool ok, const QString& name) {
    std::printf("%s %s\n", ok ? "PASS" : "FAIL", qPrintable(name));
    std::fflush(stdout);
    if (!ok) {
        std::fprintf(stderr, "FAIL %s\n", qPrintable(name));
        ++failures;
    }
}

void measure(const QString& what, const QList<qint64>& values) {
    QStringList text;
    for (const qint64 value : values) {
        text.append(QString::number(value));
    }
    std::printf("MEASURE %s ms: %s\n", qPrintable(what), qPrintable(text.join(' ')));
    std::fflush(stdout);
}

void handler(QtMsgType, const QMessageLogContext&, const QString& message) {
    QMutexLocker locker(&messagesMutex);
    messages.append(message);
    if (message.startsWith(QStringLiteral("ConfigAutosave: saved"))) {
        ++configSaves;
    }
    if (message.startsWith(QStringLiteral("EffectsAutosave: saved"))) {
        ++effectsSaves;
    }
    std::fprintf(stderr, "LOG %lld %s\n", static_cast<long long>(runClock.elapsed()),
            message.toLocal8Bit().constData());
}

int saves(const int& counter) {
    QMutexLocker locker(&messagesMutex);
    return counter;
}

bool logged(const QString& part) {
    QMutexLocker locker(&messagesMutex);
    for (const QString& message : std::as_const(messages)) {
        if (message.contains(part)) {
            return true;
        }
    }
    return false;
}

void spin(int ms) {
    QEventLoop loop;
    QTimer::singleShot(ms, &loop, &QEventLoop::quit);
    loop.exec();
}

// Polls every 5 ms; returns the time taken, or -1 after maxMs.
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

double get(const char* group, const QString& item) {
    return ControlObject::get(ConfigKey(QString::fromLatin1(group), item));
}

void set(const char* group, const QString& item, double value) {
    ControlObject::set(ConfigKey(QString::fromLatin1(group), item), value);
}

// ---------------------------------------------------------------------------
// Settings: one change on disk in under a second (spec s11).

int settingsFast(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    writeAll(path, QByteArrayLiteral("\n[Test]\nexisting 1\n"));
    UserSettingsPointer pConfig(new UserSettings(path, QStringLiteral("/res/"), directory));
    mixxx::ConfigAutosave autosave(pConfig);
    autosave.start();
    spin(400);
    QList<qint64> times;
    for (int i = 0; i < 6; ++i) {
        const QByteArray expected = QByteArrayLiteral("key single-") + QByteArray::number(i);
        pConfig->set(ConfigKey("[Test]", "key"), ConfigValue(QString::fromLatin1(expected.mid(4))));
        times.append(waitFor(3000, [&] { return readAll(path).contains(expected); }));
        // Changes at random points of the poll cycle.
        spin(900 + 37 * i);
    }
    measure(QStringLiteral("settings change to mixxx.cfg on disk"), times);
    check(!times.contains(-1) && *std::max_element(times.begin(), times.end()) < 1000,
            QStringLiteral("a single settings change is on disk in under 1 s"));
    check(saves(configSaves) == 6, QStringLiteral("one write for one change"));

    const int before = saves(configSaves);
    for (int i = 0; i < 50; ++i) {
        pConfig->set(ConfigKey("[Test]", "key"), ConfigValue(QStringLiteral("burst-%1").arg(i)));
        spin(20);
    }
    check(waitFor(3000, [&] { return readAll(path).contains("key burst-49"); }) >= 0,
            QStringLiteral("the last of a burst is on disk"));
    spin(1500);
    check(saves(configSaves) - before == 1, QStringLiteral("fifty sets in 1 s give one write"));

    const int idle = saves(configSaves);
    spin(3000);
    check(saves(configSaves) == idle, QStringLiteral("no write in 3 s of idle"));
    autosave.stop();
    return failures ? 1 : 0;
}

// ---------------------------------------------------------------------------
// Effects: effects.xml within a second of a change (spec s8, U-7).

// The loaded effect per unit and slot, as effects.xml stores it.
struct EffectsState {
    std::array<std::array<QString, 3>, 4> ids;
    int snapshots = 0;
    bool offGuiThread = false;
    QByteArray xml() {
        ++snapshots;
        if (QThread::currentThread() != qApp->thread()) {
            offGuiThread = true;
        }
        QDomDocument doc;
        QDomElement root = doc.createElement(QStringLiteral("MixxxEffects"));
        doc.appendChild(root);
        QDomElement chains = doc.createElement(QStringLiteral("Chains"));
        root.appendChild(chains);
        for (int unit = 0; unit < 4; ++unit) {
            QDomElement chain = doc.createElement(QStringLiteral("EffectChain"));
            chain.setAttribute(QStringLiteral("unit"), unit + 1);
            chains.appendChild(chain);
            for (int slot = 0; slot < 3; ++slot) {
                QDomElement effect = doc.createElement(QStringLiteral("Effect"));
                effect.setAttribute(QStringLiteral("slot"), slot + 1);
                QDomElement id = doc.createElement(QStringLiteral("Id"));
                id.appendChild(doc.createTextNode(ids[unit][slot]));
                effect.appendChild(id);
                chain.appendChild(effect);
            }
        }
        return doc.toString().toUtf8();
    }
};

QString loadedEffect(const QString& path, int unit, int slot) {
    QDomDocument doc;
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly) || !doc.setContent(&file)) {
        return QStringLiteral("<unreadable>");
    }
    const QDomNodeList chains = doc.elementsByTagName(QStringLiteral("EffectChain"));
    for (int i = 0; i < chains.size(); ++i) {
        const QDomElement chain = chains.at(i).toElement();
        if (chain.attribute(QStringLiteral("unit")).toInt() != unit) {
            continue;
        }
        const QDomNodeList effects = chain.elementsByTagName(QStringLiteral("Effect"));
        for (int j = 0; j < effects.size(); ++j) {
            const QDomElement effect = effects.at(j).toElement();
            if (effect.attribute(QStringLiteral("slot")).toInt() == slot) {
                return effect.firstChildElement(QStringLiteral("Id")).text();
            }
        }
    }
    return QStringLiteral("<missing>");
}

int effectsSave(const QString& directory) {
    const QString path = directory + QStringLiteral("/effects.xml");
    EffectsState state;
    state.ids[0] = {QStringLiteral("org.mixxx.effects.reverb"), QString(), QString()};
    writeAll(path, state.xml());
    mixxx::EffectsAutosave autosave(path, [&state] { return state.xml(); });
    autosave.start();
    spin(1200);
    check(saves(effectsSaves) == 0, QStringLiteral("no effects write while nothing changes"));

    const char* const effects[] = {"org.mixxx.effects.echo", "org.mixxx.effects.flanger",
            "org.mixxx.effects.filter", "org.mixxx.effects.bitcrusher",
            "org.mixxx.effects.phaser", "org.mixxx.effects.autopan"};
    QList<qint64> times;
    for (int i = 0; i < 6; ++i) {
        const int unit = i % 2;
        const int slot = i % 3;
        state.ids[unit][slot] = QString::fromLatin1(effects[i]);
        times.append(waitFor(3000, [&] {
            return loadedEffect(path, unit + 1, slot + 1) == QString::fromLatin1(effects[i]);
        }));
        spin(700 + 53 * i);
    }
    measure(QStringLiteral("effect change to effects.xml on disk"), times);
    check(!times.contains(-1) && *std::max_element(times.begin(), times.end()) < 1000,
            QStringLiteral("a loaded effect change is on disk in under 1 s"));
    check(saves(effectsSaves) == 6, QStringLiteral("one effects write for one change"));
    check(!state.offGuiThread, QStringLiteral("the effects state is read on the GUI thread only"));

    // Ten changes in one second (a player choosing effects): one write.
    int before = saves(effectsSaves);
    for (int i = 0; i < 10; ++i) {
        state.ids[2][i % 3] = QStringLiteral("org.mixxx.effects.burst%1").arg(i);
        spin(100);
    }
    check(waitFor(3000, [&] {
        return loadedEffect(path, 3, 1) == QStringLiteral("org.mixxx.effects.burst9");
    }) >= 0,
            QStringLiteral("the last of ten changes is on disk"));
    spin(1000);
    check(saves(effectsSaves) - before == 1, QStringLiteral("ten effect changes in 1 s give one write"));

    // A knob turned for 7 s: at most one write per 3 s.
    before = saves(effectsSaves);
    for (int i = 0; i < 70; ++i) {
        state.ids[3][0] = QStringLiteral("org.mixxx.effects.knob%1").arg(i);
        spin(100);
    }
    spin(1000);
    const int constant = saves(effectsSaves) - before;
    std::printf("MEASURE effects writes during 7 s of constant change: %d\n", constant);
    check(constant >= 2 && constant <= 4,
            QStringLiteral("under constant change at most one effects write per 3 s"));
    check(loadedEffect(path, 4, 1) == QStringLiteral("org.mixxx.effects.knob69"),
            QStringLiteral("the end of constant change is on disk"));

    // Idle: the snapshot is cheap and nothing is written.
    before = saves(effectsSaves);
    const int snapshots = state.snapshots;
    spin(2000);
    check(saves(effectsSaves) == before, QStringLiteral("no effects write in 2 s of idle"));
    std::printf("MEASURE effects snapshots per second while idle: %d\n", (state.snapshots - snapshots) / 2);

    // A failed write keeps the old file and is logged.
    const QByteArray old = readAll(path);
    ::chmod(QFile::encodeName(directory).constData(), 0555);
    state.ids[0][0] = QStringLiteral("org.mixxx.effects.readonly");
    spin(1500);
    check(readAll(path) == old, QStringLiteral("a failed effects write leaves the old file byte-identical"));
    check(logged(QStringLiteral("Could not write")), QStringLiteral("the failed effects write logs a warning"));
    ::chmod(QFile::encodeName(directory).constData(), 0755);
    check(waitFor(8000, [&] {
        return loadedEffect(path, 1, 1) == QStringLiteral("org.mixxx.effects.readonly");
    }) >= 0,
            QStringLiteral("the effects write is retried after a failure"));

    // After stop() (the quit path) nothing more is written.
    state.ids[0][1] = QStringLiteral("org.mixxx.effects.afterstop");
    autosave.stop();
    before = saves(effectsSaves);
    spin(1000);
    check(saves(effectsSaves) == before, QStringLiteral("no effects write after stop"));
    return failures ? 1 : 0;
}

int effectsKill(const QString& directory) {
    const QString path = directory + QStringLiteral("/effects.xml");
    EffectsState state;
    state.ids[0] = {QStringLiteral("org.mixxx.effects.reverb"), QString(), QString()};
    writeAll(path, state.xml());
    mixxx::EffectsAutosave autosave(path, [&state] { return state.xml(); });
    autosave.start();
    spin(500);
    state.ids[0][0] = QStringLiteral("org.mixxx.effects.flanger");
    std::printf("SET\n");
    std::fflush(stdout);
    spin(30000);
    return 1;
}

int effectsLoad(const QString& directory) {
    const QString loaded = loadedEffect(directory + QStringLiteral("/effects.xml"), 1, 1);
    std::printf("LOADED %s\n", qPrintable(loaded));
    check(loaded == QStringLiteral("org.mixxx.effects.flanger"),
            QStringLiteral("the next load has the effect changed 1 s before the kill"));
    return failures ? 1 : 0;
}

// ---------------------------------------------------------------------------
// Clear samples (spec s6, U-5).

// A sampler pad with Mixxx's eject rules (BaseTrackPlayerImpl::slotEjectTrack):
// no eject while playing; an eject on an empty pad reloads the last sample.
// Its stop is Mixxx's (EngineBuffer::slotControlStop): a press sets play to 0.
class Pad : public QObject {
  public:
    explicit Pad(int number, const QString& sample)
            : m_group(QStringLiteral("[Sampler%1]").arg(number)),
              m_sample(sample),
              m_loaded(ConfigKey(m_group, "track_loaded")),
              m_play(ConfigKey(m_group, "play")),
              m_stop(ConfigKey(m_group, "stop")),
              m_eject(ConfigKey(m_group, "eject")) {
        connect(&m_stop, &ControlObject::valueChanged, this, [this](double value) {
            if (value > 0) {
                ++stops;
                m_play.set(0);
            }
        });
        connect(&m_eject, &ControlObject::valueChanged, this, [this](double value) {
            if (value <= 0) {
                return;
            }
            if (m_play.get() > 0) {
                ++refused;
                return;
            }
            if (m_loaded.get() == 0) {
                ++reloads;
                m_loaded.set(1);
                return;
            }
            ++ejects;
            m_loaded.set(0);
        });
    }
    void load() {
        m_loaded.set(1);
    }
    void unload() {
        m_loaded.set(0);
    }
    void play(bool on) {
        m_play.set(on ? 1 : 0);
    }
    bool loaded() const {
        return m_loaded.get() == 1;
    }
    bool playing() const {
        return m_play.get() == 1;
    }
    QString sample() const {
        return m_sample;
    }
    int ejects = 0;
    int refused = 0;
    int reloads = 0;
    int stops = 0;

  private:
    const QString m_group;
    const QString m_sample;
    ControlObject m_loaded;
    ControlObject m_play;
    ControlPushButton m_stop;
    ControlPushButton m_eject;
};

QString tick(int pad) {
    return QStringLiteral("sampler_clear_tick%1").arg(pad);
}

int clearSamples(const QString& directory) {
    ControlObject samplers(ConfigKey("[App]", "num_samplers"));
    samplers.set(4);
    std::vector<std::unique_ptr<Pad>> pads;
    QHash<QString, QByteArray> files;
    auto addPad = [&](int number) {
        const QString sample = directory + QStringLiteral("/samples/pad%1.wav").arg(number);
        const QByteArray bytes = QByteArrayLiteral("RIFF sample ") + QByteArray::number(number);
        writeAll(sample, bytes);
        files.insert(sample, bytes);
        pads.push_back(std::make_unique<Pad>(number, sample));
    };
    for (int number = 1; number <= 4; ++number) {
        addPad(number);
    }
    MixpiSamplerClear clear;
    // Pads 5-8 appear later, as when the skin asks for 8 samplers.
    for (int number = 5; number <= 8; ++number) {
        addPad(number);
    }
    samplers.set(8);

    check(get("[MixPi]", "sampler_clear_open") == 0 && get("[MixPi]", "sampler_clear_count") == 0,
            QStringLiteral("the popover starts closed with nothing counted"));
    set("[MixPi]", tick(1), 1);
    set("[MixPi]", tick(7), 1);
    set("[MixPi]", "sampler_clear_open", 1);
    bool allClear = true;
    for (int pad = 1; pad <= 8; ++pad) {
        allClear = allClear && get("[MixPi]", tick(pad)) == 0;
    }
    check(allClear && get("[MixPi]", "sampler_clear_open") == 1,
            QStringLiteral("opening the popover clears every tick"));

    for (int number : {1, 2, 3, 6}) {
        pads[number - 1]->load();
    }
    set("[MixPi]", tick(1), 1);
    check(get("[MixPi]", "sampler_clear_count") == 1, QStringLiteral("a ticked loaded pad counts"));
    set("[MixPi]", tick(3), 1);
    set("[MixPi]", tick(4), 1); // empty
    set("[MixPi]", tick(6), 1); // added after start-up
    check(get("[MixPi]", "sampler_clear_count") == 3,
            QStringLiteral("the count is the ticked pads that hold a sample"));
    set("[MixPi]", tick(2), 2);
    check(get("[MixPi]", tick(2)) == 0, QStringLiteral("a tick takes only 0 or 1"));
    set("[MixPi]", "sampler_clear_count", 7);
    check(get("[MixPi]", "sampler_clear_count") == 3, QStringLiteral("the count is read-only"));
    pads[2]->unload();
    check(get("[MixPi]", "sampler_clear_count") == 2,
            QStringLiteral("the count follows a ticked pad that empties"));
    pads[2]->load();
    check(get("[MixPi]", "sampler_clear_count") == 3,
            QStringLiteral("the count follows a ticked pad that loads"));
    set("[MixPi]", tick(3), 0);
    check(get("[MixPi]", "sampler_clear_count") == 2, QStringLiteral("the count follows an unticked pad"));
    set("[MixPi]", tick(3), 1);

    // Pad 6 (ticked) and pad 2 (not ticked) play. Build E, the owner's
    // "Stop it, then clear": a ticked pad that plays is stopped, then emptied.
    pads[5]->play(true);
    pads[1]->play(true);
    set("[MixPi]", "sampler_clear", 1);
    check(!pads[0]->loaded() && !pads[2]->loaded() && pads[0]->ejects == 1 && pads[2]->ejects == 1,
            QStringLiteral("CLEAR empties the ticked pads that hold a sample"));
    check(pads[0]->stops == 0 && pads[2]->stops == 0,
            QStringLiteral("a ticked pad that is not playing is emptied without a stop"));
    check(pads[1]->loaded() && pads[1]->ejects == 0,
            QStringLiteral("CLEAR leaves an unticked pad loaded"));
    check(pads[1]->playing() && pads[1]->stops == 0,
            QStringLiteral("an unticked pad that plays keeps playing (not stopped)"));
    check(pads[3]->reloads == 0 && !pads[3]->loaded(),
            QStringLiteral("CLEAR never ejects an empty ticked pad (which would reload a sample)"));
    check(!pads[5]->playing() && pads[5]->stops == 1 && pads[5]->refused == 0,
            QStringLiteral("a playing ticked pad is stopped first (its own stop, once)"));
    check(!pads[5]->loaded() && pads[5]->ejects == 1,
            QStringLiteral("then the stopped pad is emptied: every ticked pad goes empty"));
    allClear = true;
    for (int pad = 1; pad <= 8; ++pad) {
        allClear = allClear && get("[MixPi]", tick(pad)) == 0;
    }
    check(allClear, QStringLiteral("CLEAR clears the ticks"));
    check(get("[MixPi]", "sampler_clear_open") == 0, QStringLiteral("CLEAR closes the popover"));
    check(get("[MixPi]", "sampler_clear_count") == 0 && get("[MixPi]", "sampler_clear") == 0,
            QStringLiteral("after CLEAR the count and the trigger read 0"));
    bool untouched = true;
    for (auto it = files.constBegin(); it != files.constEnd(); ++it) {
        untouched = untouched && QFile::exists(it.key()) && readAll(it.key()) == it.value();
    }
    check(untouched && QDir(directory + QStringLiteral("/samples")).entryList(QDir::Files).size() == 8,
            QStringLiteral("every sample file stays where it was, byte-identical"));

    // CLEAR with nothing ticked does nothing.
    set("[MixPi]", "sampler_clear", 1);
    check(pads[1]->loaded() && pads[1]->ejects == 0 && pads[1]->playing() && pads[1]->stops == 0 &&
                    pads[5]->reloads == 0 && !pads[5]->loaded(),
            QStringLiteral("CLEAR with nothing ticked empties nothing"));
    return failures ? 1 : 0;
}

// ---------------------------------------------------------------------------
// Brightness, Night dim and CPU readout (spec s12, U-9).

struct Panel {
    QString folder;
    QString brightness() const {
        return QString::fromLatin1(readAll(folder + QStringLiteral("/brightness"))).trimmed();
    }
};

Panel makePanels(const QString& directory, const QByteArray& level = "128\n") {
    const QString sys = directory + QStringLiteral("/sys");
    // Sorted first, but has no max_brightness: skipped.
    writeAll(sys + QStringLiteral("/0-broken/brightness"), "3\n");
    writeAll(sys + QStringLiteral("/10-0045/brightness"), level);
    writeAll(sys + QStringLiteral("/10-0045/max_brightness"), "255\n");
    writeAll(sys + QStringLiteral("/zz-other/brightness"), "10\n");
    writeAll(sys + QStringLiteral("/zz-other/max_brightness"), "100\n");
    qputenv("MIXPI_BACKLIGHT_DIR", QFile::encodeName(sys));
    return Panel{sys + QStringLiteral("/10-0045")};
}

int backlight(const QString& directory) {
    const Panel panel = makePanels(directory);
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    writeAll(path, QByteArrayLiteral("\n[Test]\nexisting 1\n"));
    UserSettingsPointer pConfig(new UserSettings(path, QStringLiteral("/res/"), directory));
    mixxx::ConfigAutosave autosave(pConfig);
    autosave.start();
    MixpiDisplayControls controls(pConfig);

    check(get("[MixPi]", "backlight_available") == 1, QStringLiteral("backlight_available is 1 for a writable panel"));
    check(get("[MixPi]", "backlight") == 50,
            QStringLiteral("with no saved value the slider starts from the panel's level (128 of 255 = 50 %)"));
    check(panel.brightness() == "128", QStringLiteral("nothing is written at start without a saved value"));
    check(get("[MixPi]", "show_cpu") == 1, QStringLiteral("show_cpu defaults to 1"));
    check(get("[MixPi]", "night_dim") == 0, QStringLiteral("night_dim defaults to 0"));

    set("[MixPi]", "backlight", 80);
    check(panel.brightness() == "204", QStringLiteral("80 % writes round(80 × 255 / 100) = 204"));
    QElapsedTimer timer;
    timer.start();
    const qint64 saved = waitFor(3000, [&] { return readAll(path).contains("Backlight 80"); });
    measure(QStringLiteral("brightness change to mixxx.cfg on disk"), {saved});
    check(saved >= 0 && saved < 1000, QStringLiteral("the brightness is in mixxx.cfg in under 1 s"));
    check(QString::fromLatin1(readAll(directory + QStringLiteral("/sys/zz-other/brightness"))).trimmed() == "10" &&
                    QString::fromLatin1(readAll(directory + QStringLiteral("/sys/0-broken/brightness"))).trimmed() == "3",
            QStringLiteral("only the first panel is written"));

    ControlProxy slider(ConfigKey("[MixPi]", "backlight"));
    slider.setParameter(1.0);
    check(get("[MixPi]", "backlight") == 100 && panel.brightness() == "255",
            QStringLiteral("the slider's top end is 100 % = max_brightness"));
    slider.setParameter(0.0);
    check(get("[MixPi]", "backlight") == 5 && panel.brightness() == "13",
            QStringLiteral("the slider's bottom end is 5 % = 13"));
    set("[MixPi]", "backlight", 1);
    check(get("[MixPi]", "backlight") == 5, QStringLiteral("the brightness never goes below 5 %"));

    set("[MixPi]", "night_dim", 1);
    check(get("[MixPi]", "night_dim") == 1 && panel.brightness() == "26",
            QStringLiteral("Night dim on puts the panel at 10 % of max (26)"));
    set("[MixPi]", "backlight", 60);
    check(get("[MixPi]", "backlight") == 60 && panel.brightness() == "26",
            QStringLiteral("a brightness change during Night dim is kept, the panel stays dim"));
    set("[MixPi]", "night_dim", 2);
    check(get("[MixPi]", "night_dim") == 1, QStringLiteral("night_dim takes only 0 or 1"));
    set("[MixPi]", "night_dim", 0);
    check(get("[MixPi]", "night_dim") == 0 && panel.brightness() == "153",
            QStringLiteral("Night dim off returns the panel to the brightness (60 % = 153)"));

    set("[MixPi]", "show_cpu", 0);
    check(get("[MixPi]", "show_cpu") == 0, QStringLiteral("show_cpu can be turned off"));
    set("[MixPi]", "show_cpu", 3);
    check(get("[MixPi]", "show_cpu") == 0, QStringLiteral("show_cpu takes only 0 or 1"));
    set("[MixPi]", "backlight_available", 0);
    check(get("[MixPi]", "backlight_available") == 1, QStringLiteral("backlight_available is read-only"));

    check(waitFor(3000, [&] {
        const QByteArray text = readAll(path);
        return text.contains("Backlight 60") && text.contains("NightDim 0") && text.contains("ShowCpu 0");
    }) >= 0,
            QStringLiteral("Brightness, Night dim and CPU readout are saved in mixxx.cfg"));
    autosave.stop();
    return failures ? 1 : 0;
}

int backlightReadOnly(const QString& directory) {
    if (::geteuid() == 0) {
        check(false, QStringLiteral("the read-only check needs a non-root user"));
        return 1;
    }
    const Panel panel = makePanels(directory);
    ::chmod(QFile::encodeName(panel.folder + QStringLiteral("/brightness")).constData(), 0444);
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    writeAll(path, QByteArrayLiteral("\n[MixPi]\nBacklight 40\n"));
    UserSettingsPointer pConfig(new UserSettings(path, QStringLiteral("/res/"), directory));
    MixpiDisplayControls controls(pConfig);
    check(get("[MixPi]", "backlight_available") == 0,
            QStringLiteral("backlight_available is 0 for a read-only brightness file"));
    set("[MixPi]", "backlight", 70);
    set("[MixPi]", "night_dim", 1);
    check(panel.brightness() == "128", QStringLiteral("a read-only panel is left as it is"));
    check(get("[MixPi]", "backlight") == 70 && get("[MixPi]", "backlight_available") == 0,
            QStringLiteral("the value is kept and the slider stays unavailable"));
    return failures ? 1 : 0;
}

int backlightSaved(const QString& directory) {
    {
        const Panel panel = makePanels(directory + QStringLiteral("/a"));
        const QString path = directory + QStringLiteral("/a/mixxx.cfg");
        writeAll(path, QByteArrayLiteral("\n[MixPi]\nBacklight 30\nNightDim 0\nShowCpu 0\n"));
        UserSettingsPointer pConfig(new UserSettings(path, QStringLiteral("/res/"), directory));
        MixpiDisplayControls controls(pConfig);
        check(get("[MixPi]", "backlight") == 30 && get("[MixPi]", "night_dim") == 0 &&
                        get("[MixPi]", "show_cpu") == 0,
                QStringLiteral("saved values are read back at start"));
        check(panel.brightness() == "77", QStringLiteral("the saved brightness is applied at start (30 % = 77)"));
    }
    {
        const Panel panel = makePanels(directory + QStringLiteral("/b"));
        const QString path = directory + QStringLiteral("/b/mixxx.cfg");
        writeAll(path, QByteArrayLiteral("\n[MixPi]\nBacklight 30\nNightDim 1\n"));
        UserSettingsPointer pConfig(new UserSettings(path, QStringLiteral("/res/"), directory));
        MixpiDisplayControls controls(pConfig);
        check(get("[MixPi]", "night_dim") == 1 && get("[MixPi]", "backlight") == 30 &&
                        get("[MixPi]", "show_cpu") == 1,
                QStringLiteral("a saved Night dim is read back at start"));
        check(panel.brightness() == "26", QStringLiteral("a saved Night dim is applied at start"));
    }
    return failures ? 1 : 0;
}

int backlightNone(const QString& directory) {
    const QString sys = directory + QStringLiteral("/sys");
    QDir().mkpath(sys);
    qputenv("MIXPI_BACKLIGHT_DIR", QFile::encodeName(sys));
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    writeAll(path, QByteArrayLiteral("\n"));
    UserSettingsPointer pConfig(new UserSettings(path, QStringLiteral("/res/"), directory));
    MixpiDisplayControls controls(pConfig);
    check(get("[MixPi]", "backlight_available") == 0, QStringLiteral("no panel: backlight_available is 0"));
    set("[MixPi]", "backlight", 50);
    set("[MixPi]", "night_dim", 1);
    check(get("[MixPi]", "backlight_available") == 0 && QDir(sys).isEmpty(),
            QStringLiteral("no panel: changes write nothing"));
    return failures ? 1 : 0;
}

} // namespace

int main(int argc, char** argv) {
    runClock.start();
    qInstallMessageHandler(handler);
    QApplication app(argc, argv);
    if (argc != 3) {
        std::fprintf(stderr, "usage: %s MODE DIRECTORY\n", argv[0]);
        return 2;
    }
    const QString mode = QString::fromLocal8Bit(argv[1]);
    const QString directory = QString::fromLocal8Bit(argv[2]);
    const QHash<QString, std::function<int(const QString&)>> modes = {
            {QStringLiteral("settings-fast"), settingsFast},
            {QStringLiteral("effects-save"), effectsSave},
            {QStringLiteral("effects-kill"), effectsKill},
            {QStringLiteral("effects-load"), effectsLoad},
            {QStringLiteral("clear"), clearSamples},
            {QStringLiteral("backlight"), backlight},
            {QStringLiteral("backlight-readonly"), backlightReadOnly},
            {QStringLiteral("backlight-saved"), backlightSaved},
            {QStringLiteral("backlight-none"), backlightNone},
    };
    if (!modes.contains(mode)) {
        std::fprintf(stderr, "unknown mode %s\n", argv[1]);
        return 2;
    }
    return modes.value(mode)(directory);
}
