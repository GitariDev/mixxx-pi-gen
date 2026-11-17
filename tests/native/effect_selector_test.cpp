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
        // The open list takes the agreed token colours of every list: text
        // #e4e7ec on surface #161a20; the current effect is the current menu
        // row, surface-2 #1d222a (its accent edge is the item rule's).
        require(selector.view()->palette().color(QPalette::Text) == QColor("#e4e7ec"), "open text colour");
        require(selector.view()->palette().color(QPalette::Base) == QColor("#161a20"), "open list surface");
        require(selector.view()->palette().color(QPalette::Highlight) == QColor("#1d222a"), "current row surface-2");
        require(selector.view()->palette().color(QPalette::HighlightedText) == QColor("#e4e7ec"), "current row text");
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
        require(selector.palette().color(QPalette::Disabled, QPalette::ButtonText) == QColor("#7f8896"), "disabled text-off");
        // N-C's mixpiEmpty: the empty selector's text is dim (m-fx.png).
        selector.setEnabled(true);
        selector.setProperty("mixpiEmpty", true);
        selector.style()->unpolish(&selector);
        selector.style()->polish(&selector);
        app.processEvents();
        require(selector.palette().color(QPalette::Active, QPalette::ButtonText) == QColor("#949dab"), "empty selector is dim");
        selector.setProperty("mixpiEmpty", false);
        selector.style()->unpolish(&selector);
        selector.style()->polish(&selector);
        app.processEvents();
        require(selector.palette().color(QPalette::Active, QPalette::ButtonText) == QColor("#e4e7ec"), "loaded selector is light");
        if (argc > 2) selector.grab().save(QString::fromLocal8Bit(argv[2]) + "/effect-disabled.png");
        std::cout << "PASS exact WEffectSelector placeholder, popup token colours, empty dim, long label, identity, unload, refocus\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
