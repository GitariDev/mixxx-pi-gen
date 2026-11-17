#include <QApplication>
#include <QDir>
#include <QImage>
#include <QLabel>
#include <QLineEdit>
#include <QMainWindow>
#include <QProgressBar>
#include <QPushButton>
#include <QTemporaryDir>
#include <QTest>
#include <QVBoxLayout>
#include <algorithm>
#include <iostream>
#include <memory>
#include <stdexcept>

#include "control/controlobject.h"
#include "library_scanner_strip_doubles.h"
#define CHECK(x) do { if (!(x)) throw std::runtime_error(#x); } while (false)

std::chrono::milliseconds g_fakeNow{0};

static void advance() {
    g_fakeNow += std::chrono::milliseconds(2500);
}

// The strip checks [MixPi],screen every 250 ms while a scan runs.
static void watch() {
    QTest::qWait(400);
}

LibraryScanner::LibraryScanner(const UserSettingsPointer& pConfig) {
#include "scanner_wiring.inc"
}

// R-12: two names in a row leave no pixels of the first. The label is
// painted over what the screen already shows (no window background), as
// when the strip updates in place on the Pi.
static bool repaintLeavesNoOldPixels(QLabel* status, const QString& first, const QString& second) {
    QImage canvas(status->size(), QImage::Format_ARGB32);
    canvas.fill(Qt::transparent);
    status->setText(first);
    status->render(&canvas, {}, {}, QWidget::DrawChildren);
    status->setText(second);
    status->render(&canvas, {}, {}, QWidget::DrawChildren);
    QImage fresh(status->size(), QImage::Format_ARGB32);
    fresh.fill(Qt::transparent);
    status->render(&fresh, {}, {}, QWidget::DrawChildren);
    return canvas == fresh;
}

static void percentChecks(LibraryScanner& scanner, ControlObject* active, ControlObject* percent,
        QProgressBar* progress, QLabel* percentLabel) {
    // A fake music folder of 10 folders: the root and 9 below it.
    QTemporaryDir music;
    CHECK(music.isValid());
    QDir root(music.path());
    for (const char* name : {"A", "A/One", "A/Two", "B", "B/Three", "C", "D", "E", "E/Four"}) {
        CHECK(root.mkpath(name));
    }
    CHECK(root.mkpath(".hidden"));  // not scanned, not counted
    const int folders = mixpi::countScanFolders({music.path(), music.path() + "/missing"});
    std::cout << "OBSERVE counted " << folders << " folders" << std::endl;
    CHECK(folders == 10);

    emit scanner.scanStarted();
    CHECK(active->get() == 1 && percent->get() == 0);
    mixpi::ScanPercent counter;
    counter.start(folders);
    emit scanner.progressPercent(0);
    QList<double> seen{percent->get()};
    for (int done = 0; done < folders; ++done) {
        if (counter.folderDone()) {
            emit scanner.progressPercent(counter.value());
        }
        seen.append(percent->get());
        if (done == 5) {
            // A late, lower number never moves the percent down.
            emit scanner.progressPercent(10);
            seen.append(percent->get());
        }
    }
    std::cout << "OBSERVE percent";
    for (double value : seen) {
        std::cout << ' ' << value;
    }
    std::cout << std::endl;
    CHECK(seen.first() == 0 && seen.last() == 99);
    CHECK(std::is_sorted(seen.begin(), seen.end()));
    CHECK(counter.value() == 99 && !counter.folderDone());
    CHECK(progress->value() == 99 && percentLabel->text() == "99%");
    emit scanner.progressPercent(250);
    CHECK(percent->get() == 99);
    emit scanner.scanFinished();
    CHECK(active->get() == 0 && percent->get() == 100);
    emit scanner.progressPercent(42);
    CHECK(percent->get() == 100);
    // Nothing counted: the percent stays 0 until the scan finishes.
    mixpi::ScanPercent empty;
    empty.start(0);
    CHECK(!empty.folderDone() && empty.value() == 0);
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    try {
        CHECK(mixpi::scanItemName("/home/pi/Music/Backup/x/Beautiful.mp3") == "Beautiful.mp3");
        CHECK(mixpi::scanItemName("/home/pi/Music/Backup/Artist/") == "Artist");

        QMainWindow window;
        auto* central = new QWidget;
        auto* layout = new QVBoxLayout(central);
        auto* other = new QPushButton("Deck");
        auto* edit = new QLineEdit;
        auto* play = new QPushButton("Play");
        play->setFixedHeight(48);
        play->setFocusPolicy(Qt::NoFocus);  // as the skin's transport buttons
        int otherClicks = 0;
        int playClicks = 0;
        QObject::connect(other, &QPushButton::clicked, [&] { ++otherClicks; });
        QObject::connect(play, &QPushButton::clicked, [&] { ++playClicks; });
        layout->setContentsMargins(0, 0, 0, 4);
        layout->addWidget(other);
        layout->addWidget(edit);
        layout->addStretch();
        layout->addWidget(play);  // the transport row: y 428-476 in 480
        window.setCentralWidget(central);
        window.resize(800, 480);
        window.show();
        app.processEvents();
        edit->setFocus();
        app.processEvents();

        // The skin's screen control: 0 none, 1 Sources, ...
        ControlObject screen(ConfigKey("[MixPi]", "screen"));
        auto settings = UserSettingsPointer::create();
        auto owner = std::make_unique<LibraryScanner>(settings);
        LibraryScanner& scanner = *owner;
        auto* dialog = scanner.m_pProgressDlg.data();
        CHECK(dialog);
        auto* active = ControlObject::getControl(ConfigKey("[MixPi]", "scan_active"));
        auto* percent = ControlObject::getControl(ConfigKey("[MixPi]", "scan_percent"));
        auto* hidden = ControlObject::getControl(ConfigKey("[MixPi]", "scan_bar_hidden"));
        CHECK(active && percent && hidden);
        CHECK(active->get() == 0 && hidden->get() == 0);

        emit scanner.scanStarted();
        CHECK(active->get() == 1);
        emit scanner.progressLoading("/home/pi/Music/Backup/early.mp3");
        watch();
        // Short scans stay silent, as upstream.
        auto* strip = window.findChild<QWidget*>("LibraryScannerStrip");
        CHECK(!strip || strip->isHidden());

        advance();
        emit scanner.progressLoading("/home/pi/Music/Backup/x/Beautiful.mp3");
        app.processEvents();
        strip = window.findChild<QWidget*>("LibraryScannerStrip");
        CHECK(strip);
        CHECK(strip->isVisible());
        CHECK(!strip->isWindow());
        CHECK(!dialog->isVisible());
        // 48 px, directly above the 56 px transport row, over the overviews.
        std::cout << "OBSERVE strip " << strip->geometry().x() << ',' << strip->geometry().y() << ' '
                  << strip->width() << 'x' << strip->height() << std::endl;
        CHECK(strip->geometry() == QRect(0, 376, 800, 48));
        auto* status = strip->findChild<QLabel*>("LibraryScannerStatus");
        auto* progress = strip->findChild<QProgressBar*>("LibraryScannerProgress");
        auto* percentLabel = strip->findChild<QLabel*>("LibraryScannerPercent");
        auto* hide = strip->findChild<QPushButton*>("LibraryScannerHide");
        auto* cancel = strip->findChild<QPushButton*>("LibraryScannerCancel");
        CHECK(status && progress && percentLabel && hide && cancel);
        CHECK(status->text() == "Scanning · Beautiful.mp3");
        CHECK(!status->wordWrap());
        CHECK(progress->isVisible() && progress->minimum() == 0 && progress->maximum() == 100);
        CHECK(percentLabel->isVisible() && percentLabel->text() == "0%");
        CHECK(hide->isVisible() && cancel->isVisible());
        CHECK(hide->size() == QSize(96, 48) && cancel->size() == QSize(96, 48));
        const QRect hideOnWindow(hide->mapTo(&window, QPoint()), hide->size());
        const QRect cancelOnWindow(cancel->mapTo(&window, QPoint()), cancel->size());
        std::cout << "OBSERVE Hide centre " << hideOnWindow.center().x() << ',' << hideOnWindow.center().y()
                  << " Cancel centre " << cancelOnWindow.center().x() << ',' << cancelOnWindow.center().y()
                  << std::endl;
        CHECK(cancelOnWindow.right() == 799 && hideOnWindow.right() < cancelOnWindow.left());
        CHECK(status->geometry().bottom() < strip->height());
        // The transport row stays fully visible and takes taps.
        const QRect playOnWindow(play->mapTo(&window, QPoint()), play->size());
        CHECK(playOnWindow.top() >= strip->geometry().bottom() + 1);
        CHECK(window.childAt(playOnWindow.center()) == play);
        QTest::mouseClick(play, Qt::LeftButton);
        CHECK(playClicks == 1);
        emit scanner.progressHashing("/home/pi/Music/Backup/Artist/Album");
        app.processEvents();
        CHECK(status->text() == "Scanning · Album");
        emit scanner.progressHashing(QString(400, 'x'));
        app.processEvents();
        CHECK(strip->height() == 48);
        CHECK(repaintLeavesNoOldPixels(status, "Scanning · A very long first file name that fills the label.mp3",
                "Scanning · B.mp3"));
        status->setText("Scanning · Beautiful.mp3");

        // Non-modal and never steals focus.
        CHECK(!QApplication::activeModalWidget());
        CHECK(strip->windowModality() == Qt::NonModal);
        CHECK(QApplication::focusWidget() == edit);
        CHECK(cancel->focusPolicy() == Qt::NoFocus && hide->focusPolicy() == Qt::NoFocus);

        // A full-screen view (Sources) hides the strip; the scan goes on.
        screen.setAndConfirm(1);
        watch();
        CHECK(strip->isHidden() && active->get() == 1);
        emit scanner.progressLoading("/home/pi/Music/Backup/during-sources.mp3");
        app.processEvents();
        CHECK(strip->isHidden());
        screen.setAndConfirm(0);
        watch();
        CHECK(strip->isVisible() && strip->geometry() == QRect(0, 376, 800, 48));
        CHECK(status->text() == "Scanning · during-sources.mp3");

        QTest::mouseClick(cancel, Qt::LeftButton);
        CHECK(scanner.cancelled == 1);
        CHECK(strip->isHidden());
        CHECK(active->get() == 0);
        CHECK(QApplication::focusWidget() == edit);

        // Taps elsewhere still reach the main window while the strip shows.
        emit scanner.scanStarted();
        advance();
        emit scanner.progressLoading("/home/pi/Music/Backup/again.mp3");
        app.processEvents();
        CHECK(strip->isVisible());
        const QPoint otherCenter = other->mapTo(&window, other->rect().center());
        CHECK(window.childAt(otherCenter) == other);
        CHECK(strip->geometry().top() > otherCenter.y());
        QTest::mouseClick(other, Qt::LeftButton);
        CHECK(otherClicks == 1);
        QTest::keyClicks(edit, "ok");
        CHECK(edit->text() == "ok");
        CHECK(strip->isVisible());

        // Follows the main window size: 800x444 with the desktop bar shown.
        window.resize(800, 444);
        app.processEvents();
        CHECK(strip->geometry() == QRect(0, 444 - 56 - 48, 800, 48));
        window.resize(640, 400);
        app.processEvents();
        CHECK(strip->geometry() == QRect(0, 400 - 56 - 48, 640, 48));
        window.resize(800, 480);
        app.processEvents();

        // Cover-art progress, completion, and cancellation through the real wiring.
        emit scanner.m_trackDao.progressCoverArt("/home/pi/Music/Backup/cover.jpg");
        app.processEvents();
        CHECK(status->text() == "Scanning cover art · cover.jpg");
        emit scanner.scanFinished();
        app.processEvents();
        CHECK(strip->isHidden() && active->get() == 0);
        emit scanner.progressLoading("/home/pi/Music/Backup/late.mp3");
        watch();
        CHECK(strip->isHidden());
        CHECK(scanner.cancelled == 1);
        emit scanner.scanStarted();
        advance();
        emit scanner.m_trackDao.progressVerifyTracksOutside("/media/usb/x.mp3");
        app.processEvents();
        CHECK(strip->isVisible());
        cancel->click();
        CHECK(scanner.cancelled == 2);
        CHECK(strip->isHidden());
        emit scanner.progressLoading("/home/pi/Music/Backup/after-cancel.mp3");
        watch();
        CHECK(strip->isHidden());

        // Hide: the strip goes, the scan goes on, and ScanBarHidden 1 is saved.
        emit scanner.scanStarted();
        advance();
        emit scanner.progressLoading("/home/pi/Music/Backup/hide.mp3");
        app.processEvents();
        CHECK(strip->isVisible());
        QTest::mouseClick(hide, Qt::LeftButton);
        CHECK(strip->isHidden() && active->get() == 1 && scanner.cancelled == 2);
        CHECK(settings->values.value("[MixPi],ScanBarHidden") == 1 && hidden->get() == 1);
        emit scanner.progressLoading("/home/pi/Music/Backup/still-hidden.mp3");
        watch();
        CHECK(strip->isHidden());
        emit scanner.scanFinished();
        // Later scans show no strip.
        emit scanner.scanStarted();
        advance();
        emit scanner.progressLoading("/home/pi/Music/Backup/next-scan.mp3");
        watch();
        CHECK(strip->isHidden() && active->get() == 1);
        emit scanner.scanFinished();
        // Settings turns it back on through [MixPi],scan_bar_hidden.
        emit scanner.scanStarted();
        advance();
        emit scanner.progressLoading("/home/pi/Music/Backup/bar-back.mp3");
        watch();
        CHECK(strip->isHidden());
        hidden->set(0);
        watch();
        CHECK(strip->isVisible() && settings->values.value("[MixPi],ScanBarHidden") == 0);
        hidden->set(7);
        CHECK(hidden->get() == 0);
        emit scanner.scanFinished();

        percentChecks(scanner, active, percent, progress, percentLabel);
        const int height = strip->height();

        // After a restart the saved Hide still holds: a new owner of the
        // controls starts from mixxx.cfg.
        QTest::mouseClick(hide, Qt::LeftButton);
        CHECK(settings->values.value("[MixPi],ScanBarHidden") == 1);
        owner.reset();
        CHECK(!ControlObject::exists(ConfigKey("[MixPi]", "scan_bar_hidden")));
        LibraryScanner restarted(settings);
        CHECK(ControlObject::getControl(ConfigKey("[MixPi]", "scan_bar_hidden"))->get() == 1);
        emit restarted.scanStarted();
        advance();
        emit restarted.progressLoading("/home/pi/Music/Backup/after-restart.mp3");
        watch();
        for (auto* any : window.findChildren<QWidget*>("LibraryScannerStrip")) {
            CHECK(any->isHidden());
        }
        std::cout << "LIBRARY_SCANNER_STRIP_OK height=" << height << std::endl;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << std::endl;
        return 1;
    }
    return 0;
}
