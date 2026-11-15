#include <QApplication>
#include <QDomDocument>
#include <QImage>
#include <QPainter>
#include <QGridLayout>
#include <iostream>

#include "widget/wkey.h"
#include "track/keyutils.h"
#include "skin/legacy/skincontext.h"

static int failures = 0;
static int checks = 0;

static void require(bool condition, const char* name) {
    ++checks;
    if (!condition) {
        ++failures;
        std::cerr << "FAIL " << name << '\n';
    }
}

static void setup(WKey& widget, const QString& contents) {
    QDomDocument document;
    require(bool(document.setContent("<Key>" + contents + "</Key>")), "valid fixture XML");
    widget.setup(document.documentElement(), SkinContext());
}

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    KeyUtils::setNotation({{mixxx::track::io::key::C_MAJOR, "owner-C"}});
    WKey paired("[Channel1]");
    WKey ordinary("[Channel2]");
    setup(paired, "<PairedNotation>true</PairedNotation>");
    setup(ordinary, "");
    paired.onConnectedControlChanged(0, 1);
    ordinary.onConnectedControlChanged(0, 1);
    require(paired.text() == "8B (C)", "paired native formatter");
    require(ordinary.text() == "owner-C", "ordinary custom notation preserved");
    for (int key = 1; key <= 24; ++key) {
        paired.onConnectedControlChanged(0, key);
        const auto expected = KeyUtils::keyToString(static_cast<ChromaticKey>(key),
                KeyUtils::KeyNotation::LancelotAndTraditional);
        require(paired.text() == expected, "all 24 keys use native paired formatter");
    }
    paired.onConnectedControlChanged(0, 7);
    require(paired.text() == QString::fromUtf8("2B (F♯/G♭)"), "enharmonic label");
    const auto longLabel = paired.text();
    paired.resize(120, 30);
    require(paired.fontMetrics().horizontalAdvance(longLabel) <= paired.width(),
            "long label fits 120px isolated Qt label");
    paired.onConnectedControlChanged(0, -1);
    require(paired.text().isEmpty(), "invalid key clears label");
    setup(paired, "<PairedNotation>true</PairedNotation><DisplayCents>true</DisplayCents>");
    ControlProxy::cents = -0.25;
    paired.onConnectedControlChanged(0, 1);
    require(paired.text() == "8B (C) -25c", "cents retained");
    setup(paired, "<PairedNotation>true</PairedNotation><DisplayKey>false</DisplayKey>");
    paired.onConnectedControlChanged(0, 1);
    require(paired.text().isEmpty(), "hidden key remains hidden");
    setup(paired, "<PairedNotation>true</PairedNotation>");
    paired.onConnectedControlChanged(0, 7);
    setup(paired, "");
    require(paired.text() == KeyUtils::keyToString(static_cast<ChromaticKey>(7)),
            "setup refresh restores custom/default notation");
    if (argc > 1) {
        for (const int height : {444, 480}) {
            QWidget surface;
            surface.setStyleSheet("QWidget { background: #071426; color: #dbe9f6; } QLabel { font: 14px sans-serif; }");
            surface.resize(800, height);
            auto* layout = new QGridLayout(&surface);
            layout->addWidget(new QLabel("Isolated WKey + real extracted formatter; not full Mixxx/Pi"), 0, 0, 1, 4);
            for (int key = 1; key <= 24; ++key) {
                auto* label = new WKey("[Channel1]", &surface);
                setup(*label, "<PairedNotation>true</PairedNotation>");
                label->onConnectedControlChanged(0, key);
                layout->addWidget(label, 1 + (key - 1) / 4, (key - 1) % 4);
            }
            surface.show();
            application.processEvents();
            require(surface.size() == QSize(800, height), "isolated render dimensions retained");
            require(surface.grab().save(QString::fromLocal8Bit(argv[1]) +
                    QString("/key-widget-%1.png").arg(height)), "saved isolated render");
        }
    }
    std::cout << "CHECKS " << checks << " FAILURES " << failures << '\n';
    return failures ? 1 : 0;
}
