#include <QApplication>
#include <QLabel>
#include <QLineEdit>
#include <QMainWindow>
#include <QProgressBar>
#include <QPushButton>
#include <QTest>
#include <QVBoxLayout>
#include <iostream>
#include <stdexcept>
#include "library_scanner_strip_doubles.h"
#define CHECK(x) do { if (!(x)) throw std::runtime_error(#x); } while (false)

std::chrono::milliseconds g_fakeNow{0};

static void advance() {
    g_fakeNow += std::chrono::milliseconds(2500);
}

LibraryScanner::LibraryScanner() {
#include "scanner_wiring.inc"
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    try {
        QMainWindow window;
        auto* central = new QWidget;
        auto* layout = new QVBoxLayout(central);
        auto* other = new QPushButton("Deck");
        auto* edit = new QLineEdit;
        int otherClicks = 0;
        QObject::connect(other, &QPushButton::clicked, [&] { ++otherClicks; });
        layout->addWidget(other);
        layout->addWidget(edit);
        layout->addStretch();
        window.setCentralWidget(central);
        window.resize(800, 444);
        window.show();
        app.processEvents();
        edit->setFocus();
        app.processEvents();

        LibraryScanner scanner;
        auto* dialog = scanner.m_pProgressDlg.data();
        CHECK(dialog);
        emit scanner.scanStarted();
        emit scanner.progressLoading("/home/pi/Music/Backup/early.mp3");
        app.processEvents();
        // Short scans stay silent, as upstream.
        auto* strip = window.findChild<QWidget*>("LibraryScannerStrip");
        CHECK(!strip || strip->isHidden());

        advance();
        emit scanner.progressLoading("/home/pi/Music/Backup/Artist/Album/Track.mp3");
        app.processEvents();
        strip = window.findChild<QWidget*>("LibraryScannerStrip");
        CHECK(strip);
        CHECK(strip->isVisible());
        CHECK(!strip->isWindow());
        CHECK(!dialog->isVisible());
        // Compact: one strip of 40-48 px along the bottom of the main window.
        CHECK(strip->height() >= 40 && strip->height() <= 48);
        CHECK(strip->geometry() == QRect(0, 444 - strip->height(), 800, strip->height()));
        auto* status = strip->findChild<QLabel*>("LibraryScannerStatus");
        auto* progress = strip->findChild<QProgressBar*>("LibraryScannerProgress");
        auto* cancel = strip->findChild<QPushButton*>("LibraryScannerCancel");
        CHECK(status && progress && cancel);
        CHECK(status->text() == "Scanning: /home/pi/Music/Backup/Artist/Album/Track.mp3");
        CHECK(!status->wordWrap());
        CHECK(progress->isVisible() && progress->minimum() == 0 && progress->maximum() == 0);
        CHECK(cancel->isVisible());
        CHECK(status->geometry().bottom() < strip->height() && cancel->geometry().bottom() < strip->height());
        emit scanner.progressHashing(QString(400, 'x'));
        app.processEvents();
        CHECK(strip->height() == 44);

        // Non-modal and never steals focus.
        CHECK(!QApplication::activeModalWidget());
        CHECK(strip->windowModality() == Qt::NonModal);
        CHECK(QApplication::focusWidget() == edit);
        CHECK(cancel->focusPolicy() == Qt::NoFocus);
        QTest::mouseClick(cancel, Qt::LeftButton);
        CHECK(scanner.cancelled == 1);
        CHECK(strip->isHidden());
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

        // Follows the main window size.
        window.resize(640, 400);
        app.processEvents();
        CHECK(strip->geometry() == QRect(0, 400 - strip->height(), 640, strip->height()));

        // Cover-art progress, completion, and cancellation through the real wiring.
        emit scanner.m_trackDao.progressCoverArt("/home/pi/Music/Backup/cover.jpg");
        app.processEvents();
        CHECK(status->text().startsWith("Scanning cover art (safe to cancel): "));
        emit scanner.scanFinished();
        app.processEvents();
        CHECK(strip->isHidden());
        emit scanner.progressLoading("/home/pi/Music/Backup/late.mp3");
        app.processEvents();
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
        app.processEvents();
        CHECK(strip->isHidden());
        std::cout << "LIBRARY_SCANNER_STRIP_OK height=" << strip->height() << std::endl;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << std::endl;
        return 1;
    }
    return 0;
}
