// media_screen fixture (R-2, R-4): the shipped MixpiPage, MixpiMediaPage and
// MixpiBottomStrip with fake drives and a fake clock, and the shipped
// MixpiUsbName text setter against the pinned Mixxx WLabel.
#include <QApplication>
#include <QDomDocument>
#include <QFile>
#include <QImage>
#include <QLabel>
#include <QPushButton>
#include <QRegularExpression>
#include <iostream>

#include "library/mixpimediapage.h"
#include "widget/wlabel.h"

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

MixpiMediaDrive drive(const QString& name, bool rekordbox = true) {
    MixpiMediaDrive result;
    result.identity = QStringLiteral("identity-") + name;
    result.name = name;
    result.size = 58600000000LL;
    result.rekordbox = rekordbox;
    MixpiMediaVolume volume;
    volume.token = QStringLiteral("token-") + name;
    volume.label = name;
    volume.path = QStringLiteral("/media/pi/") + name;
    result.volumes.append(volume);
    result.state = mixpi_media::idleState(result);
    return result;
}

void refreshState(MixpiMediaDrive* value) {
    value->state = mixpi_media::idleState(*value);
}

QList<QPushButton*> visibleButtons(QWidget* root) {
    QList<QPushButton*> result;
    for (auto* button : root->findChildren<QPushButton*>()) {
        if (button->isVisibleTo(root->window())) {
            result.append(button);
        }
    }
    return result;
}

QStringList visibleTexts(QWidget* root) {
    QStringList result;
    for (auto* label : root->findChildren<QLabel*>()) {
        result.append(label->text());
    }
    for (auto* button : root->findChildren<QPushButton*>()) {
        result.append(button->text());
    }
    return result;
}

void checkWords(QWidget* root, const std::string& where) {
    static const QRegularExpression device(QStringLiteral("\\b\\d+:\\d+\\b"));
    for (const auto& text : visibleTexts(root)) {
        for (const auto* word : {"physical", "generation", "broker", "token"}) {
            if (text.contains(QLatin1String(word), Qt::CaseInsensitive)) {
                check(false, where + ": no owner-visible label says '" + word + "': " + text.toStdString());
            }
        }
        if (device.match(text).hasMatch()) {
            check(false, where + ": no device number in a label: " + text.toStdString());
        }
    }
    check(true, where + ": no label has an internal word or a device number");
}

void checkTouch(QWidget* root, const std::string& where, int minimumWidth = 48) {
    bool ok = true;
    for (auto* button : visibleButtons(root)) {
        const auto size = button->size();
        if (size.height() < 48 || size.width() < minimumWidth) {
            ok = false;
            std::cerr << "  small button " << button->objectName().toStdString() << ' ' << size.width() << 'x'
                      << size.height() << '\n';
        }
    }
    check(ok, where + ": every button is at least " + std::to_string(minimumWidth) + "x48");
}

QPushButton* buttonNamed(QWidget* root, const QString& name, int index = 0) {
    QList<QPushButton*> found;
    for (auto* button : root->findChildren<QPushButton*>(name)) {
        found.append(button);
    }
    return found.value(index);
}

int countNamed(QWidget* root, const QString& name) {
    int count = 0;
    for (auto* widget : root->findChildren<QWidget*>(name)) {
        count += widget->isVisibleTo(root->window()) ? 1 : 0;
    }
    return count;
}

bool hasLabel(QWidget* root, const QString& text) {
    for (auto* label : root->findChildren<QLabel*>()) {
        if (label->text().contains(text) && label->isVisibleTo(root->window())) {
            return true;
        }
    }
    return false;
}

void settle() {
    for (int index = 0; index < 3; ++index) {
        QApplication::processEvents();
    }
}

void pageChecks(QWidget& window) {
    double screen = -1;
    int writes = 0;
    MixpiMediaPage page(&window, [&](double value) {
        screen = value;
        ++writes;
    });
    check(!page.isVisible(), "page host: hidden until opened");
    page.open();
    settle();
    check(page.geometry() == QRect(0, 48, 800, 432), "page host: 800x480 window gives (0,48,800,432)");
    check(screen == 2 && writes == 1, "page host: open writes [MixPi],screen 2 (Media)");
    window.resize(800, 444);
    settle();
    check(page.geometry() == QRect(0, 48, 800, 396), "page host: 800x444 window gives (0,48,800,396)");
    window.resize(800, 480);
    settle();
    check(page.geometry() == QRect(0, 48, 800, 432), "page host: follows the resize back to 800x480");
    auto* close = page.closeButton();
    check(close && close->width() >= 48 && close->height() >= 48 && close->geometry().topLeft() == QPoint(0, 0),
            "page host: the close button is 48x48 at the left of the header");
    check(page.focusPolicy() == Qt::NoFocus && close->focusPolicy() == Qt::NoFocus,
            "page host: takes no keyboard focus from Mixxx");
    const auto image = page.grab().toImage();
    const QColor corner = image.pixelColor(image.width() - 4, image.height() - 4);
    check(corner.lightness() < 40, "page host: the grabbed page has a dark background");
    close->click();
    check(!page.isVisible() && screen == 0, "page host: the close button hides the page and writes screen 0");
    page.open();
    writes = 0;
    page.screenChanged(0); // a tab tap in the top bar
    check(!page.isVisible() && writes == 0, "page host: a tab writing screen 0 closes the page without a second write");
    page.open();
    page.screenChanged(2);
    check(page.isVisible(), "page host: its own number keeps it open");
    page.closePage();

    // Drives.
    QStringList opened;
    QStringList ejected;
    page.openRequested = [&](QString identity, QString token) { opened.append(identity + '|' + token); };
    page.ejectRequested = [&](QString identity) { ejected.append(identity); };
    page.open();
    page.setDrives({});
    settle();
    check(countNamed(&page, QStringLiteral("MixpiMediaCard")) == 1 && hasLabel(&page, QStringLiteral("No USB drive")),
            "media page: no drive shows the one empty card");
    check(mixpi_media::chipState({}) == MixpiMediaState::None, "media_state: 0 with no drive");
    auto one = drive(QStringLiteral("MANTACORE"));
    page.setDrives({one});
    settle();
    check(countNamed(&page, QStringLiteral("MixpiMediaCard")) == 1 && hasLabel(&page, QStringLiteral("MANTACORE")) &&
                    hasLabel(&page, QStringLiteral("58.6 GB · rekordbox export found")) &&
                    hasLabel(&page, QStringLiteral("READY")),
            "media page: one drive shows one card with name, size, export and state pill");
    check(mixpi_media::chipState({one}) == MixpiMediaState::Ready && mixpi_media::chipName({one}) == "MANTACORE",
            "media_state: 1 ready for a drive nothing uses; chip name is the drive name");
    auto two = drive(QStringLiteral("SPARE"), false);
    page.setDrives({one, two});
    settle();
    check(countNamed(&page, QStringLiteral("MixpiMediaCard")) == 2 && hasLabel(&page, QStringLiteral("folders")),
            "media page: two drives show two cards (one with folders)");
    page.setDrives({one});
    settle();
    auto* open = buttonNamed(&page, QStringLiteral("MixpiMediaOpen"));
    check(open && open->text() == "OPEN" && open->isEnabled(), "media page: OPEN for a drive not yet open");
    open->click();
    check(opened == QStringList{QStringLiteral("identity-MANTACORE|token-MANTACORE")},
            "media page: OPEN calls the open callback once with that drive's volume");
    auto busy = one;
    busy.busy = true;
    refreshState(&busy);
    check(mixpi_media::chipState({busy}) == MixpiMediaState::InUse, "media_state: 2 in use while the registry counts a use");
    busy.busy = false;
    refreshState(&busy);
    check(mixpi_media::chipState({busy}) == MixpiMediaState::Ready, "media_state: back to 1 when the use ends");
    auto openedDrive = one;
    openedDrive.opened = true;
    openedDrive.volumes[0].opened = true;
    refreshState(&openedDrive);
    page.setDrives({openedDrive});
    settle();
    check(buttonNamed(&page, QStringLiteral("MixpiMediaOpen"))->text() == "BROWSE" &&
                    mixpi_media::chipState({openedDrive}) == MixpiMediaState::InUse,
            "media page: an opened drive shows BROWSE and state 2");
    auto ejecting = one;
    ejecting.state = MixpiMediaState::Ejecting;
    auto safe = two;
    safe.state = MixpiMediaState::SafeToRemove;
    check(mixpi_media::chipState({openedDrive, ejecting}) == MixpiMediaState::Ejecting &&
                    mixpi_media::chipState({openedDrive, safe}) == MixpiMediaState::SafeToRemove &&
                    mixpi_media::chipName({openedDrive, safe}) == "SPARE",
            "media_state: 3 ejecting and 4 safe to remove win the chip");
    check(buttonNamed(&page, QStringLiteral("MixpiMediaCopy")) &&
                    !buttonNamed(&page, QStringLiteral("MixpiMediaRefresh")) && !hasLabel(&page, QStringLiteral("Scan")),
            "media page: COPY TO PI; no Scan, no Refresh");

    // Gate closed.
    page.setEjectAvailable(false);
    page.setDrives({one});
    settle();
    auto* eject = buttonNamed(&page, QStringLiteral("MixpiMediaEject"));
    check(eject && !eject->isEnabled() && hasLabel(&page, QStringLiteral("Eject is off on this card.")),
            "gate closed: EJECT is disabled and says Eject is off on this card.");
    eject->click();
    check(!page.sheetVisible() && ejected.isEmpty(), "gate closed: a tap on EJECT does nothing");

    // Gate open, with users.
    auto used = one;
    used.users = {{QStringLiteral("[Channel1]"), QStringLiteral("Frontin' The Best"), true, true},
            {QStringLiteral("[Sampler3]"), QStringLiteral("Air horn.wav"), false, true},
            {QStringLiteral("[Channel2]"), QStringLiteral("Whipped Cream"), false, false}};
    refreshState(&used);
    page.setEjectAvailable(true);
    page.setDrives({used});
    settle();
    eject = buttonNamed(&page, QStringLiteral("MixpiMediaEject"));
    check(eject->isEnabled() && hasLabel(&page, QStringLiteral("Deck 1 is playing")) &&
                    hasLabel(&page, QStringLiteral("Pad 3 holds")),
            "gate open: EJECT is enabled and the card lists who uses the drive");
    eject->click();
    settle();
    auto* sheet = page.sheet();
    check(page.sheetVisible() && hasLabel(sheet, QStringLiteral("Eject MANTACORE?")) &&
                    hasLabel(sheet, QStringLiteral("keeps playing from its Pi copy")) &&
                    hasLabel(sheet, QStringLiteral("stays loaded from its Pi copy")) &&
                    hasLabel(sheet, QStringLiteral("will be unloaded")),
            "eject sheet: one line per user with what happens to it");
    checkTouch(sheet, "eject sheet");
    const auto confirmCenter = buttonNamed(sheet, QStringLiteral("MixpiEjectConfirm"))
                                       ->mapTo(&window, buttonNamed(sheet, QStringLiteral("MixpiEjectConfirm"))->rect().center());
    const auto cancelCenter = buttonNamed(sheet, QStringLiteral("MixpiEjectCancel"))
                                      ->mapTo(&window, buttonNamed(sheet, QStringLiteral("MixpiEjectCancel"))->rect().center());
    std::cout << "COORD sheet EJECT " << confirmCenter.x() << ',' << confirmCenter.y() << " CANCEL "
              << cancelCenter.x() << ',' << cancelCenter.y() << '\n';
    const auto ejectCenter = eject->mapTo(&window, eject->rect().center());
    std::cout << "COORD card EJECT " << ejectCenter.x() << ',' << ejectCenter.y() << '\n';
    buttonNamed(sheet, QStringLiteral("MixpiEjectCancel"))->click();
    check(!page.sheetVisible() && ejected.isEmpty(), "eject sheet: CANCEL closes it and ejects nothing");
    eject->click();
    buttonNamed(sheet, QStringLiteral("MixpiEjectConfirm"))->click();
    settle();
    check(ejected == QStringList{QStringLiteral("identity-MANTACORE")} &&
                    hasLabel(sheet, QStringLiteral("Stop new reads from MANTACORE")) &&
                    hasLabel(sheet, QStringLiteral("Keep 2 items playing from their Pi copies")) &&
                    hasLabel(sheet, QStringLiteral("Close Mixxx’s files on the drive")) &&
                    hasLabel(sheet, QStringLiteral("Unmount and check")),
            "eject steps: EJECT starts the engine once and shows the four steps");
    check(buttonNamed(sheet, QStringLiteral("MixpiEjectCancel"))->isEnabled(), "eject steps: Cancel works before the unmount");
    page.setEjectStep(MixpiMediaPage::Step::Unmount);
    check(!buttonNamed(sheet, QStringLiteral("MixpiEjectCancel"))->isEnabled(), "eject steps: no Cancel once the unmount starts");
    page.setEjectStep(MixpiMediaPage::Step::Done);
    settle();
    check(hasLabel(sheet, QStringLiteral("Safe to remove MANTACORE")) &&
                    buttonNamed(sheet, QStringLiteral("MixpiEjectDone"))->isEnabled(),
            "eject steps: the end state is Safe to remove with DONE");
    buttonNamed(sheet, QStringLiteral("MixpiEjectDone"))->click();
    eject->click();
    buttonNamed(sheet, QStringLiteral("MixpiEjectConfirm"))->click();
    page.setEjectFailed(QStringLiteral("Not ejected. The drive is still in use."));
    settle();
    check(hasLabel(sheet, QStringLiteral("Not ejected. The drive is still in use.")) &&
                    buttonNamed(sheet, QStringLiteral("MixpiEjectDone"))->isEnabled(),
            "eject steps: a failure says Not ejected. The drive is still in use.");
    page.hideSheet();

    auto blocked = used;
    blocked.users[2].playing = true; // Deck 2 plays straight from the drive
    page.setDrives({blocked});
    settle();
    eject = buttonNamed(&page, QStringLiteral("MixpiMediaEject"));
    check(!eject->isEnabled() && hasLabel(&page, QStringLiteral("straight from the drive")),
            "stop it first: a deck playing straight from the drive disables EJECT");
    page.showEjectSheet(blocked.identity);
    check(hasLabel(sheet, QStringLiteral("plays straight from the drive: stop it first")) &&
                    !buttonNamed(sheet, QStringLiteral("MixpiEjectConfirm"))->isEnabled(),
            "stop it first: the sheet names the deck and its EJECT is disabled");
    page.hideSheet();

    // Handover column.
    page.setHandover({}, {});
    settle();
    check(hasLabel(&page, QStringLiteral("Nothing yet.")), "handover: empty list says Nothing yet.");
    page.setHandover({{QStringLiteral("[Channel1]"), QStringLiteral("Frontin' The Best")},
                             {QStringLiteral("[Sampler3]"), QStringLiteral("Air horn.wav")}},
            {QStringLiteral("Old track")});
    settle();
    check(countNamed(&page, QStringLiteral("MixpiMediaOnPiRow")) == 2 && hasLabel(&page, QStringLiteral("PAD 3")) &&
                    hasLabel(&page, QStringLiteral("Old track")),
            "handover: the list follows the on-Pi flags and Cleaned out");
    checkWords(&page, "media page");
    page.setDrives({used, two});
    settle();
    checkTouch(&page, "media page");
    checkWords(&page, "media page with users");
}

void stripChecks(QWidget& window) {
    qint64 now = 1000;
    MixpiBottomStrip strip(&window, [&] { return now; });
    QStringList loads;
    QStringList dismissals;
    strip.loadRequested = [&](QString identity) { loads.append(identity); };
    strip.dismissed = [&](QString identity) { dismissals.append(identity); };
    check(mixpi_media::shouldPing(true, false, false, true, false, false), "ping: a new mounted drive that is not open");
    check(!mixpi_media::shouldPing(true, false, false, true, true, false), "ping: not for a drive that is already open");
    check(!mixpi_media::shouldPing(false, false, false, true, false, false), "ping: not for a drive found at start-up");
    check(!mixpi_media::shouldPing(true, true, false, true, false, false), "ping: not again for a drive already here");
    check(!mixpi_media::shouldPing(true, false, false, true, false, true), "ping: not while the Media page is open");
    strip.showPing(QStringLiteral("identity-A"), QStringLiteral("Mantacore"),
            QStringLiteral("rekordbox export found · 58.6 GB"));
    settle();
    check(strip.isVisible() && strip.geometry() == QRect(0, 424, 800, 56),
            "ping: a 56 px strip over the bottom row of the 800x480 window");
    check(hasLabel(&strip, QStringLiteral("MANTACORE PLUGGED IN")) &&
                    hasLabel(&strip, QStringLiteral("rekordbox export found · 58.6 GB")),
            "ping: NAME PLUGGED IN with the export and size line");
    check(!window.findChild<QWidget*>(QStringLiteral("MixpiMediaScrim")) || !window.findChild<QWidget*>(QStringLiteral("MixpiMediaScrim"))->isVisible(),
            "ping: no sheet and no scrim");
    checkTouch(&strip, "ping", 96);
    auto* load = buttonNamed(&strip, QStringLiteral("MixpiStripLoad"));
    check(load && load->property("primary").toBool() && buttonNamed(&strip, QStringLiteral("MixpiStripDismiss"))->isVisible(),
            "ping: LOAD (primary) and DISMISS");
    const auto loadCenter = load->mapTo(&window, load->rect().center());
    const auto dismissButton = buttonNamed(&strip, QStringLiteral("MixpiStripDismiss"));
    const auto dismissCenter = dismissButton->mapTo(&window, dismissButton->rect().center());
    std::cout << "COORD ping LOAD " << loadCenter.x() << ',' << loadCenter.y() << " DISMISS " << dismissCenter.x()
              << ',' << dismissCenter.y() << '\n';
    load->click();
    check(!strip.isVisible() && loads == QStringList{QStringLiteral("identity-A")} && dismissals.isEmpty(),
            "ping: LOAD opens the drive and hides the strip");
    strip.showPing(QStringLiteral("identity-B"), QStringLiteral("SPARE"), QStringLiteral("folders · 8.0 GB"));
    buttonNamed(&strip, QStringLiteral("MixpiStripDismiss"))->click();
    check(!strip.isVisible() && dismissals == QStringList{QStringLiteral("identity-B")} && loads.size() == 1,
            "ping: DISMISS hides it and leaves the drive closed");
    strip.showPing(QStringLiteral("identity-C"), QStringLiteral("SPARE"), QStringLiteral("folders"));
    now += 14900;
    strip.tick();
    check(strip.isVisible(), "ping: still there at 14.9 s");
    now += 200;
    strip.tick();
    check(!strip.isVisible() && dismissals.size() == 2 && loads.size() == 1, "ping: auto-dismiss after 15 s, as DISMISS");

    // Safe to remove.
    strip.showSafe(QStringLiteral("identity-A"), QStringLiteral("Mantacore"));
    settle();
    check(strip.isVisible() && strip.kind() == MixpiBottomStrip::Kind::Safe &&
                    hasLabel(&strip, QStringLiteral("MANTACORE · SAFE TO REMOVE")) &&
                    hasLabel(&strip, QStringLiteral("Pull the drive out now.")) &&
                    buttonNamed(&strip, QStringLiteral("MixpiStripOk"))->isVisible(),
            "safe strip: shows on state 4 with OK");
    check(strip.property("kind").toString() == "safe", "safe strip: styled as the green strip");
    checkTouch(&strip, "safe strip", 96);
    strip.showPing(QStringLiteral("identity-D"), QStringLiteral("OTHER"), QStringLiteral("folders"));
    check(strip.kind() == MixpiBottomStrip::Kind::Safe, "safe strip: a ping does not replace it");
    strip.driveGone(QStringLiteral("identity-other"));
    check(strip.isVisible(), "safe strip: another drive going does not hide it");
    strip.driveGone(QStringLiteral("identity-A"));
    check(!strip.isVisible(), "safe strip: hides when the drive is pulled out");
    strip.showSafe(QStringLiteral("identity-A"), QStringLiteral("Mantacore"));
    now += 29900;
    strip.tick();
    check(strip.isVisible(), "safe strip: still there at 29.9 s");
    now += 200;
    strip.tick();
    check(!strip.isVisible(), "safe strip: hides after 30 s");
    strip.showSafe(QStringLiteral("identity-A"), QStringLiteral("Mantacore"));
    buttonNamed(&strip, QStringLiteral("MixpiStripOk"))->click();
    check(!strip.isVisible(), "safe strip: OK hides it");
    window.resize(800, 444);
    strip.showSafe(QStringLiteral("identity-A"), QStringLiteral("Mantacore"));
    settle();
    check(strip.geometry() == QRect(0, 388, 800, 56), "safe strip: at the bottom of an 800x444 window");
    window.resize(800, 480);
    settle();
    check(strip.geometry() == QRect(0, 424, 800, 56), "safe strip: follows the resize");
    checkWords(&strip, "bottom strip");
}

void labelChecks() {
    // The not-confirmed step (R-4): set the text of the skin's MixpiUsbName
    // Label from native code and read it back after what a skin does to it.
    for (const auto* elide : {"none", "right"}) {
        QWidget chip;
        chip.resize(150, 48);
        QDomDocument document;
        document.setContent(QStringLiteral("<Label><ObjectName>MixpiUsbName</ObjectName><Text>USB</Text>"
                                           "<Elide>%1</Elide></Label>")
                                    .arg(QLatin1String(elide)));
        const auto node = document.documentElement();
        SkinContext context;
        auto* label = new WLabel(&chip);
        label->setObjectName(context.selectString(node, QStringLiteral("ObjectName")));
        label->setup(node, context);
        label->setGeometry(36, 4, 110, 20);
        chip.show(); // resize and font events reach a shown Label only
        settle();
        const std::string mode = std::string(" (Elide ") + elide + ")";
        check(label->text() == "USB", "usb name: the skin's default text is USB" + mode);
        check(mixpiSetNamedLabelText<WLabel>(&chip, QStringLiteral("MixpiUsbName"), QStringLiteral("MANTACORE")) == 1,
                "usb name: the setter finds the Label by its object name" + mode);
        label->resize(100, 20);
        auto font = label->font();
        font.setPixelSize(15);
        label->setFont(font);
        chip.setStyleSheet(QStringLiteral("QLabel { font-size: 16px; }"));
        label->setHighlight(1);
        label->setVisible(false);
        label->setVisible(true);
        settle();
        check(label->text() == "MANTACORE" && label->QLabel::text().startsWith(QStringLiteral("MANT")),
                "usb name: the text stays after a resize, a font change, a style change and a visibility change" + mode);
        // Why QLabel::setText is not used: WLabel puts its own text back on a resize.
        static_cast<QLabel*>(label)->setText(QStringLiteral("SPARE"));
        label->resize(110, 20);
        settle();
        check(label->QLabel::text() != "SPARE", "usb name: QLabel::setText would be undone by a resize" + mode);
        // A skin reload makes a new Label; the next refresh sets it again.
        delete label;
        auto* reloaded = new WLabel(&chip);
        reloaded->setObjectName(QStringLiteral("MixpiUsbName"));
        reloaded->setup(node, context);
        check(reloaded->text() == "USB", "usb name: a reloaded skin starts at USB" + mode);
        mixpiSetNamedLabelText<WLabel>(&chip, QStringLiteral("MixpiUsbName"), QStringLiteral("MANTACORE"));
        check(reloaded->text() == "MANTACORE", "usb name: the next refresh sets the reloaded Label" + mode);
    }
}
} // namespace

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    QString style;
    for (const auto& path : qEnvironmentVariable("MIXPI_SKIN_QSS").split(':', Qt::SkipEmptyParts)) {
        QFile file(path);
        if (file.open(QIODevice::ReadOnly)) {
            style += QString::fromUtf8(file.readAll());
        }
    }
    check(!style.isEmpty(), "the menu style sheet is loaded");
    QWidget window;
    window.setObjectName(QStringLiteral("MixxxMainWindowDouble"));
    window.setStyleSheet(style);
    window.resize(800, 480);
    window.show();
    settle();
    pageChecks(window);
    stripChecks(window);
    labelChecks();
    std::cout << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
