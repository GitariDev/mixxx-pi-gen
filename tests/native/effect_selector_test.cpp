#include <QAbstractItemView>
#include <QApplication>
#include <QFile>
#include <QPalette>
#include <QItemSelectionModel>
#include <QStandardItemModel>
#include <iostream>
#include <stdexcept>
#include "effect_selector_stubs.h"
#include "widget/weffectselector.h"

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    try {
        QFile style(argv[1]);
        require(style.open(QIODevice::ReadOnly), "open production style");
        app.setStyleSheet(QString::fromUtf8(style.readAll()));
        EffectsManager manager;
        for (auto title : QStringList{QStringLiteral("Echo"), QStringLiteral("Filter"),
                 QString(180, QChar('W')) + QStringLiteral(" long label holdout")}) {
            auto manifest = EffectManifestPointer::create();
            manifest->title = title;
            manager.effects->entries.append(manifest);
        }
        QWidget parent;
        parent.resize(800, 444);
        WEffectSelector selector(&parent, &manager);
        selector.setObjectName("MixpiEffectSelector");
        selector.setGeometry(10, 300, 250, 48);
        selector.setup(QDomNode(), SkinContext());
        require(selector.itemText(0) == QStringLiteral("Select effect…"), "scoped empty text");
        require(!selector.itemData(0).isValid(), "empty effect identity must stay invalid");
        require(manager.slot->loads == 0, "setup must not load an effect");
        WEffectSelector ordinary(&parent, &manager);
        ordinary.setup(QDomNode(), SkinContext());
        require(ordinary.itemText(0) == "---", "other skins keep ordinary empty text");
        parent.show();
        app.processEvents();
        selector.showPopup();
        app.processEvents();
        auto* popup = selector.view()->window();
        require(popup != &parent && popup->isWindow() && popup->isVisible(), "popup is independent, not child clipped");
        for (int height : {480, 444}) {
            selector.hidePopup();
            parent.resize(800, height);
            selector.showPopup();
            app.processEvents();
            require(selector.view()->window()->isVisible() &&
                    selector.view()->window()->isWindow(), "popup retained at both app heights");
        }
        require(selector.view()->palette().color(QPalette::Text) == QColor("#f5f6fa"), "open text contrast");
        require(selector.view()->palette().color(QPalette::Highlight) == QColor("#b5e15c"), "selected background contrast");
        require(selector.view()->palette().color(QPalette::HighlightedText) == QColor("#101318"), "selected text contrast");
        require(selector.itemData(3, Qt::ToolTipRole).toString().contains(manager.effects->entries[2]->title), "long label remains in tooltip");
        if (argc > 2) popup->grab().save(QString::fromLocal8Bit(argv[2]) + "/effect-open.png");
        selector.view()->setCurrentIndex(selector.model()->index(1, 0));
        selector.view()->selectionModel()->select(selector.model()->index(1, 0),
                QItemSelectionModel::ClearAndSelect | QItemSelectionModel::Rows);
        app.processEvents();
        if (argc > 2) popup->grab().save(QString::fromLocal8Bit(argv[2]) + "/effect-selected.png");
        selector.hidePopup();
        selector.setCurrentIndex(2);
        require(QMetaObject::invokeMethod(&selector, "activated", Qt::DirectConnection, Q_ARG(int, 2)), "native activation signal");
        require(manager.slot->loads == 1 && manager.slot->manifest == manager.effects->entries[1], "ordinary selected effect identity");
        require(ControlObject::refocus == 1, "ordinary library refocus retained");
        require(QMetaObject::invokeMethod(&selector, "activated", Qt::DirectConnection, Q_ARG(int, 0)), "empty activation signal");
        require(manager.slot->loads == 2 && !manager.slot->manifest, "empty selection still unloads effect");
        selector.setEnabled(false);
        selector.ensurePolished();
        app.processEvents();
        require(selector.palette().color(QPalette::Disabled, QPalette::ButtonText) == QColor("#a9b7c8"), "disabled contrast");
        if (argc > 2) selector.grab().save(QString::fromLocal8Bit(argv[2]) + "/effect-disabled.png");
        std::cout << "PASS exact WEffectSelector placeholder, popup/contrast, long label, identity, unload, refocus\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
