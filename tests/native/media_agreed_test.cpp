// Build C, wave C1 (mixxx-media-agreed.patch): the agreed Media page (U-10,
// spec s13, mockups/m-media.png) and the insert choice (U-8, s11), with the
// shipped MixpiPage, MixpiMediaPage and MixpiBottomStrip, fake drives and the
// real stylesheets (pioneered-menus.qss, mixpi-media-page.qss, ...).
//
// usage: media-agreed-test [RENDER_DIRECTORY]
// With a directory, it also writes the 800x480 offscreen renders there.
#include <QApplication>
#include <QDir>
#include <QFile>
#include <QFontDatabase>
#include <QMainWindow>
#include <QPointer>
#include <QTest>
#include <QWindow>
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

MixpiMediaDrive drive(const QString& name, qint64 size, bool inUse = false) {
    MixpiMediaDrive result;
    result.identity = QStringLiteral("identity-") + name;
    result.name = name;
    result.size = size;
    result.rekordbox = true;
    result.volumes.append({QStringLiteral("token-") + name, name, QStringLiteral("/media/pi/") + name, false});
    if (inUse) {
        // A deck plays a track from it: build B wrote a line for that; s13 does not.
        result.users.append({QStringLiteral("[Channel1]"), QStringLiteral("Song on the deck"), true, true});
    }
    result.state = mixpi_media::idleState(result);
    return result;
}

QList<MixpiMediaDrive> threeDrives() {
    return {drive(QStringLiteral("MANTACORE"), 58600000000LL, true), drive(QStringLiteral("SPARE"), 32000000000LL),
            drive(QStringLiteral("KINGSTON"), 16000000000LL)};
}

QList<MixpiHandoverItem> onPi(int count) {
    QList<MixpiHandoverItem> result;
    for (int index = 1; index <= count; ++index) {
        result.append({QStringLiteral("[Channel%1]").arg(index), QStringLiteral("Track %1").arg(index)});
    }
    return result;
}

QColor pixel(QWidget* widget, QPoint point) {
    return widget->grab().toImage().pixelColor(point);
}

std::string name(const QColor& color) {
    return color.name().toStdString();
}

QList<QFrame*> cards(MixpiMediaPage& page) {
    auto* list = page.findChild<QScrollArea*>(QStringLiteral("MixpiMediaDrives"));
    return list && list->widget() ? list->widget()->findChildren<QFrame*>(QStringLiteral("MixpiMediaCard"))
                                  : QList<QFrame*>();
}

QStringList cardNames(MixpiMediaPage& page) {
    QStringList result;
    for (auto* card : cards(page)) {
        result.append(card->property("identity").toString().remove(QStringLiteral("identity-")));
    }
    return result;
}

QStringList allTexts(QWidget* root) {
    QStringList result;
    for (auto* label : root->findChildren<QLabel*>()) {
        if (label->isVisibleTo(root)) {
            result.append(label->text());
        }
    }
    for (auto* button : root->findChildren<QPushButton*>()) {
        if (button->isVisibleTo(root)) {
            result.append(button->text());
        }
    }
    return result;
}

bool shownIn(QScrollArea* area, QWidget* widget) {
    if (!widget) {
        return false;
    }
    const QRect rect(widget->mapTo(area->viewport(), QPoint(0, 0)), widget->size());
    return area->viewport()->rect().contains(rect);
}

void save(QWidget* widget, const QString& file) {
    if (renders.isEmpty()) {
        return;
    }
    const bool saved = widget->grab().save(QDir(renders).filePath(file));
    check(saved, "render: wrote " + file.toStdString());
}

void pageChecks(QMainWindow& window, QWidget* root) {
    double screen = -1;
    MixpiMediaPage page(root, [&](double value) { screen = value; });
    page.setEjectAvailable(true);
    page.setDrives(threeDrives());
    page.setHandover(onPi(2), {QStringLiteral("cleaned")});
    page.open();
    settle(50);
    check(page.geometry() == QRect(0, 48, 800, 432) && screen == 2, "page: under the 48 px top bar, screen 2");

    // Header: title, ALL, READY, IN USE, then the close control at the right end.
    auto* header = page.findChild<QFrame*>(QStringLiteral("MixpiPageHeader"));
    auto* title = page.findChild<QLabel*>(QStringLiteral("MixpiPageTitle"));
    const auto options = page.findChildren<QPushButton*>(QStringLiteral("MixpiMediaFilterOption"));
    auto* close = page.closeButton();
    check(header && header->height() == 52, "header: 52 px, as drawn");
    check(title && title->text() == QStringLiteral("USB & MEDIA"), "header: the title reads USB & MEDIA");
    QStringList words;
    for (auto* option : options) {
        words.append(option->text());
    }
    check(words == QStringList({QStringLiteral("ALL"), QStringLiteral("READY"), QStringLiteral("IN USE")}),
            "header: the filters read ALL, READY, IN USE");
    const auto x = [header](QWidget* widget) { return widget->mapTo(header, QPoint(0, 0)).x(); };
    check(options.size() == 3 && x(title) < x(options[0]) && x(options[0]) < x(options[1]) &&
                    x(options[1]) < x(options[2]) && x(options[2]) < x(close),
            "header: order is title, ALL, READY, IN USE, close");
    check(x(close) + close->width() == 796 && close->size() == QSize(48, 48),
            "header: the close control is 48x48 at the right end (" + std::to_string(x(close)) + ")");
    check(close->text().isEmpty() && close->accessibleName() == QStringLiteral("Close"),
            "close: no text glyph, the strokes are drawn; accessible name Close");
    check(x(title) == 16, "header: the title starts 16 px from the left");
    // Close: surface-2 square, no outline at rest, red strokes; pressed shows the danger border.
    check(pixel(close, QPoint(24, 0)) == QColor(QStringLiteral("#1d222a")) &&
                    pixel(close, QPoint(0, 24)) == QColor(QStringLiteral("#1d222a")),
            "close: surface-2 to its edge, no outline at rest (" + name(pixel(close, QPoint(24, 0))) + ")");
    const QColor stroke = pixel(close, QPoint(24, 24));
    check(stroke.red() > 200 && stroke.green() < 160 && stroke.blue() < 150,
            "close: the centre of the ✕ is red (" + name(stroke) + ")");
    close->setDown(true);
    const QColor pressedEdge = pixel(close, QPoint(24, 0));
    const QColor pressedFill = pixel(close, QPoint(6, 6));
    close->setDown(false);
    check(pressedEdge == QColor(QStringLiteral("#d0574d")) && pressedFill == QColor(QStringLiteral("#34191b")),
            "close: pressed is danger-surface with a danger border (" + name(pressedFill) + ", " + name(pressedEdge) +
                    ")");

    // Filters: ALL by default and chosen as a lit tint with an accent border.
    check(options[0]->isChecked() && !options[1]->isChecked() && !options[2]->isChecked() &&
                    page.filter() == mixpi_media::Filter::All,
            "filters: ALL is the default");
    const QColor lit = pixel(options[0], QPoint(options[0]->width() / 2, 10));
    const QColor edge = pixel(options[0], QPoint(options[0]->width() / 2, 0));
    check(edge == QColor(QStringLiteral("#a3c45e")) && lit != QColor(QStringLiteral("#a3c45e")) && lit.green() > lit.red(),
            "filters: the chosen segment is a see-through accent tint with an accent border (" + name(lit) + ")");
    check(cardNames(page) == QStringList({QStringLiteral("MANTACORE"), QStringLiteral("SPARE"), QStringLiteral("KINGSTON")}),
            "filters: ALL shows every drive");
    save(window.centralWidget(), QStringLiteral("r1-three-drives.png"));

    // One row per drive: USB icon, name, size, chip, OPEN, EJECT.
    bool rows = true;
    for (auto* card : cards(page)) {
        rows = rows && card->findChildren<QPushButton*>(QStringLiteral("MixpiMediaOpen")).size() == 1 &&
                card->findChildren<QPushButton*>(QStringLiteral("MixpiMediaEject")).size() == 1 &&
                card->findChildren<QLabel*>(QStringLiteral("MixpiMediaChip")).size() == 1 &&
                card->findChildren<QWidget*>(QStringLiteral("MixpiMediaUsbIcon")).size() == 1 &&
                card->findChildren<QLabel*>(QStringLiteral("MixpiMediaSize")).size() == 1;
    }
    check(rows && cards(page).size() == 3, "rows: each drive has a USB icon, size, chip, OPEN and EJECT");
    auto* first = cards(page).value(0);
    auto* chip = first->findChild<QLabel*>(QStringLiteral("MixpiMediaChip"));
    auto* size = first->findChild<QLabel*>(QStringLiteral("MixpiMediaSize"));
    auto* open = first->findChild<QPushButton*>(QStringLiteral("MixpiMediaOpen"));
    auto* eject = first->findChild<QPushButton*>(QStringLiteral("MixpiMediaEject"));
    check(chip->text() == QStringLiteral("IN USE") && cards(page)[1]->findChild<QLabel*>(QStringLiteral("MixpiMediaChip"))->text() ==
                    QStringLiteral("READY"),
            "rows: the chips read IN USE and READY");
    check(size->text() == QStringLiteral("58.6 GB"), "rows: the size line is only the size (" + size->text().toStdString() + ")");
    check(open->text() == QStringLiteral("OPEN") && open->property("role").toString() == QStringLiteral("navigate") &&
                    eject->text() == QStringLiteral("EJECT") && eject->property("role").toString() == QStringLiteral("caution"),
            "rows: OPEN is Navigate and EJECT is Caution");
    const auto x2 = [first](QWidget* widget) { return widget->mapTo(first, QPoint(0, 0)).x(); };
    check(x2(open) < x2(eject) && open->size() == QSize(160, 48) && eject->size() == QSize(160, 48),
            "rows: OPEN then EJECT, each 160x48 (" + std::to_string(open->width()) + 'x' +
                    std::to_string(open->height()) + ", " + std::to_string(eject->width()) + 'x' +
                    std::to_string(eject->height()) + ")");
    check(pixel(eject, QPoint(80, 4)) == QColor(QStringLiteral("#30260e")) &&
                    pixel(eject, QPoint(80, 0)) == QColor(QStringLiteral("#dfa33a")),
            "rows: EJECT is dark amber with an amber border (" + name(pixel(eject, QPoint(80, 4))) + ")");
    check(pixel(open, QPoint(80, 4)) == QColor(QStringLiteral("#1d222a")) &&
                    pixel(open, QPoint(80, 0)) == QColor(QStringLiteral("#3a424e")),
            "rows: OPEN is neutral (" + name(pixel(open, QPoint(80, 4))) + ")");
    check(pixel(chip, QPoint(4, chip->height() / 2)) == QColor(QStringLiteral("#13272f")),
            "rows: the IN USE chip has the info tint (" + name(pixel(chip, QPoint(4, chip->height() / 2))) + ")");
    // In the card's grab: the chip's corner shows the card behind it, its top edge the chip border.
    const QImage cardImage = first->grab().toImage();
    const QPoint chipAt = chip->mapTo(first, QPoint(0, 0));
    const QColor corner = cardImage.pixelColor(chipAt);
    const QColor top = cardImage.pixelColor(chipAt + QPoint(chip->width() / 2, 0));
    check(corner == QColor(QStringLiteral("#161a20")) && top == QColor(QStringLiteral("#5aa4c4")) &&
                    chip->height() == 22,
            "rows: the chip is a 22 px pill (its corners are rounded: " + name(corner) + ", " + name(top) + ", " +
                    std::to_string(chip->width()) + 'x' + std::to_string(chip->height()) + ")");
    // The eject icon is drawn: amber pixels in the icon box left of the label.
    bool amber = false;
    const QImage ejectImage = eject->grab().toImage();
    for (int px = 0; px < 70 && !amber; ++px) {
        for (int py = 14; py < 34 && !amber; ++py) {
            const QColor color = ejectImage.pixelColor(px, py);
            amber = color.red() > 180 && color.green() > 130 && color.blue() < 120;
        }
    }
    check(amber, "rows: EJECT shows the eject icon before its label");
    QTest::mousePress(eject, Qt::LeftButton, {}, QPoint(150, 24));
    const QColor ejectPressed = pixel(eject, QPoint(150, 6));
    QTest::mouseRelease(eject, Qt::LeftButton, {}, QPoint(150, 24));
    check(ejectPressed == QColor(QStringLiteral("#dfa33a")), "rows: EJECT is solid amber only while pressed (" +
                    name(ejectPressed) + ")");
    page.hideSheet();
    // Removed: no COPY TO PI, no deck or song lines, no paragraph, no right column.
    const auto texts = allTexts(&page);
    check(!texts.contains(QStringLiteral("COPY TO PI")) && !page.findChild<QWidget*>(QStringLiteral("MixpiMediaCopy")),
            "removed: no COPY TO PI");
    bool songLines = false;
    for (const auto& text : texts) {
        songLines = songLines || text.contains(QStringLiteral("Deck 1")) || text.contains(QStringLiteral("Song on the deck")) ||
                text.contains(QStringLiteral("PLAYING FROM PI MEMORY")) || text.contains(QStringLiteral("library opens")) ||
                text.contains(QStringLiteral("Drives are ready")) || text.contains(QStringLiteral("CLEANED OUT"));
    }
    check(!songLines && !page.findChild<QWidget*>(QStringLiteral("MixpiMediaHandover")),
            "removed: no deck or song lines, no paragraph, no Pi memory column");

    // Footer: "2 tracks playing from Pi memory", only while tracks are.
    auto* footer = page.findChild<QFrame*>(QStringLiteral("MixpiMediaFooter"));
    auto* count = page.findChild<QLabel*>(QStringLiteral("MixpiMediaFooterCount"));
    auto* rest = page.findChild<QLabel*>(QStringLiteral("MixpiMediaFooterText"));
    check(footer && footer->isVisible() && count->text() == QStringLiteral("2 tracks") &&
                    rest->text() == QStringLiteral("playing from Pi memory") && footer->height() == 40 &&
                    footer->mapTo(&page, QPoint(0, footer->height())).y() == page.height(),
            "footer: 2 tracks playing from Pi memory, at the bottom");
    check(count->font().bold() || count->font().weight() >= QFont::DemiBold, "footer: the count is bold");
    page.setHandover(onPi(1), {});
    check(count->text() == QStringLiteral("1 track"), "footer: 1 track");
    page.setHandover({}, {});
    check(!footer->isVisible(), "footer: hidden while no track plays from Pi memory");
    page.setHandover(onPi(2), {});

    // Scrolling: three rows do not fit, the bar shows at 24 px and a drag scrolls.
    auto* list = page.findChild<QScrollArea*>(QStringLiteral("MixpiMediaDrives"));
    settle(20);
    check(list->verticalScrollBar()->isVisible() && list->verticalScrollBar()->width() == 24 &&
                    list->verticalScrollBar()->mapTo(&page, QPoint(24, 0)).x() == 800,
            "scroll: three drives show a 24 px bar at the right edge");
    check(list->findChild<QObject*>(QStringLiteral("MixpiDragScroll"), Qt::FindDirectChildrenOnly) != nullptr,
            "scroll: the list scrolls by drag");
    auto* lastEject = cards(page).last()->findChild<QPushButton*>(QStringLiteral("MixpiMediaEject"));
    check(!shownIn(list, lastEject), "scroll: the third row's EJECT is below the fold at first");
    QWindow* handle = window.windowHandle();
    const QPoint start = first->mapTo(&window, QPoint(300, 30));
    QTest::mousePress(handle, Qt::LeftButton, {}, start);
    for (int step = 1; step <= 15; ++step) {
        QTest::mouseMove(handle, start - QPoint(0, 12 * step), 16);
    }
    QTest::mouseRelease(handle, Qt::LeftButton, {}, start - QPoint(0, 180), 16);
    settle(50);
    check(shownIn(list, lastEject), "scroll: a drag brings the third row's EJECT into view");
    const int right = cards(page).last()->mapTo(&page, QPoint(cards(page).last()->width(), 0)).x();
    check(right == 772, "scroll: the rows end 4 px left of the bar (" + std::to_string(right) + ")");
    list->verticalScrollBar()->setValue(0);
    settle();

    // OPEN reads the drive; once open the button reads BROWSE.
    QString openedIdentity;
    QString openedToken;
    page.openRequested = [&](QString identity, QString token) {
        openedIdentity = identity;
        openedToken = token;
    };
    cards(page)[1]->findChild<QPushButton*>(QStringLiteral("MixpiMediaOpen"))->click();
    check(openedIdentity == QStringLiteral("identity-SPARE") && openedToken == QStringLiteral("token-SPARE"),
            "open: OPEN asks the owner to open that drive's volume");
    auto drives = threeDrives();
    drives[1].volumes[0].opened = true;
    drives[1].opened = true;
    drives[1].state = mixpi_media::idleState(drives[1]);
    page.setDrives(drives);
    settle();
    check(cards(page)[1]->findChild<QPushButton*>(QStringLiteral("MixpiMediaOpen"))->text() == QStringLiteral("BROWSE"),
            "open: after it, the button reads BROWSE");
    page.setDrives(threeDrives());

    // Filters.
    options[1]->click();
    settle();
    check(page.filter() == mixpi_media::Filter::Ready && options[1]->isChecked() &&
                    cardNames(page) == QStringList({QStringLiteral("SPARE"), QStringLiteral("KINGSTON")}),
            "filters: READY shows the ready drives");
    save(window.centralWidget(), QStringLiteral("r2-ready-filter.png"));
    options[2]->click();
    settle();
    check(cardNames(page) == QStringList({QStringLiteral("MANTACORE")}), "filters: IN USE shows the drive in use");
    auto leaving = threeDrives();
    leaving[1].state = MixpiMediaState::Ejecting;
    leaving[2].state = MixpiMediaState::SafeToRemove;
    page.setDrives(leaving);
    const QStringList everyone{QStringLiteral("MANTACORE"), QStringLiteral("SPARE"), QStringLiteral("KINGSTON")};
    check(cardNames(page) == everyone, "filters: EJECTING and SAFE TO REMOVE drives show under IN USE");
    options[1]->click();
    check(cardNames(page) == QStringList({QStringLiteral("SPARE"), QStringLiteral("KINGSTON")}),
            "filters: and under READY");
    check(cards(page)[0]->findChild<QLabel*>(QStringLiteral("MixpiMediaChip"))->text() == QStringLiteral("EJECTING") &&
                    !cards(page)[0]->findChild<QPushButton*>(QStringLiteral("MixpiMediaEject"))->isEnabled(),
            "rows: an ejecting drive reads EJECTING and its EJECT is off");
    page.setDrives(threeDrives());
    page.closePage();
    page.open();
    settle();
    check(page.filter() == mixpi_media::Filter::All && options[0]->isChecked() && cards(page).size() == 3,
            "filters: each open starts on ALL");

    // R-6 gate: with eject off on this card, EJECT is off and nothing explains it in a row.
    page.setEjectAvailable(false);
    check(!cards(page)[1]->findChild<QPushButton*>(QStringLiteral("MixpiMediaEject"))->isEnabled(),
            "gate: EJECT is off while the eject gate is closed");
    page.setEjectAvailable(true);
    // The eject sheet keeps build B's words and steps, with the section 1 roles.
    int ejects = 0;
    page.ejectRequested = [&](QString) { ++ejects; };
    cards(page)[1]->findChild<QPushButton*>(QStringLiteral("MixpiMediaEject"))->click();
    settle();
    auto* sheet = page.sheet();
    auto* cancel = sheet->findChild<QPushButton*>(QStringLiteral("MixpiEjectCancel"));
    auto* confirm = sheet->findChild<QPushButton*>(QStringLiteral("MixpiEjectConfirm"));
    check(page.sheetVisible() && ejects == 0 && sheet->findChild<QLabel*>(QStringLiteral("MixpiEjectTitle"))->text() ==
                    QStringLiteral("Eject SPARE?"),
            "sheet: EJECT on a row opens the sheet and ejects nothing yet");
    check(cancel->property("role").toString() == QStringLiteral("navigate") &&
                    confirm->property("role").toString() == QStringLiteral("caution") &&
                    pixel(confirm, QPoint(confirm->width() / 2, 4)) == QColor(QStringLiteral("#30260e")),
            "sheet: CANCEL is Navigate and EJECT is Caution");
    save(window.centralWidget(), QStringLiteral("r5-eject-sheet.png"));
    page.setEjectStep(MixpiMediaPage::Step::Done);
    auto* done = sheet->findChild<QPushButton*>(QStringLiteral("MixpiEjectDone"));
    check(done->isVisible() && done->property("role").toString() == QStringLiteral("confirm") &&
                    pixel(done, QPoint(done->width() / 2, 4)) == QColor(QStringLiteral("#a3c45e")),
            "sheet: DONE is Confirm");
    page.hideSheet();

    // Touch: every visible button is 48 px tall or more.
    bool touch = true;
    for (auto* button : page.findChildren<QPushButton*>()) {
        if (button->isVisibleTo(&page) && button->height() < 48) {
            touch = false;
            std::cerr << "  small " << button->objectName().toStdString() << '\n';
        }
    }
    check(touch, "touch: every button on the page is at least 48 px tall");

    // No drive: build B's short line only.
    page.setDrives({});
    page.setHandover({}, {});
    settle();
    const auto empty = allTexts(&page);
    check(empty.contains(QStringLiteral("No USB drive")) && !empty.join(' ').contains(QStringLiteral("Plug in")),
            "no drive: the short line No USB drive, without the paragraph");
    save(window.centralWidget(), QStringLiteral("r3-no-drive.png"));
    page.closePage();
}

void insertChecks(QWidget* root, QMainWindow& window) {
    MixpiBottomStrip strip(root);
    QStringList loads;
    const auto load = [&](QString identity) { loads.append(identity); };
    // ASK (0, the default): the ping with LOAD and DISMISS, nothing loads.
    const bool asked = mixpiDriveInserted(&strip, 0, QStringLiteral("identity-SPARE"), QStringLiteral("SPARE"),
            QStringLiteral("rekordbox export found · 32.0 GB"), load);
    settle();
    auto* loadButton = strip.findChild<QPushButton*>(QStringLiteral("MixpiStripLoad"));
    auto* dismiss = strip.findChild<QPushButton*>(QStringLiteral("MixpiStripDismiss"));
    check(!asked && loads.isEmpty() && strip.isVisible() && strip.kind() == MixpiBottomStrip::Kind::Ping &&
                    loadButton->isVisible() && dismiss->isVisible(),
            "insert: ASK shows the ping with LOAD and DISMISS");
    check(loadButton->property("role").toString() == QStringLiteral("confirm") &&
                    dismiss->property("role").toString() == QStringLiteral("navigate") &&
                    pixel(loadButton, QPoint(60, 4)) == QColor(QStringLiteral("#a3c45e")) &&
                    pixel(dismiss, QPoint(60, 4)) == QColor(QStringLiteral("#1d222a")),
            "insert: LOAD is Confirm and DISMISS is Navigate");
    check(strip.geometry() == QRect(0, 424, 800, 56), "insert: the ping covers the bottom 56 px");
    save(&window, QStringLiteral("r4-insert-ping.png"));
    strip.loadRequested = load;
    loadButton->click();
    check(loads == QStringList({QStringLiteral("identity-SPARE")}) && !strip.isVisible(),
            "insert: the ping's LOAD opens that drive, as before");
    loads.clear();
    // AUTO LOAD (1): opens the drive at once, no ping.
    const bool loaded = mixpiDriveInserted(&strip, 1, QStringLiteral("identity-KINGSTON"), QStringLiteral("KINGSTON"),
            QStringLiteral("folders · 16.0 GB"), load);
    settle();
    check(loaded && loads == QStringList({QStringLiteral("identity-KINGSTON")}) && !strip.isVisible() &&
                    strip.kind() == MixpiBottomStrip::Kind::None,
            "insert: AUTO LOAD loads the drive at once with no ping");
    check(mixpi_media::autoLoad(1) && !mixpi_media::autoLoad(0) && !mixpi_media::autoLoad(2),
            "insert: only 1 is AUTO LOAD; 0 and anything else ask");
    // The Safe to remove strip stays green, with OK as Navigate.
    strip.showSafe(QStringLiteral("identity-SPARE"), QStringLiteral("SPARE"));
    settle();
    const QColor safe = pixel(&strip, QPoint(400, 40));
    check(safe == QColor(QStringLiteral("#5fae6e")) || safe == QColor(QStringLiteral("#7cc58a")),
            "safe strip: green (" + name(safe) + ")");
    const QColor safeText = strip.findChild<QLabel*>(QStringLiteral("MixpiStripTitle"))->palette().color(QPalette::WindowText);
    check(safeText == QColor(QStringLiteral("#0d1014")), "safe strip: dark text on the green (" + name(safeText) + ")");
    save(&window, QStringLiteral("r6-safe-strip.png"));
    strip.dismiss();
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
    pageChecks(window, root);
    insertChecks(root, window);
    std::cout << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
