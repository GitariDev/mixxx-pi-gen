// Spec 2h (build M, wave J12; owner: "You should be able to press open to
// mount again so the safe to remove stays, but if you press open it goes back
// to a ready state"). A drive mounted and read, then ejected through the
// Media path (the real MixpiEjectEngine, MixpiMedia::startEject and
// ejectFinished): reads are refused and its row reads SAFE TO REMOVE. Then
// OPEN on that row: the drive is mounted again through udisks2 (the
// fixture's udisksctl, which logs its arguments and adds the drive's line to
// the fixture's mount table), its read generation takes reads again as a new
// round, the row reads READY and OPEN's normal read runs (the open source).
// Then a deck load (IN USE), EJECT again (reads refused again), a mount by
// hand, a pull (the drive goes), a failed mount, and a drive pulled while
// SAFE TO REMOVE (nothing is mounted). The other drive (IXIAN) is never
// touched.
//
// The shipped Media page (rows, chips, OPEN, EJECT, the strips), the eject
// engine, the read-generation registry and, with the patch, MixpiRemount,
// plus the actual MixpiMedia methods (tests/native/open_remount_runner.py
// copies them in). Stand-ins: the inventory (built from the fixture's mount
// table, as mixpi-media-inventory.py reports a drive), the players, the
// eject engine's drain hooks (the registry's real Drain, as engineHooks uses
// it; a fake drive has no kernel generation for observePath) and the open
// source (it records the volume and reads it as Library does).
// BASELINE is the source without mixxx-open-remount.patch.
#include <QApplication>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonObject>
#include <QLabel>
#include <QMap>
#include <QPointer>
#include <QPushButton>
#include <QSet>
#include <QTemporaryDir>
#include <QTest>
#include <iostream>
#include <memory>

#include "library/media/mediause.h"
#include "library/mixpimediapage.h"

// The mount table and udisks2 the production code uses.
QString kFixtureMountTable;
QString kFixtureUdisksctl;

#ifndef BASELINE
#include "library/mixpimediaremount.h"
#endif

// A mount table line ends with its source and its super options.
QByteArray tail(const QString& source) {
    QByteArray result(" ");
    result += source.toUtf8();
    result += " rw";
    return result;
}

int failures = 0;
void require(bool condition, const char* name) {
    std::cout << (condition ? "PASS " : "FAIL ") << name << std::endl;
    failures += !condition;
}

// The players, as describe reads them.
struct Track {
    QString location;
    QString getLocation() const {
        return location;
    }
    QString getTitle() const {
        return QFileInfo(location).baseName();
    }
};
using TrackPointer = std::shared_ptr<Track>;
class PlayerInfo {
  public:
    static PlayerInfo& instance() {
        static PlayerInfo info;
        return info;
    }
    QMap<QString, TrackPointer> getLoadedTracks() const {
        return loaded;
    }
    QMap<QString, TrackPointer> loaded;
};
struct ControlObject {
    double get() const {
        return 0;
    }
};
using WLabel = QLabel; // the skin Label (findChildren needs a Q_OBJECT class)
void mixpiClosePageToTracks(MixpiPage* page);
int tracksShown = 0;

const std::string kGander = "generation-GANDER1";
const std::string kIxian = "generation-IXIAN";

class MixpiMedia : public QObject {
  public:
    using OpenSource = std::function<std::function<void()>(const QJsonObject&, QObject*, std::function<void(QString)>)>;
    struct State {
        double value = 0;
        void setAndConfirm(double next) {
            value = next;
        }
    };

    MixpiMedia(QWidget* host, std::function<QJsonObject()> inventory, OpenSource openSource)
            : m_inventory(std::move(inventory)), m_openSource(std::move(openSource)) {
        m_page = new MixpiMediaPage(host, [](double) {});
        // As MixpiMedia::ensureWidgets wires the page.
        m_page->openRequested = [this](QString identity, QString token) { openVolume(identity, token); };
        m_page->ejectRequested = [this](QString identity) { startEject(identity); };
        m_page->visibilityChanged = [this](bool) { refresh(); };
        m_strip = new MixpiBottomStrip(host);
        m_handover = std::make_unique<MixpiHandover>([](const QString&, double) {});
        m_engine = new MixpiEjectEngine(engineHooks(), this);
        m_engine->finished = [this](bool ok, QString message) { ejectFinished(ok, message); };
#ifndef BASELINE
        m_remount = new MixpiRemount(remountHooks(), this);
#endif
    }

    // The eject engine's hooks as engineHooks sets them, with the registry's
    // real Drain on the drive's generation.
    MixpiEjectEngine::Hooks engineHooks() {
        MixpiEjectEngine::Hooks hooks;
        hooks.mustStopFirst = [this] {
            const auto* drive = currentDrive(m_ejectingIdentity);
            return !drive || mixpi_media::blocksEject(*drive);
        };
        hooks.beginDrain = [this] {
            const auto generation = m_ejectingIdentity == QStringLiteral("id-GANDER1") ? kGander : kIxian;
            m_drain = std::make_unique<mixxx::media::MediaUseRegistry::Drain>(
                    mixxx::media::registry().beginDrain(generation));
#ifndef BASELINE
            m_remount->drained({generation});
#endif
            return bool(*m_drain);
        };
        hooks.drainIdle = [this] { return m_drain && m_drain->snapshot().locallyIdle(); };
        hooks.cancelDrain = [this] { m_drain.reset(); };
        hooks.retire = [this] {
            const bool retired = m_drain && m_drain->retire();
            m_drain.reset();
#ifndef BASELINE
            m_remount->retired(m_ejectingIdentity, m_ejectVolumes, retired);
#endif
            return retired;
        };
        hooks.unmount = [this](const QString& source, MixpiEjectEngine::Done done) {
            unmounts.append(source);
            removeMount(source);
            QTimer::singleShot(0, this, [done] { done(true); });
        };
        hooks.stillMounted = [](const QString& device) {
            for (const auto& mount : mounts()) {
                if (mount.first == device) {
                    return true;
                }
            }
            return false;
        };
        return hooks;
    }

    static void removeMount(const QString& source) {
        QFile file(kFixtureMountTable);
        (void)file.open(QIODevice::ReadOnly);
        QByteArray kept;
        for (const auto& line : file.readAll().split('\n')) {
            if (!line.isEmpty() && !line.endsWith(tail(source))) {
                kept += line;
                kept += '\n';
            }
        }
        file.close();
        (void)file.open(QIODevice::WriteOnly | QIODevice::Truncate);
        file.write(kept);
    }

    // The inventory run: synchronous here; then what observeNow's callback
    // does after the snapshot (refresh, the auto loads, the ★ start and,
    // with the patch, openRemounted).
    void observeNow() {
        ++observations;
        m_snapshot = m_inventory();
        QSet<QString> present;
        for (const auto& value : m_snapshot.value("drives").toArray()) {
            present.insert(value.toObject().value("identity").toString());
        }
        m_present = present;
        refresh();
        runAutoLoads();
#ifndef BASELINE
        openRemounted();
#endif
    }

    QPointer<MixpiMediaPage> m_page;
    QPointer<MixpiBottomStrip> m_strip;
    std::function<void()> mountsChanged;
    QStringList unmounts;
    int observations = 0;

  private:
    bool ensureWidgets() {
        return true;
    }
    bool ejectAvailable() const {
        return true;
    }
    QWidget* window() const {
        return nullptr;
    }
    void refreshHandover() {
    }
    void runAutoLoads() {
    }
    static ControlObject* control(const QString&, const QString&) {
        return nullptr;
    }
    static bool servedFromCopy(const QString&) {
        return false;
    }
    static mixxx::rekordbox::SourceObservation inspectSelected(const QJsonObject&) {
        return {};
    }

  public:
#include "open_remount_media.inc"

  private:
    std::function<QJsonObject()> m_inventory;
    OpenSource m_openSource;
    std::unique_ptr<mixxx::media::MediaUseRegistry::Drain> m_drain;
    std::shared_ptr<QSet<QString>> m_opened = std::make_shared<QSet<QString>>();
    mutable QHash<QString, bool> m_rekordbox;
    std::unique_ptr<MixpiHandover> m_handover;
    std::unique_ptr<State> m_state = std::make_unique<State>();
    MixpiEjectEngine* m_engine = nullptr;
#ifndef BASELINE
    MixpiRemount* m_remount = nullptr;
#endif
    QJsonObject m_snapshot;
    QByteArray m_mounts;
    QString m_problem;
    QSet<QString> m_present;
    bool m_opening = false;
    std::function<void()> m_cancelOpen;
    QList<MixpiMediaDrive> m_drives;
    QString m_ejectingIdentity;
    QString m_safeIdentity;
    QString m_safeSysfs;
    QString m_safeName;
    QString m_safeDiskseq;
    QString m_ejectSysfs;
    QString m_ejectDiskseq;
    QString m_ejectName;
    QStringList m_ejectPaths;
    QList<MixpiMediaUser> m_ejectUsers;
    QList<MixpiEjectEngine::Volume> m_ejectVolumes;
    QString m_remounted;
    qint64 m_remountedSince = 0;
};

void mixpiClosePageToTracks(MixpiPage* page) {
    page->closePage();
    ++tracksShown;
}

// The fake drives: a sysfs node with its diskseq, a block device and a mount.
struct Drive {
    QString identity;
    QString label;
    QString device;
    QString source;
    QString sysfs;
    QString diskseq;
    std::string generation;
};

bool mounted(const Drive& drive) {
    QFile file(kFixtureMountTable);
    (void)file.open(QIODevice::ReadOnly);
    return file.readAll().contains(tail(drive.source));
}

int mountId(const Drive& drive) {
    QFile file(kFixtureMountTable);
    (void)file.open(QIODevice::ReadOnly);
    for (const auto& line : file.readAll().split('\n')) {
        if (line.endsWith(tail(drive.source))) {
            return line.split(' ').value(0).toInt();
        }
    }
    return 0;
}

int nextMount = 100;
void addMount(const Drive& drive) {
    QFile file(kFixtureMountTable);
    (void)file.open(QIODevice::Append);
    file.write(QStringLiteral("%1 25 %2 / /media/pi/%3 rw,nosuid - vfat %4 rw\n")
                    .arg(++nextMount)
                    .arg(drive.device, drive.label, drive.source)
                    .toUtf8());
}

QList<Drive> plugged;

// The inventory's volume token changes with the mount.
QString token(const Drive& drive) {
    return QString(drive.label + QString::number(mountId(drive)));
}

// The registry's round and retired flag (the patch adds them).
std::uint64_t roundOf(const std::string& generation) {
#ifdef BASELINE
    (void)generation;
    return 0;
#else
    return mixxx::media::registry().round(generation);
#endif
}
bool retiredNow(const std::string& generation) {
#ifdef BASELINE
    (void)generation;
    return true;
#else
    return mixxx::media::registry().retired(generation);
#endif
}

QJsonObject inventory() {
    QJsonArray drives;
    for (const auto& drive : std::as_const(plugged)) {
        QJsonArray volumes;
        if (mounted(drive)) {
            volumes.append(QJsonObject{{"token", token(drive)}, {"label", drive.label},
                    {"mount", QJsonObject{{"id", mountId(drive)}, {"device", drive.device}, {"root", "/"},
                                      {"path", QString(QStringLiteral("/media/pi/") + drive.label)}}},
                    {"physical", QJsonObject{{"sysfs", drive.sysfs}, {"diskseq", drive.diskseq}}}});
        }
        drives.append(QJsonObject{{"identity", drive.identity}, {"size", 16e9}, {"volumes", volumes}});
    }
    return QJsonObject{{"version", 1}, {"drives", drives}};
}

// Reads as Mixxx makes them: a deck load, a Folders tag read.
bool reads(const Drive& drive, mixxx::media::Producer producer) {
    return bool(mixxx::media::registry().acquire({drive.generation, "source-" + drive.generation, {}}, producer));
}

bool waitFor(const std::function<bool()>& condition, int ms = 5000) {
    QElapsedTimer timer;
    timer.start();
    while (!condition() && timer.elapsed() < ms) {
        QTest::qWait(10);
    }
    return condition();
}

QFrame* card(MixpiMediaPage* page, const QString& identity) {
    for (auto* found : page->findChildren<QFrame*>(QStringLiteral("MixpiMediaCard"))) {
        if (found->property("identity").toString() == identity && found->isVisibleTo(page)) {
            return found;
        }
    }
    return nullptr;
}

QString chip(MixpiMediaPage* page, const QString& identity) {
    auto* found = card(page, identity);
    auto* label = found ? found->findChild<QLabel*>(QStringLiteral("MixpiMediaChip")) : nullptr;
    return label ? label->text() : QString();
}

QPushButton* button(MixpiMediaPage* page, const QString& identity, const char* name) {
    auto* found = card(page, identity);
    return found ? found->findChild<QPushButton*>(QLatin1String(name)) : nullptr;
}

QString message(MixpiMediaPage* page, const QString& identity) {
    auto* found = card(page, identity);
    auto* label = found ? found->findChild<QLabel*>(QStringLiteral("MixpiMediaUse")) : nullptr;
    return label ? label->text() : QString();
}

QStringList logged(const QString& log) {
    QFile file(log);
    (void)file.open(QIODevice::ReadOnly);
    return QString::fromUtf8(file.readAll()).split(QLatin1Char('\n'), Qt::SkipEmptyParts);
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    QTemporaryDir root;
    kFixtureMountTable = root.filePath(QStringLiteral("mountinfo"));
    const QString log = root.filePath(QStringLiteral("udisksctl.log"));
    const QString failFlag = root.filePath(QStringLiteral("fail"));
    kFixtureUdisksctl = root.filePath(QStringLiteral("udisksctl"));
    // udisks2 as the fixture: log the call; "mount -b SOURCE" adds the
    // drive's line to the mount table (the device comes from SOURCE's name).
    {
        QFile script(kFixtureUdisksctl);
        (void)script.open(QIODevice::WriteOnly);
        script.write(QStringLiteral(
                "#!/bin/sh\n"
                "echo \"$*\" >> '%1'\n"
                "[ -e '%2' ] && exit 1\n"
                "[ \"$1\" = mount ] || exit 2\n"
                "device=$(cat \"%3/$(basename \"$3\").dev\") || exit 3\n"
                "label=$(cat \"%3/$(basename \"$3\").label\")\n"
                "echo \"$(( $(wc -l < '%4') + 200 )) 25 $device / /media/pi/$label rw,nosuid - vfat $3 rw\" >> '%4'\n")
                             .arg(log, failFlag, root.path(), kFixtureMountTable)
                             .toUtf8());
        script.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner);
    }
    const auto makeDrive = [&](const QString& label, const QString& device, const QString& source,
                                   const QString& diskseq, const std::string& generation) {
        Drive drive{QString(QStringLiteral("id-") + label), label, device, source,
                root.filePath(QString(QStringLiteral("sys-") + label)), diskseq, generation};
        QDir().mkpath(drive.sysfs);
        QFile sequence(QString(drive.sysfs + QStringLiteral("/diskseq")));
        (void)sequence.open(QIODevice::WriteOnly);
        sequence.write(diskseq.toUtf8());
        sequence.write("\n");
        const QString base = QFileInfo(source).fileName();
        QFile dev(root.filePath(QString(base + QStringLiteral(".dev"))));
        (void)dev.open(QIODevice::WriteOnly);
        dev.write(device.toUtf8());
        QFile name(root.filePath(QString(base + QStringLiteral(".label"))));
        (void)name.open(QIODevice::WriteOnly);
        name.write(label.toUtf8());
        return drive;
    };
    {
        QFile table(kFixtureMountTable);
        (void)table.open(QIODevice::WriteOnly);
    }
    const Drive gander = makeDrive(QStringLiteral("GANDER1"), QStringLiteral("8:1"), QStringLiteral("/dev/sdz1"),
            QStringLiteral("7"), kGander);
    const Drive ixian = makeDrive(QStringLiteral("IXIAN"), QStringLiteral("8:17"), QStringLiteral("/dev/sdy1"),
            QStringLiteral("9"), kIxian);
    plugged = {gander, ixian};
    addMount(gander);
    addMount(ixian);

    QWidget host;
    host.resize(800, 480);
    host.show();
    QStringList opened;           // the open source: the volume tokens it read
    QList<bool> openReads;        // and whether its read was allowed
    MixpiMedia media(&host, inventory,
            [&](const QJsonObject& volume, QObject* receiver, std::function<void(QString)> done) {
                opened.append(volume.value("token").toString());
                const auto& drive = volume.value("label").toString() == gander.label ? gander : ixian;
                const bool allowed = reads(drive, mixxx::media::Producer::Import);
                openReads.append(allowed);
                QTimer::singleShot(0, receiver, [done, allowed] {
                    done(allowed ? QString() : QStringLiteral("No SoundSourceProvider"));
                });
                return std::function<void()>();
            });
    media.tick();
    media.m_page->open();
    QApplication::processEvents();
    auto* page = media.m_page.data();

    require(chip(page, gander.identity) == "READY" && reads(gander, mixxx::media::Producer::Load) &&
                    reads(gander, mixxx::media::Producer::Metadata),
            "GANDER1 mounted: READY, and its tracks and tags read");
    require(reads(ixian, mixxx::media::Producer::Load) && chip(page, ixian.identity) == "READY",
            "IXIAN mounted: READY and read");

    // Eject through the Media path (the sheet's EJECT calls ejectRequested).
    page->ejectRequested(gander.identity);
    waitFor([&] { return chip(page, gander.identity) == "SAFE TO REMOVE"; });
    require(media.unmounts == QStringList{gander.source} && !mounted(gander),
            "eject: GANDER1's volume unmounted through udisks2");
    require(!reads(gander, mixxx::media::Producer::Load) && !reads(gander, mixxx::media::Producer::Metadata),
            "eject: GANDER1's reads are refused (its generation is retired)");
    require(chip(page, gander.identity) == "SAFE TO REMOVE", "eject: GANDER1's row reads SAFE TO REMOVE");
    auto* open = button(page, gander.identity, "MixpiMediaOpen");
    require(open && open->text() == "OPEN", "eject: the SAFE TO REMOVE row keeps its OPEN button");
    require(open && open->isEnabled(), "eject: OPEN on the SAFE TO REMOVE row can be tapped");
    require(button(page, gander.identity, "MixpiMediaEject") &&
                    !button(page, gander.identity, "MixpiMediaEject")->isEnabled(),
            "eject: EJECT on the SAFE TO REMOVE row stays off");
    require(reads(ixian, mixxx::media::Producer::Load) && chip(page, ixian.identity) == "READY",
            "eject: IXIAN still reads and reads READY");

    // A failed mount: nothing reopens, the row stays SAFE TO REMOVE.
    {
        QFile flag(failFlag);
        (void)flag.open(QIODevice::WriteOnly);
    }
    if (open) {
        open->click();
    }
    waitFor([&] { return !message(page, gander.identity).isEmpty() &&
                         message(page, gander.identity) != QStringLiteral("Opening the drive…"); });
    require(logged(log) == QStringList{"mount -b /dev/sdz1 --no-user-interaction"},
            "OPEN asks udisks2 to mount the drive's volume (mount -b /dev/sdz1 --no-user-interaction)");
    require(!mounted(gander) && !reads(gander, mixxx::media::Producer::Load) &&
                    chip(page, gander.identity) == "SAFE TO REMOVE" && opened.isEmpty(),
            "a failed mount: reads stay refused, the row stays SAFE TO REMOVE, nothing opens");
    require(message(page, gander.identity) == QStringLiteral("This drive changed or could not be checked."),
            "a failed mount: the row says so in build B's words");
    QFile::remove(failFlag);
    QFile::remove(log);
    // Build B keeps an OPEN error on the page, with OPEN off, until the next
    // open's completion clears it (setOpening({}, {})); as that does here.
    page->setOpening({}, {});

    // OPEN on the SAFE TO REMOVE row: mounted again, a new round, READY, read.
    open = button(page, gander.identity, "MixpiMediaOpen");
    if (open) {
        open->click();
    }
    waitFor([&] { return !opened.isEmpty() && tracksShown > 0; });
    require(logged(log) == QStringList{"mount -b /dev/sdz1 --no-user-interaction"} && mounted(gander),
            "OPEN: GANDER1 is mounted again through udisks2 (no re-plug)");
    require(roundOf(kGander) == 1 && !retiredNow(kGander),
            "OPEN: GANDER1's read generation reopens as a new round");
    require(reads(gander, mixxx::media::Producer::Load), "OPEN: GANDER1's tracks load to decks again");
    require(reads(gander, mixxx::media::Producer::Metadata), "OPEN: Folders reads GANDER1's full tags again");
    require(opened.size() == 1 && opened.first() == token(gander) &&
                    openReads.value(0),
            "OPEN: OPEN's normal read of the remounted volume runs");
    require(tracksShown == 1 && !page->isVisible(), "OPEN: the page switches to Tracks");
    media.m_page->open();
    QApplication::processEvents();
    require(chip(page, gander.identity) == "READY", "OPEN: GANDER1's row reads READY");
    require(button(page, gander.identity, "MixpiMediaOpen") &&
                    button(page, gander.identity, "MixpiMediaOpen")->text() == "BROWSE",
            "OPEN: the button then reads BROWSE");
    require(button(page, gander.identity, "MixpiMediaEject") &&
                    button(page, gander.identity, "MixpiMediaEject")->isEnabled(),
            "OPEN: EJECT works on the row again");
    require(!media.m_strip->isVisible(), "OPEN: the SAFE TO REMOVE strip goes");
    require(roundOf(kIxian) == 0 && reads(ixian, mixxx::media::Producer::Load) &&
                    chip(page, ixian.identity) == "READY",
            "OPEN: IXIAN is not touched");

    // A track from GANDER1 on deck 1: IN USE, as the chip rules say.
    PlayerInfo::instance().loaded.insert(QStringLiteral("[Channel1]"),
            std::make_shared<Track>(Track{QStringLiteral("/media/pi/GANDER1/Music/a.mp3")}));
    media.refresh();
    QApplication::processEvents();
    require(chip(page, gander.identity) == "IN USE", "after OPEN: a GANDER1 track on deck 1 reads IN USE");
    PlayerInfo::instance().loaded.clear();
    media.refresh();
    QApplication::processEvents();

    // EJECT again: its clean eject, reads refused again.
    page->ejectRequested(gander.identity);
    waitFor([&] { return chip(page, gander.identity) == "SAFE TO REMOVE"; });
    require(media.unmounts.size() == 2 && !mounted(gander) && chip(page, gander.identity) == "SAFE TO REMOVE",
            "EJECT after the remount: a clean eject, SAFE TO REMOVE");
    require(!reads(gander, mixxx::media::Producer::Load) && !reads(gander, mixxx::media::Producer::Metadata),
            "EJECT after the remount: reads are refused again");

    // Mounted again by hand meanwhile: OPEN does not mount twice.
    QFile::remove(log);
    addMount(gander);
    open = button(page, gander.identity, "MixpiMediaOpen");
    if (open) {
        open->click();
    }
    waitFor([&] { return opened.size() >= 2 && tracksShown == 2; });
    require(logged(log).isEmpty() && roundOf(kGander) == 2 &&
                    reads(gander, mixxx::media::Producer::Load),
            "OPEN on a drive mounted by hand: no second mount, a new round, reads allowed");

    // A pull after the remount removes the drive.
    MixpiMedia::removeMount(gander.source);
    QFile::remove(QString(gander.sysfs + QStringLiteral("/diskseq")));
    plugged = {ixian};
    media.tick();
    media.m_page->open();
    QApplication::processEvents();
    require(!card(page, gander.identity) && card(page, ixian.identity),
            "a pull after the remount: GANDER1's row goes, IXIAN stays");

    // IXIAN ejected, then pulled before OPEN: nothing is mounted.
    QFile::remove(log);
    page->ejectRequested(ixian.identity);
    waitFor([&] { return chip(page, ixian.identity) == "SAFE TO REMOVE"; });
    require(!reads(ixian, mixxx::media::Producer::Load) && chip(page, ixian.identity) == "SAFE TO REMOVE",
            "IXIAN ejected: reads refused, SAFE TO REMOVE");
    QFile::remove(QString(ixian.sysfs + QStringLiteral("/diskseq")));
    open = button(page, ixian.identity, "MixpiMediaOpen");
    if (open) {
        open->click();
    }
    QTest::qWait(300);
    require(logged(log).isEmpty() && !mounted(ixian) && !reads(ixian, mixxx::media::Producer::Load),
            "OPEN on a drive pulled while SAFE TO REMOVE: nothing is mounted, reads stay refused");
    plugged = {};
    media.tick();
    QApplication::processEvents();
    require(!card(page, ixian.identity), "the pulled drive's row goes at the next check");

    // Nothing was written to a drive: only udisks2 mount calls, no other file.
    const QStringList files = QDir(root.path()).entryList(QDir::Files);
    require(QSet<QString>(files.begin(), files.end()) ==
                    QSet<QString>{"mountinfo", "udisksctl", "sdz1.dev", "sdz1.label", "sdy1.dev", "sdy1.label"},
            "nothing was written but the fixture's own files");
    std::cout << "OK " << failures << std::endl;
    return failures ? 1 : 0;
}
