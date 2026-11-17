// mixxx-agreed-controls.patch: the effect selector carries the dynamic
// property mixpiEmpty (true while its slot has no effect) and is re-polished
// when it changes, so a stylesheet rule can dim "Select effect…" (spec s8).
//
// usage: agreed-selector-test PRODUCTION_QSS
#include <QApplication>
#include <QFile>
#include <QPalette>
#include <iostream>
#include <stdexcept>

#include "effect_selector_stubs.h"
#include "widget/weffectselector.h"

namespace {
int failures = 0;

void check(bool ok, const char* name) {
    std::cout << (ok ? "PASS " : "FAIL ") << name << '\n';
    if (!ok) {
        ++failures;
    }
}

const QColor kDim("#010203");
const QColor kRest("#0a0b0c");
} // namespace

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    QString production;
    if (argc > 1) {
        QFile style(QString::fromLocal8Bit(argv[1]));
        if (style.open(QIODevice::ReadOnly)) {
            production = QString::fromUtf8(style.readAll());
        }
    }
    // The production style plus a probe rule of the kind the skin adds.
    app.setStyleSheet(production +
            QStringLiteral("\nWEffectSelector#MixpiEffectSelector { color: #0a0b0c; }"
                           "\nWEffectSelector#MixpiEffectSelector[mixpiEmpty=\"true\"] { color: #010203; }\n"));
    EffectsManager manager;
    for (const auto& title : {QStringLiteral("Echo"), QStringLiteral("Filter")}) {
        auto manifest = EffectManifestPointer::create();
        manifest->title = title;
        manager.effects->entries.append(manifest);
    }
    QWidget parent;
    parent.resize(800, 480);
    WEffectSelector selector(&parent, &manager);
    selector.setObjectName("MixpiEffectSelector");
    selector.setGeometry(10, 300, 250, 48);
    selector.setup(QDomNode(), SkinContext());
    parent.show();
    app.processEvents();

    auto text = [&] { return selector.palette().color(QPalette::ButtonText); };
    check(selector.property("mixpiEmpty").isValid() && selector.property("mixpiEmpty").toBool(),
            "mixpiEmpty is true for an empty slot");
    check(text() == kDim, "the [mixpiEmpty=\"true\"] rule applies to an empty selector");

    manager.slot->loadEffectWithDefaults(manager.effects->entries[0]);
    app.processEvents();
    check(!selector.property("mixpiEmpty").toBool(), "mixpiEmpty is false once an effect is loaded");
    check(text() == kRest, "the selector is re-polished: the dim rule no longer applies");
    check(selector.currentText() == QStringLiteral("Echo"), "the selector shows the loaded effect");

    manager.slot->loadEffectWithDefaults(EffectManifestPointer());
    app.processEvents();
    check(selector.property("mixpiEmpty").toBool(), "mixpiEmpty is true again after the effect is unloaded");
    check(text() == kDim, "the dim rule applies again after the unload");
    check(selector.currentText() == QStringLiteral("Select effect…"), "an empty selector reads Select effect…");

    // Picking an effect in the list itself also clears it.
    selector.setCurrentIndex(2);
    QMetaObject::invokeMethod(&selector, "activated", Qt::DirectConnection, Q_ARG(int, 2));
    app.processEvents();
    check(!selector.property("mixpiEmpty").toBool() && text() == kRest,
            "choosing an effect in the selector clears mixpiEmpty");

    // The visible list changing (populate) keeps the property right.
    emit manager.effects->visibleEffectsListChanged();
    app.processEvents();
    check(!selector.property("mixpiEmpty").toBool(), "a list refresh keeps mixpiEmpty false for a loaded slot");
    return failures ? 1 : 0;
}
