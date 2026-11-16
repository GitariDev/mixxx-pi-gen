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

    // A saved "both" (old profile, or chosen in Preferences) is still shown.
    mode.set(kBoth);
    application.processEvents();
    require(both(deck1.text()) && both(deck2.text()), "saved 2 still shows both");
    stored.clear();
    press(deck1);
    require(mode.get() == kElapsed && elapsed(deck1.text()), "tap 2 -> 0 (elapsed)");
    for (int tap = 0; tap < 6; ++tap) {
        press(tap % 2 ? deck2 : deck1);
    }
    require(stored == std::vector<double>({0, 1, 0, 1, 0, 1, 0}), "taps after 2 toggle 0/1 only");

    // A widget built while the saved mode is 2 starts there; its first tap gives elapsed.
    mode.set(kBoth);
    WNumberPos fresh("[Channel1]");
    require(both(fresh.text()), "new widget shows saved 2");
    press(fresh);
    require(mode.get() == kElapsed && elapsed(fresh.text()) && elapsed(deck2.text()),
            "first tap from saved 2 -> 0 on every deck");
    std::cout << "CHECKS " << checks << " FAILURES " << failures << '\n';
    return failures ? 1 : 0;
}
