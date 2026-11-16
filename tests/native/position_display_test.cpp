#include <QApplication>
#include <QMouseEvent>
#include <iostream>
#include <vector>

#include "control/controlobject.h"
#include "preferences/dialog/dlgprefdeck.h"
#include "widget/wnumberpos.h"

static int checks = 0;
static int failures = 0;

static void require(bool condition, const char* name) {
    ++checks;
    if (!condition) {
        ++failures;
        std::cerr << "FAIL " << name << '\n';
    }
}

static void press(QWidget& widget, Qt::MouseButton button = Qt::LeftButton) {
    QMouseEvent event(QEvent::MouseButtonPress, QPointF(4, 4), widget.mapToGlobal(QPointF(4, 4)),
            button, button, Qt::NoModifier);
    QApplication::sendEvent(&widget, &event);
}

static bool elapsed(const QString& text) {
    return !text.isEmpty() && !text.startsWith('-') && !text.contains("  -");
}
static bool remaining(const QString& text) {
    return text.startsWith('-') && !text.contains("  -");
}
static bool both(const QString& text) {
    return text.contains("  -");
}

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    constexpr double kElapsed = 0, kRemaining = 1, kBoth = 2;
    static_assert(static_cast<int>(TrackTime::DisplayMode::ELAPSED) == 0 &&
            static_cast<int>(TrackTime::DisplayMode::REMAINING) == 1 &&
            static_cast<int>(TrackTime::DisplayMode::ELAPSED_AND_REMAINING) == 2);
    // DlgPrefDeck owns this control and writes [Controls] PositionDisplay
    // from its valueChanged signal (PIN src/preferences/dialog/dlgprefdeck.cpp:81-85, 640-642).
    ControlObject mode(ConfigKey("[Controls]", "ShowDurationRemaining"));
    ControlObject format(ConfigKey("[Controls]", "TimeFormat"));
    std::vector<double> stored;
    QObject receiver;
    QObject::connect(&mode, &ControlObject::valueChanged, &receiver,
            [&](double value) { stored.push_back(value); });
    ControlObject elapsed1(ConfigKey("[Channel1]", "time_elapsed"));
    ControlObject remaining1(ConfigKey("[Channel1]", "time_remaining"));
    ControlObject elapsed2(ConfigKey("[Channel2]", "time_elapsed"));
    ControlObject remaining2(ConfigKey("[Channel2]", "time_remaining"));
    remaining1.set(754.25);
    remaining2.set(300.5);
    elapsed1.set(65.5);
    elapsed2.set(12.0);

    mode.set(kElapsed);
    stored.clear();
    WNumberPos deck1("[Channel1]");
    WNumberPos deck2("[Channel2]");
    application.processEvents();
    require(elapsed(deck1.text()), "saved 0 shows elapsed only");
    press(deck1);
    require(mode.get() == kRemaining && remaining(deck1.text()), "tap 0 -> 1 (remaining)");
    require(remaining(deck2.text()), "other deck follows the shared mode");
    press(deck1);
    require(mode.get() == kElapsed && elapsed(deck1.text()), "tap 1 -> 0 (elapsed)");
    press(deck2);
    require(mode.get() == kRemaining, "tap on deck 2 -> 1");
    press(deck2);
    require(mode.get() == kElapsed && elapsed(deck2.text()), "tap on deck 2 -> 0");
    require(stored == std::vector<double>({1, 0, 1, 0}), "stored sequence 0 -> 1 -> 0, never 2");
    press(deck1, Qt::RightButton);
    require(mode.get() == kElapsed, "right button does not change the mode");

    // F-5 (owner decision 4.1, council round 1): a saved "both" (Mixxx's
    // default for a new profile, PIN dlgprefdeck.cpp:26-27, or chosen in
    // Preferences) shows elapsed only; a deck never shows both times.
    mode.set(kBoth);
    application.processEvents();
    std::cout << "OBSERVE saved 2: deck 1 '" << deck1.text().toStdString() << "', deck 2 '"
              << deck2.text().toStdString() << "'\n";
    require(elapsed(deck1.text()) && elapsed(deck2.text()), "saved 2 shows elapsed only, never both");
    elapsed1.set(130.0);
    remaining1.set(689.75);
    application.processEvents();
    require(elapsed(deck1.text()) && !both(deck1.text()), "saved 2 stays elapsed only as the track plays");
    require(mode.get() == kBoth, "showing saved 2 as elapsed does not rewrite the setting");
    stored.clear();
    press(deck1);
    require(mode.get() == kRemaining && remaining(deck1.text()) && remaining(deck2.text()),
            "tap from saved 2 -> 1 (remaining), the next time after elapsed");
    for (int tap = 0; tap < 6; ++tap) {
        press(tap % 2 ? deck2 : deck1);
        require(!both(deck1.text()) && !both(deck2.text()), "no tap after saved 2 shows both");
    }
    require(stored == std::vector<double>({1, 0, 1, 0, 1, 0, 1}), "taps after 2 toggle 1/0 only");

    // A widget built while the saved mode is 2 shows elapsed; its first tap gives remaining.
    mode.set(kBoth);
    WNumberPos fresh("[Channel1]");
    require(elapsed(fresh.text()) && !both(fresh.text()), "new widget with saved 2 shows elapsed only");
    press(fresh);
    require(mode.get() == kRemaining && remaining(fresh.text()) && remaining(deck2.text()),
            "first tap from saved 2 -> 1 (remaining) on every deck");
    press(fresh);
    require(mode.get() == kElapsed && elapsed(fresh.text()), "the toggle continues 1 -> 0 (elapsed)");
    std::cout << "CHECKS " << checks << " FAILURES " << failures << '\n';
    return failures ? 1 : 0;
}
