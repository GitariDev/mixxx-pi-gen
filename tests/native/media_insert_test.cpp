// U-8 (mixxx-media-agreed.patch): [MixPi],drive_insert, made by the shipped
// mixpiNewDriveInsertControl() with the shipped control framework and save on
// change (ConfigAutosave). It is read from mixxx.cfg at start, defaults to
// ASK (0), and a change is in mixxx.cfg within a second or so, like every
// MixPi setting.
//
// usage: media-insert-test DIRECTORY first|next|third
// Each start runs in its own process, as Mixxx starts do.
#include <QApplication>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QTimer>
#include <cstdio>
#include <functional>
#include <memory>

#include "control/control.h"
#include "control/controlobject.h"
#include "library/mixpidriveinsert.h"
#include "preferences/usersettings.h"

namespace {
int failures = 0;

void check(bool ok, const std::string& name) {
    std::printf("%s %s\n", ok ? "PASS" : "FAIL", name.c_str());
    std::fflush(stdout);
    if (!ok) {
        std::fprintf(stderr, "FAIL %s\n", name.c_str());
        ++failures;
    }
}

void spin(int ms) {
    QEventLoop loop;
    QTimer::singleShot(ms, &loop, &QEventLoop::quit);
    loop.exec();
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

// Milliseconds until the condition holds, or -1 after maxMs.
qint64 waitFor(int maxMs, const std::function<bool()>& condition) {
    QElapsedTimer timer;
    timer.start();
    while (!condition()) {
        if (timer.elapsed() > maxMs) {
            return -1;
        }
        spin(10);
    }
    return timer.elapsed();
}

// One start of Mixxx: a config from the file, the control, the autosave.
void start(const QString& directory, const QString& path, double expected, const std::string& when,
        const std::function<void(ControlObject*, mixxx::ConfigAutosave&)>& body) {
    UserSettingsPointer config(new UserSettings(path, QStringLiteral("/res/"), directory));
    ControlDoublePrivate::setUserConfig(config);
    std::unique_ptr<ControlObject> control(mixpiNewDriveInsertControl());
    check(control->get() == expected, when + ": drive_insert starts at " + std::to_string(static_cast<int>(expected)));
    mixxx::ConfigAutosave autosave(config);
    autosave.start();
    body(control.get(), autosave);
    autosave.stop();
    control.reset();
    config->save();
    ControlDoublePrivate::setUserConfig(UserSettingsPointer());
}
} // namespace

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    if (argc < 3) {
        std::fprintf(stderr, "usage: %s DIRECTORY first|next|third\n", argv[0]);
        return 2;
    }
    const QString directory = QString::fromLocal8Bit(argv[1]);
    const QByteArray mode(argv[2]);
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    check(mixpiDriveInsertKey() == ConfigKey(QStringLiteral("[MixPi]"), QStringLiteral("drive_insert")),
            "the key is [MixPi],drive_insert");
    if (mode == "first") {
        // A card that has never set it: ASK.
        writeAll(path, QByteArrayLiteral("\n[MixPi]\nRamCacheMB 1024\n"));
        start(directory, path, 0, "first start", [&](ControlObject* control, mixxx::ConfigAutosave&) {
            spin(600);
            control->set(1);
            const qint64 elapsed = waitFor(3000, [&] { return readAll(path).contains("\ndrive_insert 1\n"); });
            std::printf("SAVED_AFTER_MS %lld\n", static_cast<long long>(elapsed));
            check(elapsed >= 0 && elapsed <= 1600,
                    "AUTO LOAD is in mixxx.cfg within a second or so of the change (" + std::to_string(elapsed) +
                            " ms)");
            check(readAll(path).contains("\nRamCacheMB 1024\n"), "the other MixPi settings stay");
        });
    } else if (mode == "next") {
        // The next start reads AUTO LOAD back; ASK is saved back the same way.
        start(directory, path, 1, "next start", [&](ControlObject* control, mixxx::ConfigAutosave&) {
            spin(600);
            control->set(0);
            const qint64 elapsed = waitFor(3000, [&] { return readAll(path).contains("\ndrive_insert 0\n"); });
            check(elapsed >= 0 && elapsed <= 1600, "ASK is saved back too (" + std::to_string(elapsed) + " ms)");
        });
    } else if (mode == "third") {
        start(directory, path, 0, "third start", [](ControlObject*, mixxx::ConfigAutosave&) {});
    } else {
        std::fprintf(stderr, "unknown mode\n");
        return 2;
    }
    std::printf("FAILURES %d\n", failures);
    return failures == 0 ? 0 : 1;
}
