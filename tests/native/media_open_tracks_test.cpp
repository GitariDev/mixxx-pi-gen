// Build D (mixxx-table-fit-media-open.patch; spec s13, acceptance C R-4):
// OPEN and BROWSE on the Media page read the drive, "It then switches to
// Tracks." The shipped MixpiPage and mixpiClosePageToTracks run with the real
// WWidgetStack (the skin's page stack, currentpage [Tab],current, a page per
// tab trigger) and the real control framework. As in the skin, the stack's
// group is hidden while [MixPi],screen is 2 (Media) or 5 (Settings), bound
// through a ControlProxy as the skin's visible connection is.
//
// The drive's source writes [Tab],library = 1 when it has opened, while the
// page is still open (library.cpp, openRemovableSource*), then MixpiMedia's
// completion closes the page. Without the patch the page closes with
// closePage(), as on build C, and the stack shows the tab it came from.
#include <QApplication>
#include <QLabel>
#include <iostream>
#include <memory>

#include "control/controlobject.h"
#include "control/controlproxy.h"
#include "widget/mixpipage.h"
#include "widget/wwidgetstack.h"
#if __has_include("library/mixpiopentracks.h")
#include "library/mixpiopentracks.h"
#define MIXPI_OPEN_TRACKS 1
#endif

namespace {
int failures = 0;

void check(bool ok, const std::string& name) {
    std::cout << (ok ? "PASS " : "FAIL ") << name << std::endl;
    failures += ok ? 0 : 1;
}

const ConfigKey kScreen(QStringLiteral("[MixPi]"), QStringLiteral("screen"));
const ConfigKey kCurrent(QStringLiteral("[Tab]"), QStringLiteral("current"));
const char* const kTabs[] = {"overview", "library", "fx", "sampler"};

ConfigKey tab(int page) {
    return ConfigKey(QStringLiteral("[Tab]"), QString::fromLatin1(kTabs[page]));
}

// A skin tab (mixpi-performance.py tab()): its trigger, [Tab],current, then
// screen 0.
void tapTab(int page) {
    ControlObject::set(tab(page), 1);
    ControlObject::set(kCurrent, page);
    ControlObject::set(kScreen, 0);
    QApplication::processEvents();
}

// What the shipped code does when the drive has opened: library.cpp asks
// for Tracks, then MixpiMedia's completion closes the visible page.
void driveOpened(MixpiPage* page) {
    ControlObject::set(tab(1), 1);
#ifdef MIXPI_OPEN_TRACKS
    mixpiClosePageToTracks(page);
#else
    page->closePage();
#endif
    QApplication::processEvents();
}
} // namespace

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    std::vector<std::unique_ptr<ControlObject>> controls;
    controls.emplace_back(new ControlObject(kScreen));
    controls.emplace_back(new ControlObject(kCurrent));
    for (int page = 0; page < 4; ++page) {
        controls.emplace_back(new ControlObject(tab(page)));
    }
    ControlObject::set(tab(0), 1);

    QWidget window;
    window.resize(800, 480);
    auto* pages = new QWidget(&window);
    pages->setGeometry(0, 48, 800, 432);
    auto* stack = new WWidgetStack(pages, ConfigKey(), ConfigKey(), kCurrent);
    stack->resize(800, 432);
    QList<QLabel*> views;
    for (int page = 0; page < 4; ++page) {
        auto* view = new QLabel(QString::fromLatin1(kTabs[page]));
        views.append(view);
        stack->addWidgetWithControl(view, ControlObject::getControl(tab(page)), -1);
    }
    stack->Init();
    // The skin's MixpiPages: shown only while no Media (2) or Settings (5).
    ControlProxy screen(kScreen, pages);
    screen.connectValueChanged(pages, [pages](double value) {
        pages->setVisible(value != 2 && value != 5);
    });
    MixpiPage media(&window, 2, QStringLiteral("USB & Media"), QString(),
            [](double value) { ControlObject::set(kScreen, value); });
    window.show();
    QApplication::processEvents();

    auto shows = [&](int page) {
        return pages->isVisible() && stack->currentIndex() == page &&
                static_cast<int>(ControlObject::get(kCurrent)) == page &&
                ControlObject::get(tab(page)) == 1 && !media.isVisible();
    };
    check(shows(0), "start: DECKS shows");

    // OPEN from DECKS (the acceptance C repro: DECKS, the USB chip, OPEN).
    tapTab(0);
    media.openSoon();
    QApplication::processEvents();
    check(media.isVisible() && !pages->isVisible(), "the Media page covers the pages (screen 2)");
    driveOpened(&media);
    std::cout << "OBSERVE after OPEN from DECKS: page " << stack->currentIndex() << " [Tab],current "
              << ControlObject::get(kCurrent) << " [Tab],library " << ControlObject::get(tab(1))
              << " screen " << ControlObject::get(kScreen) << std::endl;
    check(shows(1), "OPEN from DECKS: the page closes and Tracks shows");
    check(ControlObject::get(kScreen) == 0, "OPEN: screen is 0 after the page closes");

    // BROWSE from SAMPLER (acceptance C: it went back to SAMPLER).
    tapTab(3);
    check(shows(3), "SAMPLER shows");
    media.openSoon();
    QApplication::processEvents();
    driveOpened(&media);
    check(shows(1), "BROWSE from SAMPLER: the page closes and Tracks shows");

    // From FX, and from Tracks itself.
    tapTab(2);
    media.openSoon();
    QApplication::processEvents();
    driveOpened(&media);
    check(shows(1), "OPEN from FX: Tracks shows");
    tapTab(1);
    media.openSoon();
    QApplication::processEvents();
    driveOpened(&media);
    check(shows(1), "OPEN from TRACKS: Tracks stays");

    // The ✕ still goes back to the tab the page was opened from.
    tapTab(0);
    media.openSoon();
    QApplication::processEvents();
    media.closeButton()->click();
    QApplication::processEvents();
    check(shows(0), "close: the red X goes back to DECKS, as before");

    std::cout << "FAILURES " << failures << std::endl;
    return failures ? 1 : 0;
}
