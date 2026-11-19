// Build I, wave I2 (mixxx-media-chip-ping.patch, spec 2d): the USB chip's
// IN USE timing and the plug-in ping on the Media page, with the shipped
// MixpiMediaPage, MixpiBottomStrip and mixpi_media helpers, fake drives, fake
// players and the real stylesheets.
//
// The players: MixpiMedia::describe() lists as a drive's users the players
// whose loaded track lives under one of the drive's mount paths
// (PlayerInfo::getLoadedTracks()), then takes the state from idleState().
// Here a map from group to location stands in for PlayerInfo and the same
// path test (mixpi_media::fromUsb) picks the users.
//
// usage: media-chip-ping-test [RENDER_DIRECTORY]
#include <QApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFontDatabase>
#include <QMainWindow>
#include <QMap>
#include <QTest>
#include <iostream>

#include "library/mixpimediapage.h"

namespace {
int failures = 0;
int checks = 0;
QString renders;

void check(bool condition, const std::string& message) {
    ++checks;
    if (!condition) {
        ++failures;
        std::cout << "FAIL " << message << '\n';
    } else {
        std::cout << "PASS " << message << '\n';
    }
}

void settle(int milliseconds = 0) {
    QElapsedTimer timer;
    timer.start();
    do {
        QApplication::processEvents(QEventLoop::AllEvents, 10);
    } while (timer.elapsed() < milliseconds);
}

QString styleSheet() {
    QString style;
    for (const auto& path : qEnvironmentVariable("MIXPI_SKIN_QSS").split(':', Qt::SkipEmptyParts)) {
        QFile file(path);
        if (file.open(QIODevice::ReadOnly)) {
            style += QString::fromUtf8(file.readAll()) + QLatin1Char('\n');
        }
    }
    return style;
}

void save(QWidget* widget, const QString& name) {
    if (!renders.isEmpty()) {
        widget->grab().save(QDir(renders).filePath(name));
    }
}

// PlayerInfo stand-in: group -> location of the loaded track.
QMap<QString, QString> players;

struct FakeDrive {
    QString name;
    bool opened = false; // OPEN or BROWSE in this session
    bool busy = false;   // the library reads its export or lists right now
};

QString mountPath(const QString& name) {
    return QStringLiteral("/media/pi/") + name;
}

MixpiMediaDrive describe(const FakeDrive& fake) {
    MixpiMediaDrive result;
    result.identity = QStringLiteral("identity-") + fake.name;
    result.name = fake.name;
    result.size = 32000000000LL;
    result.rekordbox = true;
    result.opened = fake.opened;
    result.busy = fake.busy;
    result.volumes.append({QStringLiteral("token-") + fake.name, fake.name, mountPath(fake.name), fake.opened});
    for (auto it = players.constBegin(); it != players.constEnd(); ++it) {
        if (mixpi_media::fromUsb(it.value(), {mountPath(fake.name)}, false)) {
            result.users.append({it.key(), QFileInfo(it.value()).fileName(), false, true});
        }
    }
    result.state = mixpi_media::idleState(result);
    return result;
}

std::string word(MixpiMediaState state) {
    return mixpi_media::stateWord(state).toStdString();
}

QList<QFrame*> cards(MixpiMediaPage& page) {
    auto* list = page.findChild<QScrollArea*>(QStringLiteral("MixpiMediaDrives"));
    return list && list->widget() ? list->widget()->findChildren<QFrame*>(QStringLiteral("MixpiMediaCard"))
                                  : QList<QFrame*>();
}

QString chipOf(MixpiMediaPage& page, const QString& name) {
    for (auto* card : cards(page)) {
        if (card->property("identity").toString() == QStringLiteral("identity-") + name) {
            auto* chip = card->findChild<QLabel*>(QStringLiteral("MixpiMediaChip"));
            return chip ? chip->text() : QString();
        }
    }
    return {};
}

// The widget a finger lands on at this point of the window.
QWidget* under(QWidget* root, QWidget* target) {
    const QPoint centre = target->mapTo(root, QPoint(target->width() / 2, target->height() / 2));
    return root->childAt(centre);
}

void stateChecks() {
    const FakeDrive spare{QStringLiteral("SPARE"), true, true};
    players.clear();

    // OPEN (or BROWSE) alone, with the library still reading its export.
    auto drive = describe(spare);
    check(drive.state == MixpiMediaState::Ready && mixpi_media::chipState({drive}) == MixpiMediaState::Ready,
            "open: an opened drive with nothing loaded reads READY (" + word(drive.state) + ")");

    players.insert(QStringLiteral("[Channel1]"), mountPath(QStringLiteral("SPARE")) + QStringLiteral("/Contents/a.mp3"));
    drive = describe(spare);
    check(drive.state == MixpiMediaState::InUse && mixpi_media::chipState({drive}) == MixpiMediaState::InUse,
            "deck: a track from the drive on deck 1 reads IN USE (" + word(drive.state) + ")");

    players.insert(QStringLiteral("[Channel1]"), QString()); // deck 1 ejected
    drive = describe(spare);
    check(drive.state == MixpiMediaState::Ready, "deck: ejecting deck 1's track reads READY (" + word(drive.state) + ")");

    players.insert(QStringLiteral("[Channel1]"), mountPath(QStringLiteral("SPARE")) + QStringLiteral("/Contents/a.mp3"));
    players.insert(QStringLiteral("[Channel1]"), QStringLiteral("/home/pi/Music/This Pi.mp3"));
    drive = describe(spare);
    check(drive.state == MixpiMediaState::Ready,
            "deck: a This Pi track loaded over it reads READY (" + word(drive.state) + ")");

    players.insert(QStringLiteral("[Sampler3]"), mountPath(QStringLiteral("SPARE")) + QStringLiteral("/Samples/kick.wav"));
    drive = describe(spare);
    check(drive.state == MixpiMediaState::InUse, "pad: a sample from the drive on pad 3 reads IN USE (" +
                    word(drive.state) + ")");

    players.remove(QStringLiteral("[Sampler3]")); // pad 3 cleared
    drive = describe(spare);
    check(drive.state == MixpiMediaState::Ready, "pad: clearing pad 3 reads READY (" + word(drive.state) + ")");

    players.insert(QStringLiteral("[PreviewDeck1]"), mountPath(QStringLiteral("SPARE")) + QStringLiteral("/b.mp3"));
    drive = describe(spare);
    check(drive.state == MixpiMediaState::Ready && drive.users.size() == 1,
            "browse: a track in the library's preview player only leaves it READY (" + word(drive.state) + ")");
    players.clear();

    // Two drives, each on its own.
    const FakeDrive mantacore{QStringLiteral("MANTACORE"), true, false};
    players.insert(QStringLiteral("[Channel2]"),
            mountPath(QStringLiteral("MANTACORE")) + QStringLiteral("/Contents/b.mp3"));
    auto first = describe(mantacore);
    auto second = describe(spare);
    check(first.state == MixpiMediaState::InUse && second.state == MixpiMediaState::Ready &&
                    mixpi_media::chipName({second, first}) == QStringLiteral("MANTACORE"),
            "two drives: deck 2 from MANTACORE: MANTACORE IN USE, SPARE READY, the chip shows MANTACORE");
    players.insert(QStringLiteral("[Sampler1]"), mountPath(QStringLiteral("SPARE")) + QStringLiteral("/Samples/c.wav"));
    first = describe(mantacore);
    second = describe(spare);
    check(first.state == MixpiMediaState::InUse && second.state == MixpiMediaState::InUse,
            "two drives: pad 1 from SPARE as well: both IN USE");
    players.remove(QStringLiteral("[Channel2]"));
    first = describe(mantacore);
    second = describe(spare);
    check(first.state == MixpiMediaState::Ready && second.state == MixpiMediaState::InUse &&
                    mixpi_media::chipName({first, second}) == QStringLiteral("SPARE"),
            "two drives: deck 2 ejected: MANTACORE READY, SPARE still IN USE");
    players.clear();
}

void pageChecks(QMainWindow& window, QWidget* root) {
    // As MixpiMedia::ensureWidgets(): the page first, then the strip.
    MixpiMediaPage page(root, [](double) {});
    MixpiBottomStrip strip(root);
    QStringList loads;
    const auto load = [&](QString identity) { loads.append(identity); };
    strip.loadRequested = load;

    // The page's rows and filter follow the same state.
    const FakeDrive mantacore{QStringLiteral("MANTACORE"), true, false};
    players.insert(QStringLiteral("[Channel1]"),
            mountPath(QStringLiteral("MANTACORE")) + QStringLiteral("/Contents/a.mp3"));
    page.open();
    page.setDrives({describe(mantacore)});
    settle();
    check(chipOf(page, QStringLiteral("MANTACORE")) == QStringLiteral("IN USE"),
            "page: the row of a drive with a deck loaded from it reads IN USE");
    players.clear();
    page.setDrives({describe(mantacore)});
    settle();
    check(chipOf(page, QStringLiteral("MANTACORE")) == QStringLiteral("READY") &&
                    cards(page).first()->findChild<QPushButton*>(QStringLiteral("MixpiMediaOpen"))->text() ==
                            QStringLiteral("BROWSE"),
            "page: an opened drive with nothing loaded reads READY, and its button BROWSE");

    // ASK: a drive plugged in while the Media page is open gets the ping.
    check(page.isVisible() && mixpi_media::shouldPing(true, false, false, true, false, page.isVisible()),
            "ping: a new drive is pinged while the Media page is open");
    const bool loaded = mixpiDriveInserted(&strip, 0, QStringLiteral("identity-SPARE"), QStringLiteral("SPARE"),
            QStringLiteral("rekordbox export found · 32.0 GB"), load);
    // MixpiMedia::refresh() then gives the open page the new drive's row.
    const FakeDrive spare{QStringLiteral("SPARE")};
    page.setDrives({describe(mantacore), describe(spare)});
    settle(200);
    auto* loadButton = strip.findChild<QPushButton*>(QStringLiteral("MixpiStripLoad"));
    auto* dismiss = strip.findChild<QPushButton*>(QStringLiteral("MixpiStripDismiss"));
    check(!loaded && loads.isEmpty() && strip.isVisible() && strip.kind() == MixpiBottomStrip::Kind::Ping &&
                    loadButton->isVisible() && dismiss->isVisible(),
            "ping: ASK shows LOAD and DISMISS over the Media page");
    check(strip.geometry() == QRect(0, 424, 800, 56), "ping: in the same place as on other screens, the bottom 56 px");
    check(under(root, loadButton) == loadButton && under(root, dismiss) == dismiss,
            "ping: LOAD and DISMISS are on top of the page, where a tap lands");
    check(chipOf(page, QStringLiteral("SPARE")) == QStringLiteral("READY") && cards(page).size() == 2,
            "ping: the page's own row for the new drive shows too, READY");
    save(&window, QStringLiteral("i2-ping-over-media.png"));
    QTest::mouseClick(loadButton, Qt::LeftButton);
    settle();
    check(loads == QStringList({QStringLiteral("identity-SPARE")}) && !strip.isVisible(),
            "ping: LOAD over the page opens that drive, as on other screens");
    loads.clear();

    // A ping that is up when the Media page opens stays on top of it.
    page.closePage();
    mixpiDriveInserted(&strip, 0, QStringLiteral("identity-KINGSTON"), QStringLiteral("KINGSTON"),
            QStringLiteral("folders · 16.0 GB"), load);
    settle();
    page.openSoon();
    settle(MixpiPage::kRepaintMs + 100);
    check(page.isVisible() && strip.isVisible() && under(root, loadButton) == loadButton,
            "ping: a ping already up stays on top when the Media page opens");
    strip.dismiss();
    settle();
    check(!strip.isVisible() && page.isVisible(), "ping: DISMISS leaves the Media page as it was");

    // AUTO LOAD: nothing changes, no ping, the drive opens at once.
    const bool autoLoaded = mixpiDriveInserted(&strip, 1, QStringLiteral("identity-KINGSTON"),
            QStringLiteral("KINGSTON"), QStringLiteral("folders · 16.0 GB"), load);
    settle();
    check(autoLoaded && loads == QStringList({QStringLiteral("identity-KINGSTON")}) && !strip.isVisible() &&
                    strip.kind() == MixpiBottomStrip::Kind::None,
            "ping: AUTO LOAD with the Media page open loads at once with no ping");
    page.closePage();
}
} // namespace

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    renders = argc > 1 ? QString::fromLocal8Bit(argv[1]) : QString();
    if (!renders.isEmpty()) {
        QDir().mkpath(renders);
    }
    for (const auto& font : qEnvironmentVariable("MIXPI_FONTS").split(':', Qt::SkipEmptyParts)) {
        QFontDatabase::addApplicationFont(font);
    }
    const QString style = styleSheet();
    check(style.contains(QStringLiteral("#MixpiMediaFilterOption")), "style: mixpi-media-page.qss is loaded");
    QMainWindow window;
    auto* root = new QWidget;
    root->setObjectName(QStringLiteral("SkinRootDouble"));
    root->setStyleSheet(style + QStringLiteral("\n#SkinRootDouble { background-color: #0d1014; }"));
    window.setCentralWidget(root);
    window.resize(800, 480);
    window.show();
    settle();
    stateChecks();
    pageChecks(window, root);
    std::cout << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
