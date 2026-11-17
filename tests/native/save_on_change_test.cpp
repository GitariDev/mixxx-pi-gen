// Native checks of mixxx-save-on-change.patch (R-13): the shipped
// ConfigObject::save(), ConfigAutosave and SamplerBank with real Qt timers,
// threads and files.
//
// usage: save-on-change-test MODE DIRECTORY
// Each mode runs in its own process and directory. Built with
// MIXPI_PINNED_SAVE against the pinned ConfigObject, only "never-missing"
// exists: the holdout that the pinned save fails.
#include <sys/stat.h>
#include <unistd.h>

#include <QApplication>
#include <QDir>
#include <QDomDocument>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QMutex>
#include <QStringList>
#include <QTimer>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <functional>
#include <thread>

#include "preferences/usersettings.h"
#ifndef MIXPI_PINNED_SAVE
#include "control/control.h"
#include "control/controlobject.h"
#include "mixer/playermanager.h"
#include "mixer/samplerbank.h"
#endif

namespace {
int failures = 0;
QMutex messagesMutex;
QStringList messages;
QList<qint64> saveTimesMs;
QElapsedTimer runClock;

void check(bool ok, const char* name) {
    std::printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    std::fflush(stdout);
    if (!ok) {
        std::fprintf(stderr, "FAIL %s\n", name);
        ++failures;
    }
}

void handler(QtMsgType, const QMessageLogContext&, const QString& message) {
    QMutexLocker locker(&messagesMutex);
    messages.append(message);
    if (message.startsWith(QStringLiteral("ConfigAutosave: saved"))) {
        saveTimesMs.append(runClock.elapsed());
    }
    std::fprintf(stderr, "LOG %lld %s\n", static_cast<long long>(runClock.elapsed()),
            message.toLocal8Bit().constData());
}

[[maybe_unused]] int saves() {
    QMutexLocker locker(&messagesMutex);
    return static_cast<int>(saveTimesMs.size());
}

[[maybe_unused]] bool logged(const QString& part) {
    QMutexLocker locker(&messagesMutex);
    for (const QString& message : std::as_const(messages)) {
        if (message.contains(part)) {
            return true;
        }
    }
    return false;
}

[[maybe_unused]] void spin(int ms) {
    QEventLoop loop;
    QTimer::singleShot(ms, &loop, &QEventLoop::quit);
    loop.exec();
}

[[maybe_unused]] bool waitFor(int maxMs, const std::function<bool()>& condition) {
    QElapsedTimer timer;
    timer.start();
    while (!condition()) {
        if (timer.elapsed() > maxMs) {
            return false;
        }
        spin(25);
    }
    return true;
}

QByteArray readAll(const QString& path) {
    QFile file(path);
    return file.open(QIODevice::ReadOnly) ? file.readAll() : QByteArray();
}

void writeAll(const QString& path, const QByteArray& bytes) {
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size()) {
        qFatal("cannot write %s", qPrintable(path));
    }
}

[[maybe_unused]] quint64 inode(const QString& path) {
    struct stat info;
    return ::stat(QFile::encodeName(path).constData(), &info) == 0 ? info.st_ino : 0;
}

const QByteArray kInitial = QByteArrayLiteral("\n[Test]\nexisting 1\npersisted 0.5\n");

UserSettingsPointer makeConfig(const QString& directory, const QString& path) {
    writeAll(path, kInitial);
    return UserSettingsPointer(new UserSettings(path, QStringLiteral("/res/"), directory));
}

int neverMissing(const QString& directory) {
    // The config path must exist at every moment of a save: a reader
    // racing the save (another start, a crash at the wrong moment) never
    // finds no mixxx.cfg.
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    UserSettingsPointer pConfig = makeConfig(directory, path);
    const QByteArray encoded = QFile::encodeName(path);
    std::atomic<bool> stop{false};
    std::atomic<long> probes{0};
    std::atomic<long> misses{0};
    std::thread watcher([&] {
        struct stat info;
        while (!stop.load()) {
            if (::stat(encoded.constData(), &info) != 0) {
                ++misses;
            }
            ++probes;
        }
    });
    bool allSaved = true;
    for (int i = 0; i < 400; ++i) {
        pConfig->set(ConfigKey(QStringLiteral("[Test]"), QStringLiteral("key")),
                ConfigValue(QString::number(i)));
        allSaved = pConfig->save() && allSaved;
    }
    stop = true;
    watcher.join();
    std::printf("PROBES %ld MISSES %ld\n", probes.load(), misses.load());
    check(allSaved, "400 saves succeed");
    check(probes.load() > 1000, "the watcher probed the path during the saves");
    check(misses.load() == 0, "the config path is never missing during a save");
    check(readAll(path).contains("key 399"), "the last save holds the last value");
    return failures;
}

#ifndef MIXPI_PINNED_SAVE
using mixxx::ConfigAutosave;

const ConfigKey kKey(QStringLiteral("[Test]"), QStringLiteral("key"));

double savedIndicator() {
    return ControlObject::get(ConfigAutosave::savedKey());
}

int debounce(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    UserSettingsPointer pConfig = makeConfig(directory, path);
    ConfigAutosave autosave(pConfig);
    autosave.start();
    spin(1300); // the change lands at an arbitrary phase of the poll
    const QByteArray before = readAll(path);
    check(savedIndicator() == 0.0, "[MixPi],saved is 0 before any write");
    pConfig->set(kKey, ConfigValue(QStringLiteral("one")));
    spin(500);
    check(readAll(path) == before, "the file is unchanged 0.5 s after a change");
    check(waitFor(2000, [&] { return readAll(path).contains("\nkey one\n"); }),
            "the file holds the value by 2.5 s");
    check(readAll(path) == QByteArrayLiteral("\n[Test]\nexisting 1\nkey one\npersisted 0.5\n"),
            "the file keeps the mixxx.cfg layout and every other key");
    check(saves() == 1, "one write for one change");
    check(savedIndicator() == 1.0, "[MixPi],saved is 1 after the write");
    check(waitFor(2600, [] { return savedIndicator() == 0.0; }),
            "[MixPi],saved returns to 0 about 2 s after the write");
    // Setting the same value again is no change.
    pConfig->set(kKey, ConfigValue(QStringLiteral("one")));
    spin(3000);
    check(saves() == 1, "setting a key to its current value writes nothing");
    // A change of case is a change in the file.
    pConfig->set(kKey, ConfigValue(QStringLiteral("ONE")));
    check(waitFor(3000, [&] { return readAll(path).contains("\nkey ONE\n"); }),
            "a change of case is saved");
    pConfig->remove(kKey);
    check(waitFor(3000, [&] { return !readAll(path).contains("\nkey "); }),
            "a removed key is saved");
    return failures;
}

int burst(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    UserSettingsPointer pConfig = makeConfig(directory, path);
    ConfigAutosave autosave(pConfig);
    autosave.start();
    spin(1200);
    for (int i = 0; i < 50; ++i) {
        pConfig->set(kKey, ConfigValue(QString::number(i)));
        spin(20);
    }
    spin(4000);
    check(saves() == 1, "fifty sets in 1 s give one write");
    check(readAll(path).contains("\nkey 49\n"), "the write holds the last value");
    return failures;
}

int constant(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    UserSettingsPointer pConfig = makeConfig(directory, path);
    ConfigAutosave autosave(pConfig);
    autosave.start();
    for (int i = 0; i < 120; ++i) { // a change every 100 ms for 12 s
        pConfig->set(kKey, ConfigValue(QString::number(i)));
        spin(100);
    }
    QList<qint64> times;
    {
        QMutexLocker locker(&messagesMutex);
        times = saveTimesMs;
    }
    bool spaced = true;
    for (int i = 1; i < times.size(); ++i) {
        spaced = spaced && times.at(i) - times.at(i - 1) >= 4900;
    }
    std::printf("SAVES %lld\n", static_cast<long long>(times.size()));
    check(times.size() >= 2, "constant change is still saved, at least every 5-6 s");
    check(spaced, "under constant change at most one write per 5 s");
    return failures;
}

int idle(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    UserSettingsPointer pConfig = makeConfig(directory, path);
    ControlDoublePrivate::setUserConfig(pConfig);
    // A persist control whose value is the one in the file.
    auto pPersist = std::make_unique<ControlObject>(
            ConfigKey(QStringLiteral("[Test]"), QStringLiteral("persisted")), true, false, true);
    const quint64 before = inode(path);
    const QByteArray bytes = readAll(path);
    ConfigAutosave autosave(pConfig);
    autosave.start();
    pConfig->set(ConfigKey(QStringLiteral("[Test]"), QStringLiteral("existing")),
            ConfigValue(QStringLiteral("1")));
    spin(10000);
    check(saves() == 0, "no write in 10 s of idle");
    check(inode(path) == before && readAll(path) == bytes, "the file is untouched");
    autosave.stop();
    pPersist.reset();
    ControlDoublePrivate::setUserConfig(UserSettingsPointer());
    return failures;
}

int killed(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    UserSettingsPointer pConfig = makeConfig(directory, path);
    ConfigAutosave autosave(pConfig);
    autosave.start();
    spin(1200);
    pConfig->set(kKey, ConfigValue(QStringLiteral("survives-sigkill")));
    std::printf("SET\n");
    std::fflush(stdout);
    spin(60000); // the runner sends SIGKILL 3 s after SET
    return 1;
}

int readOnly(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    UserSettingsPointer pConfig = makeConfig(directory, path);
    ConfigAutosave autosave(pConfig);
    autosave.start();
    spin(1200);
    const QByteArray before = readAll(path);
    const QByteArray encoded = QFile::encodeName(directory);
    ::chmod(encoded.constData(), 0555);
    pConfig->set(kKey, ConfigValue(QStringLiteral("blocked")));
    spin(3500);
    check(readAll(path) == before, "the old file is byte-identical after a failed save");
    check(logged(QStringLiteral("Could not write")), "the failed save logs a warning");
    check(saves() == 0 && savedIndicator() == 0.0, "a failed save does not show Saved");
    check(QDir(directory).entryList(QDir::Files | QDir::Hidden | QDir::System) ==
                    QStringList{QStringLiteral("mixxx.cfg")},
            "no temporary file is left behind");
    ::chmod(encoded.constData(), 0755);
    check(waitFor(7500, [&] { return readAll(path).contains("\nkey blocked\n"); }),
            "the save is retried once the directory is writable again");
    return failures;
}

int persist(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    UserSettingsPointer pConfig = makeConfig(directory, path);
    ControlDoublePrivate::setUserConfig(pConfig);
    auto pPersist = std::make_unique<ControlObject>(
            ConfigKey(QStringLiteral("[Test]"), QStringLiteral("persisted")), true, false, true);
    auto pFresh = std::make_unique<ControlObject>(
            ConfigKey(QStringLiteral("[Test]"), QStringLiteral("fresh")), true, false, true, 0.25);
    auto pPlain = std::make_unique<ControlObject>(
            ConfigKey(QStringLiteral("[Test]"), QStringLiteral("plain")));
    check(pPersist->get() == 0.5, "a persist control starts from the file");
    pPlain->set(3.0);
    ConfigAutosave autosave(pConfig);
    autosave.start();
    spin(1200);
    pPersist->set(0.75);
    check(waitFor(3000, [&] { return readAll(path).contains("\npersisted 0.75\n"); }),
            "a persist control changed at run time is in the file after the autosave");
    const QByteArray autosaved = readAll(path);
    check(autosaved.contains("\nfresh 0.25\n"), "a persist control not yet in the file is added");
    check(!autosaved.contains("plain"), "a control without persist is not written");
    // Quit: the persist controls write themselves into the config when they
    // are destroyed, then CoreServices saves.
    autosave.stop();
    pPersist.reset();
    pFresh.reset();
    pPlain.reset();
    check(pConfig->save(), "the quit-time save succeeds");
    const QByteArray quit = readAll(path);
    std::printf("AUTOSAVED %s\nQUIT %s\n", autosaved.toPercentEncoding().constData(),
            quit.toPercentEncoding().constData());
    check(autosaved == quit,
            "the autosave has the same keys and values as the quit-time save of that state");
    ControlDoublePrivate::setUserConfig(UserSettingsPointer());
    return failures;
}

QByteArray bankWith(const QString& directory, const QHash<QString, QString>& locations) {
    // A bank file written by the shipped SamplerBank itself.
    UserSettingsPointer pConfig(new UserSettings(
            directory + QStringLiteral("/writer.cfg"), QStringLiteral("/res/"), directory));
    PlayerManager players(4);
    auto* pBank = new SamplerBank(pConfig, &players);
    for (auto it = locations.constBegin(); it != locations.constEnd(); ++it) {
        players.sampler(it.key())->load(std::make_shared<Track>(it.value()));
    }
    const QString path = directory + QStringLiteral("/samplers.xml");
    if (!pBank->saveSamplerBankToPath(path)) {
        qFatal("cannot write the bank");
    }
    QFile::remove(directory + QStringLiteral("/writer.cfg"));
    return readAll(path);
}

bool parses(const QByteArray& bytes) {
    QDomDocument document;
    return !bytes.isEmpty() && static_cast<bool>(document.setContent(bytes)) &&
            document.documentElement().tagName() == QStringLiteral("samplerbank");
}

int bank(const QString& directory) {
    const QString path = directory + QStringLiteral("/samplers.xml");
    UserSettingsPointer pConfig = makeConfig(directory, directory + QStringLiteral("/mixxx.cfg"));
    ConfigAutosave autosave(pConfig); // owns [MixPi],saved; not started
    PlayerManager players(4);
    auto* pBank = new SamplerBank(pConfig, &players);
    for (int i = 0; i < players.numberOfSamplers(); ++i) {
        pBank->watchSampler(players.getSampler(i));
    }
    players.sampler(QStringLiteral("[Sampler4]"))
            ->load(std::make_shared<Track>(QStringLiteral("/music/early.mp3")));
    spin(2000);
    check(!QFile::exists(path), "no bank write before the start-up load");
    pBank->loadSamplerBankAndAutosave(path);
    spin(300);
    QElapsedTimer timer;
    timer.start();
    players.slotLoadLocationToPlayer(
            QStringLiteral("/music/pad one.mp3"), QStringLiteral("[Sampler1]"), false);
    check(waitFor(3000, [&] { return readAll(path).contains("/music/pad one.mp3"); }),
            "samplers.xml holds a sample loaded to sampler 1 within 3 s");
    std::printf("BANK_WRITE_MS %lld\n", static_cast<long long>(timer.elapsed()));
    check(timer.elapsed() >= 900, "the bank waits 1 s after the load");
    check(parses(readAll(path)), "samplers.xml is a sampler bank");
    check(savedIndicator() == 1.0, "a bank write shows Saved");
    players.sampler(QStringLiteral("[Sampler1]"))->load(TrackPointer());
    check(waitFor(3000, [&] { return !readAll(path).contains("/music/pad one.mp3"); }),
            "an eject is saved within 3 s");
    check(parses(readAll(path)), "samplers.xml still parses after the eject");
    return failures;
}

int bankUnchanged(const QString& directory) {
    const QString path = directory + QStringLiteral("/samplers.xml");
    const QByteArray original = bankWith(directory,
            {{QStringLiteral("[Sampler1]"), QStringLiteral("/music/a.mp3")},
                    {QStringLiteral("[Sampler2]"), QStringLiteral("/music/b.mp3")}});
    const quint64 before = inode(path);
    UserSettingsPointer pConfig = makeConfig(directory, directory + QStringLiteral("/mixxx.cfg"));
    ConfigAutosave autosave(pConfig);
    PlayerManager players(4);
    auto* pBank = new SamplerBank(pConfig, &players);
    for (int i = 0; i < players.numberOfSamplers(); ++i) {
        pBank->watchSampler(players.getSampler(i));
    }
    pBank->loadSamplerBankAndAutosave(path);
    check(players.sampler(QStringLiteral("[Sampler2]"))->getLoadedTrack() != nullptr,
            "the start-up load fills the pads");
    spin(3000);
    check(inode(path) == before && readAll(path) == original,
            "loading the bank at start-up does not rewrite it");
    return failures;
}

int bankSlow(const QString& directory) {
    const QString path = directory + QStringLiteral("/samplers.xml");
    const QByteArray original = bankWith(directory,
            {{QStringLiteral("[Sampler1]"), QStringLiteral("/music/fast.mp3")},
                    {QStringLiteral("[Sampler2]"), QStringLiteral("/music/slow.mp3")}});
    const quint64 before = inode(path);
    UserSettingsPointer pConfig = makeConfig(directory, directory + QStringLiteral("/mixxx.cfg"));
    ConfigAutosave autosave(pConfig);
    PlayerManager players(4);
    players.libraryDelayMs.insert(QStringLiteral("/music/slow.mp3"), 4000);
    auto* pBank = new SamplerBank(pConfig, &players);
    for (int i = 0; i < players.numberOfSamplers(); ++i) {
        pBank->watchSampler(players.getSampler(i));
    }
    QElapsedTimer timer;
    timer.start();
    pBank->loadSamplerBankAndAutosave(path);
    spin(500);
    // The DJ loads pad 3 while pad 2 of the bank is still loading.
    players.slotLoadLocationToPlayer(
            QStringLiteral("/music/user.mp3"), QStringLiteral("[Sampler3]"), false);
    qint64 firstChange = -1;
    while (timer.elapsed() < 7000) {
        if (firstChange < 0 && (inode(path) != before || readAll(path) != original)) {
            firstChange = timer.elapsed();
        }
        spin(25);
    }
    std::printf("FIRST_CHANGE_MS %lld\n", static_cast<long long>(firstChange));
    check(firstChange < 0 || firstChange >= 4000,
            "no bank write before the slow start-up load ends");
    const QByteArray after = readAll(path);
    check(after.contains("/music/fast.mp3") && after.contains("/music/slow.mp3"),
            "the bank is intact after the slow load");
    check(after.contains("/music/user.mp3"), "the pad loaded during start-up is saved after it");
    check(parses(after), "samplers.xml parses");
    return failures;
}
#endif

} // namespace

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    runClock.start();
    qInstallMessageHandler(handler);
    if (argc < 3) {
        std::fprintf(stderr, "usage: %s MODE DIRECTORY\n", argv[0]);
        return 2;
    }
    const char* mode = argv[1];
    const QString directory = QString::fromLocal8Bit(argv[2]);
    int result = -1;
    if (std::strcmp(mode, "never-missing") == 0) {
        result = neverMissing(directory);
    }
#ifndef MIXPI_PINNED_SAVE
    const std::pair<const char*, int (*)(const QString&)> modes[] = {
            {"debounce", debounce},
            {"burst", burst},
            {"constant", constant},
            {"idle", idle},
            {"kill", killed},
            {"readonly", readOnly},
            {"persist", persist},
            {"bank", bank},
            {"bank-unchanged", bankUnchanged},
            {"bank-slow", bankSlow},
    };
    for (const auto& [name, function] : modes) {
        if (std::strcmp(mode, name) == 0) {
            result = function(directory);
        }
    }
#endif
    if (result < 0) {
        std::fprintf(stderr, "unknown mode %s\n", mode);
        return 2;
    }
    std::printf("FAILURES %d\n", failures);
    return failures == 0 ? 0 : 1;
}
