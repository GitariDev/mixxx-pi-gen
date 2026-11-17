// Council round 1, blocker 3 (mixxx-media-lists.patch): the Media page's
// lists at 800x480 and 800x444 — several drive cards, ten handover entries,
// a long eject-user list — are reachable by scrolling, have 24 px scroll bars
// and touch drag-scrolling, and an unchanged 2 s refresh keeps the scroll
// position and the same widgets.
#include <QApplication>
#include <QFile>
#include <QMainWindow>
#include <QPointer>
#include <QTest>
#include <QWindow>
#include <iostream>

#include "library/mixpimediapage.h"

namespace {
int failures = 0;
int checks = 0;
void check(bool condition, const std::string& message) {
    ++checks;
    if (!condition) {
        ++failures;
        std::cerr << "FAIL " << message << '\n';
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

MixpiMediaDrive drive(int number, int users = 0) {
    MixpiMediaDrive result;
    result.identity = QStringLiteral("identity-%1").arg(number);
    result.name = QStringLiteral("DRIVE%1").arg(number);
    result.size = 32000000000LL;
    result.rekordbox = true;
    result.volumes.append({QStringLiteral("token-%1").arg(number), result.name,
            QStringLiteral("/media/pi/DRIVE%1").arg(number), false});
    for (int index = 1; index <= users; ++index) {
        const bool pad = index > 2;
        result.users.append({pad ? QStringLiteral("[Sampler%1]").arg(index - 2) : QStringLiteral("[Channel%1]").arg(index),
                QStringLiteral("Track number %1").arg(index), index == 1, true});
    }
    result.state = mixpi_media::idleState(result);
    return result;
}

// The widget is inside the area's viewport (fully shown) after scrolling.
bool shownIn(QScrollArea* area, QWidget* widget) {
    if (!widget) {
        std::cerr << "  missing widget in " << area->objectName().toStdString() << '\n';
        return false;
    }
    const QRect rect(widget->mapTo(area->viewport(), QPoint(0, 0)), widget->size());
    const bool shown = area->viewport()->rect().contains(rect);
    if (!shown) {
        std::cerr << "  " << widget->objectName().toStdString() << " at " << rect.x() << ',' << rect.y() << ' ' << rect.width() << 'x' << rect.height()
                  << " viewport " << area->viewport()->width() << 'x' << area->viewport()->height() << " scroll " << area->verticalScrollBar()->value()
                  << '/' << area->verticalScrollBar()->maximum() << '\n';
    }
    return shown;
}

bool insideWindow(QWidget* widget, QWidget* window) {
    const QRect rect(widget->mapTo(window, QPoint(0, 0)), widget->size());
    return window->rect().contains(rect);
}

template<class T>
T* last(QWidget* root, const QString& name) {
    const auto found = root->findChildren<T*>(name);
    return found.isEmpty() ? nullptr : found.last();
}

void run(int height) {
    const std::string size = " (800x" + std::to_string(height) + ")";
    QString style;
    for (const auto& path : qEnvironmentVariable("MIXPI_SKIN_QSS").split(':', Qt::SkipEmptyParts)) {
        QFile file(path);
        if (file.open(QIODevice::ReadOnly)) {
            style += QString::fromUtf8(file.readAll());
        }
    }
    QMainWindow window;
    auto* root = new QWidget;
    root->setStyleSheet(style);
    window.setCentralWidget(root);
    window.resize(800, height);
    window.show();
    settle();
    MixpiMediaPage page(root, {});
    page.setEjectAvailable(true);
    QList<MixpiMediaDrive> drives{drive(1), drive(2), drive(3), drive(4, 10)};
    page.setDrives(drives);
    QList<MixpiHandoverItem> onPi;
    for (const auto& group : {QStringLiteral("[Channel1]"), QStringLiteral("[Channel2]")}) {
        onPi.append({group, QStringLiteral("Deck track")});
    }
    for (int pad = 1; pad <= 8; ++pad) {
        onPi.append({QStringLiteral("[Sampler%1]").arg(pad), QStringLiteral("Sample %1").arg(pad)});
    }
    page.setHandover(onPi, {QStringLiteral("Old one"), QStringLiteral("Old two"), QStringLiteral("Old three")});
    page.open();
    settle(50);
    check(page.geometry() == QRect(0, 48, 800, height - 48), "page fills the skin under the top bar" + size);

    auto* left = page.findChild<QScrollArea*>(QStringLiteral("MixpiMediaDrives"));
    auto* right = page.findChild<QScrollArea*>(QStringLiteral("MixpiMediaHandoverScroll"));
    check(left && right, "the drive list and the handover column are scroll areas" + size);
    for (auto* area : {left, right}) {
        check(area->findChild<QObject*>(QStringLiteral("MixpiDragScroll"), Qt::FindDirectChildrenOnly) != nullptr,
                "touch: " + area->objectName().toStdString() + " scrolls by drag" + size);
    }
    check(left->verticalScrollBar()->isVisible() && left->verticalScrollBar()->width() == 24,
            "drive list: a visible 24 px scroll bar" + size);
    check(right->verticalScrollBar()->isVisible() && right->verticalScrollBar()->width() == 24,
            "handover: a visible 24 px scroll bar" + size);

    // The last drive card and its EJECT are reachable.
    auto* lastCard = last<QFrame>(left->widget(), QStringLiteral("MixpiMediaCard"));
    auto* lastEject = last<QPushButton>(left->widget(), QStringLiteral("MixpiMediaEject"));
    left->ensureWidgetVisible(lastEject);
    settle();
    check(lastCard && lastCard->property("identity").toString() == "identity-4" && shownIn(left, lastEject),
            "drive list: the last card's EJECT is reachable" + size);
    left->verticalScrollBar()->setValue(left->verticalScrollBar()->maximum());
    settle();
    check(shownIn(left, last<QLabel>(left->widget(), QStringLiteral("MixpiMediaUse"))),
            "drive list: the last card's last line is reachable" + size);
    // The last handover row (PAD 8) and the cleaned-out list are reachable.
    right->verticalScrollBar()->setValue(right->verticalScrollBar()->maximum());
    settle();
    const auto rows = right->widget()->findChildren<QFrame*>(QStringLiteral("MixpiMediaOnPiRow"));
    check(rows.size() == 10 && shownIn(right, rows.last()), "handover: the tenth entry is reachable" + size);
    check(shownIn(right, last<QLabel>(right->widget(), QStringLiteral("MixpiMediaCleaned"))),
            "handover: Cleaned out is reachable" + size);
    check(right->viewport()->height() <= height - 48 - 48, "handover: the column is bounded by the page" + size);

    // An unchanged refresh: same scroll position, same widget instances.
    left->verticalScrollBar()->setValue(left->verticalScrollBar()->maximum() / 2);
    right->verticalScrollBar()->setValue(right->verticalScrollBar()->maximum() / 2);
    const int leftPosition = left->verticalScrollBar()->value();
    const int rightPosition = right->verticalScrollBar()->value();
    QPointer<QWidget> list = left->widget();
    QPointer<QPushButton> firstOpen = left->widget()->findChild<QPushButton*>(QStringLiteral("MixpiMediaOpen"));
    QPointer<QFrame> firstRow = rows.first();
    for (int tick = 0; tick < 3; ++tick) {
        page.setDrives(drives); // what the 2 s timer does
        page.setHandover(onPi, {QStringLiteral("Old one"), QStringLiteral("Old two"), QStringLiteral("Old three")});
        settle();
    }
    check(list && list == left->widget() && firstOpen && firstRow,
            "refresh: unchanged drives keep the same widgets" + size);
    check(left->verticalScrollBar()->value() == leftPosition && right->verticalScrollBar()->value() == rightPosition,
            "refresh: unchanged drives keep the scroll position" + size);
    // A real change rebuilds, and the list stays where it was.
    drives[0].busy = true;
    drives[0].state = mixpi_media::idleState(drives[0]);
    page.setDrives(drives);
    settle();
    check(!list && left->verticalScrollBar()->value() == leftPosition,
            "refresh: a state change rebuilds the cards and keeps the scroll position" + size);

    // Touch: a drag scrolls and does not tap the button under the finger.
    left->verticalScrollBar()->setValue(0);
    settle();
    auto* open = left->widget()->findChild<QPushButton*>(QStringLiteral("MixpiMediaOpen"));
    int taps = 0;
    QObject::connect(open, &QPushButton::clicked, [&] { ++taps; });
    // Through the window, as the platform delivers a finger: press, move, release.
    QWindow* handle = window.windowHandle();
    const QPoint start = open->mapTo(&window, open->rect().center());
    QTest::mousePress(handle, Qt::LeftButton, {}, start);
    for (int step = 1; step <= 12; ++step) {
        QTest::mouseMove(handle, start - QPoint(0, 10 * step), 16);
    }
    const int dragged = left->verticalScrollBar()->value();
    // The finger comes back over OPEN and lifts there: still a drag, no tap.
    QTest::mouseMove(handle, start, 16);
    QTest::mouseRelease(handle, Qt::LeftButton, {}, start, 16);
    settle(100);
    check(taps == 0, "touch: a drag over OPEN does not tap it" + size);
    check(dragged >= 100, "touch: the drag scrolls the drive list with the finger (" + std::to_string(dragged) + ")" + size);
    check(!open->isDown(), "touch: the button is not left pressed after a drag" + size);
    // And a tap without movement still taps.
    left->verticalScrollBar()->setValue(0);
    settle(100);
    const QPoint tap = open->mapTo(&window, open->rect().center());
    QTest::mousePress(handle, Qt::LeftButton, {}, tap);
    QTest::mouseRelease(handle, Qt::LeftButton, {}, tap, 60);
    settle(600);
    check(taps == 1, "touch: a tap without movement taps OPEN" + size);

    // The eject sheet with every user listed: CANCEL and EJECT stay on screen.
    page.showEjectSheet(QStringLiteral("identity-4"));
    settle();
    auto* sheet = page.sheet();
    auto* users = sheet->findChild<QScrollArea*>(QStringLiteral("MixpiEjectUsers"));
    auto* cancel = sheet->findChild<QPushButton*>(QStringLiteral("MixpiEjectCancel"));
    auto* confirm = sheet->findChild<QPushButton*>(QStringLiteral("MixpiEjectConfirm"));
    check(users && users->findChild<QObject*>(QStringLiteral("MixpiDragScroll"), Qt::FindDirectChildrenOnly),
            "eject sheet: the user list scrolls by drag" + size);
    check(insideWindow(sheet, &window) && insideWindow(cancel, &window) && insideWindow(confirm, &window) &&
                    cancel->isVisible() && confirm->isVisible() && confirm->isEnabled(),
            "eject sheet: CANCEL and EJECT stay on screen with ten users" + size);
    users->verticalScrollBar()->setValue(users->verticalScrollBar()->maximum());
    settle();
    const auto fates = users->widget()->findChildren<QLabel*>(QStringLiteral("MixpiEjectUser"));
    check(fates.size() == 10 && shownIn(users, fates.last()), "eject sheet: the tenth user is reachable" + size);
    page.hideSheet();
}
} // namespace

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    run(480);
    run(444);
    // [ChannelN],mixpi_from_usb: the rule the control follows.
    const QStringList drives{QStringLiteral("/media/pi/MANTACORE"), QStringLiteral("/media/pi/SPARE/")};
    check(mixpi_media::fromUsb(QStringLiteral("/media/pi/MANTACORE/Contents/a.mp3"), drives, false),
            "from usb: a deck track on a mounted drive is 1");
    check(mixpi_media::fromUsb(QStringLiteral("/media/pi/SPARE/b.wav"), drives, false),
            "from usb: a drive path with a trailing slash matches too");
    check(!mixpi_media::fromUsb(QStringLiteral("/media/pi/MANTACORE/Contents/a.mp3"), drives, true),
            "from usb: 0 once the eject marks it ON PI");
    check(!mixpi_media::fromUsb(QStringLiteral("/home/pi/Music/c.mp3"), drives, false), "from usb: a Pi track is 0");
    check(!mixpi_media::fromUsb(QStringLiteral("/media/pi/MANTACORE2/d.mp3"), drives, false),
            "from usb: another drive whose name starts the same is not this drive");
    check(!mixpi_media::fromUsb({}, drives, false), "from usb: an empty deck is 0");
    check(!mixpi_media::fromUsb(QStringLiteral("/media/pi/MANTACORE/a.mp3"), {}, false),
            "from usb: 0 when the drive is no longer mounted");
    std::cout << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
