#include <QApplication>
#include <QAbstractItemModelTester>
#include <QMouseEvent>
#include <QPersistentModelIndex>
#include <QPointer>
#include <QSettings>
#include <QTemporaryDir>
#include <QTest>
#include <algorithm>
#include <iostream>
#include <memory>

#include "library/libraryfeature.h"
#include "library/sidebarmodel.h"
#include "library/sourceorder.h"
#include "library/treeitem.h"
#include "widget/libraryinterface.h"

int failures = 0;
void require(bool condition, const char* name) {
    std::cout << (condition ? "PASS " : "FAIL ") << name << std::endl;
    failures += !condition;
}

LibraryFeature::LibraryFeature(QString name) : identity(std::move(name)) {
    auto root = TreeItem::newRoot(this);
    root->appendChild("folder")->appendChild("nested");
    children.setRootItem(std::move(root));
}

#include "preferences/configobject.h"
#ifndef SOURCE_ORDER_BASELINE
#include "widget/wlibrarysidebar.h"
#endif
struct Settings {
    QSettings settings;
    explicit Settings(const QString& path) : settings(path, QSettings::IniFormat) {}
    QString getValueString(const ConfigKey& key) { return settings.value(key.key).toString(); }
    bool getValue(const ConfigKey& key, bool fallback) { return settings.value(key.key, fallback).toBool(); }
    void setValue(const ConfigKey& key, const QVariant& value) { settings.setValue(key.key, value); settings.sync(); }
};
const QString kConfigGroup = "Library";
class SidebarView : public QTreeView {
  public:
    void returnToSourceRoot() { setRootIndex({}); }
    void selectIndex(const QModelIndex& index) { setCurrentIndex(index); }
};
class Library : public QObject {
  public:
    struct SidebarSource {
        QString id;
        QString title;
        ConfigKey preference;
        LibraryFeature* feature;
        std::function<LibraryFeature*()> create;
    };
    Settings* m_pConfig;
    SidebarModel* m_pSidebarModel;
    SidebarView* m_pSidebarWidget = nullptr;
    QWidget* m_pLibraryWidget = nullptr;
    QObject* m_pSidebarKeyboard = nullptr;
    QPointer<QMenu> m_pSidebarSourcesMenu;
    QFont m_trackTableFont;
    int m_iTrackTableRowHeight = 24;
    bool m_editMetadataSelectedClick = false;
    QList<SidebarSource> m_sidebarSources;
    QList<LibraryFeature*> m_features;
    Library(Settings* settings, SidebarModel* model) : m_pConfig(settings), m_pSidebarModel(model) {}
    void applySidebarSourceOrder();
    void saveSidebarSourceOrder(const QStringList& identities);
    void applySidebarSourceVisibility();
    void showSidebarSourcesMenu();
    void onSkinLoadFinished();
    void setTrackTableFont(const QFont&) {}
    void setTrackTableRowHeight(int) {}
    void setSelectedClick(bool) {}
    void addFeature(LibraryFeature* feature) { add(feature); }
    void add(LibraryFeature* feature) {
        auto found = std::find_if(m_sidebarSources.begin(), m_sidebarSources.end(),
                [feature](const SidebarSource& source) { return source.id == feature->identity; });
        if (found == m_sidebarSources.end()) {
            m_sidebarSources.append({feature->identity, feature->identity,
                    ConfigKey(kConfigGroup, "SidebarSource" + feature->identity), feature, {}});
        } else {
            found->feature = feature;
        }
        m_features.append(feature);
        m_pSidebarModel->addLibraryFeature(feature);
#ifndef SOURCE_ORDER_BASELINE
        applySidebarSourceOrder();
        applySidebarSourceVisibility();
#endif
    }
    QStringList order() const {
        QStringList result;
        for (auto* feature : m_features) { result.append(feature->identity); }
        return result;
    }
};
#ifndef SOURCE_ORDER_BASELINE
#include "library_order_methods.h"
#else
void Library::applySidebarSourceOrder() {}
void Library::saveSidebarSourceOrder(const QStringList&) {}
void Library::applySidebarSourceVisibility() {}
void Library::showSidebarSourcesMenu() {}
void Library::onSkinLoadFinished() {}
#endif

#ifndef SOURCE_ORDER_BASELINE
// F-6 (B3): the real WLibrarySidebar in touch navigation mode, wired to the
// real SidebarModel by the exact pressed/clicked connects from library.cpp.
void mouse(QWidget* widget, QEvent::Type type, QPoint position, Qt::MouseButtons buttons) {
    QMouseEvent event(type, position, widget->mapToGlobal(position),
            type == QEvent::MouseMove ? Qt::NoButton : Qt::LeftButton, buttons, Qt::NoModifier);
    QApplication::sendEvent(widget, &event);
}

void touchSidebarChecks() {
    SidebarModel model;
    A a;
    B b;
    C c;
    D d;
    E e;
    const QList<LibraryFeature*> features{&a, &b, &c, &d, &e};
    for (auto* feature : features) {
        model.addLibraryFeature(feature);
    }
    LibraryFeature::shown = nullptr;
    WLibrarySidebar sidebar;
    sidebar.setModel(&model);
    {
        WLibrarySidebar* pSidebarWidget = &sidebar;
        SidebarModel* m_pSidebarModel = &model;
        auto connect = [](auto&&... arguments) { return QObject::connect(arguments...); };
#include "sidebar_activation_wiring.inc"
    }
    QObject::connect(&model, &SidebarModel::selectIndex, &sidebar, &WLibrarySidebar::selectIndex);
    sidebar.enableTouchNavigation();
    sidebar.resize(300, 400);
    sidebar.show();
    QApplication::processEvents();
    auto* viewport = sidebar.viewport();
    auto opened = [&] {
        int count = 0;
        for (auto* feature : features) {
            count += feature->activations;
        }
        return count;
    };
    auto row = [&](int number) { return model.index(number, 0); };
    auto centre = [&](const QModelIndex& index) { return sidebar.visualRect(index).center(); };
    auto highlighted = [&](const QModelIndex& index) {
        return sidebar.currentIndex() == index &&
                sidebar.selectionModel()->selectedRows() == QModelIndexList({index});
    };
    auto drag = [&](int from, int to, int steps, int pause) {
        QPoint position = centre(row(from));
        mouse(viewport, QEvent::MouseButtonPress, position, Qt::LeftButton);
        const QPoint end = centre(row(to));
        for (int step = 1; step <= steps; ++step) {
            position = centre(row(from)) + (end - centre(row(from))) * step / steps;
            mouse(viewport, QEvent::MouseMove, position, Qt::LeftButton);
            if (pause) {
                QTest::qWait(pause);
            }
        }
        mouse(viewport, QEvent::MouseButtonRelease, end, Qt::NoButton);
        QTest::qWait(350); // past the 300 ms pressed-until-clicked timer
    };
    // As after skin load: A is shown and highlighted, nothing opened yet.
    sidebar.selectIndex(row(0));
    require(highlighted(row(0)) && opened() == 0, "touch sidebar starts with the shown source highlighted");
    drag(1, 4, 12, 25);
    require(opened() == 0 && !LibraryFeature::shown,
            "touch slow drag from row 1 to row 4 opens no source");
    require(highlighted(row(0)) && !sidebar.rootIndex().isValid(),
            "touch slow drag keeps the highlight on the shown source");
    drag(4, 1, 1, 0);
    require(opened() == 0 && highlighted(row(0)), "touch fast flick opens nothing and keeps the highlight");
    mouse(viewport, QEvent::MouseButtonPress, centre(row(2)), Qt::LeftButton);
    QTest::qWait(400);
    require(opened() == 0 && highlighted(row(0)), "a held touch press opens nothing");
    mouse(viewport, QEvent::MouseButtonRelease, centre(row(3)), Qt::NoButton);
    QTest::qWait(350);
    require(opened() == 0, "a held press released on another row opens nothing");

    // Keyboard and controller (LibraryControl sends the same key events):
    // the pinned pressed() path still opens after the 300 ms delay.
    sidebar.setFocus();
    QTest::keyClick(&sidebar, Qt::Key_Down);
    require(opened() == 0, "keyboard Down defers opening to the pressed() timer");
    QTest::qWait(350);
    require(b.activations == 1 && opened() == 1 && LibraryFeature::shown == &b && highlighted(row(1)),
            "keyboard/controller Down opens the next source once through pressed()");

    // A tap: press and release on the same row.
    mouse(viewport, QEvent::MouseButtonPress, centre(row(3)), Qt::LeftButton);
    mouse(viewport, QEvent::MouseMove, centre(row(3)) + QPoint(3, 2), Qt::LeftButton);
    mouse(viewport, QEvent::MouseButtonRelease, centre(row(3)) + QPoint(3, 2), Qt::NoButton);
    QApplication::processEvents();
    require(d.activations == 1 && opened() == 2, "touch tap opens the source at once");
    QTest::qWait(350);
    const QModelIndex rootD = model.getFeatureRootIndex(&d);
    require(d.activations == 1 && opened() == 2, "touch tap opens the source exactly once");
    require(LibraryFeature::shown == &d && highlighted(rootD),
            "after a tap the selected row equals the shown source");
    require(sidebar.rootIndex() == rootD, "touch tap still enters the source folder");

    // Rows change under the finger (as on USB hot-plug): open nothing.
    const QModelIndex child = model.index(0, 0, rootD);
    const QPoint childPoint = centre(child);
    mouse(viewport, QEvent::MouseButtonPress, childPoint, Qt::LeftButton);
    sidebar.returnToSourceRoot();
    QApplication::processEvents();
    mouse(viewport, QEvent::MouseButtonRelease, childPoint, Qt::NoButton);
    QTest::qWait(350);
    require(opened() == 2 && LibraryFeature::shown == &d,
            "a press across a source-tree reset opens nothing");

    // Real touch input that Qt turns into mouse events.
    auto* device = QTest::createTouchDevice();
    const int before = opened();
    QTest::touchEvent(&sidebar, device).press(0, viewport->mapTo(&sidebar, centre(row(1))));
    for (int r = 2; r <= 4; ++r) {
        QTest::touchEvent(&sidebar, device).move(0, viewport->mapTo(&sidebar, centre(row(r))));
        QTest::qWait(20);
    }
    QTest::touchEvent(&sidebar, device).release(0, viewport->mapTo(&sidebar, centre(row(4))));
    QTest::qWait(350);
    require(opened() == before, "synthetic touch drag over three rows opens nothing");
    QTest::touchEvent(&sidebar, device).press(0, viewport->mapTo(&sidebar, centre(row(2))));
    QTest::touchEvent(&sidebar, device).release(0, viewport->mapTo(&sidebar, centre(row(2))));
    QTest::qWait(350);
    require(c.activations == 1 && opened() == before + 1 && LibraryFeature::shown == &c &&
                    highlighted(model.getFeatureRootIndex(&c)),
            "synthetic touch tap opens one source and highlights it");
}
#endif

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    QTemporaryDir directory;
    const QString path = directory.filePath("settings.ini");
    Settings settings(path);
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceOrder"),
            SourceOrder::encode({"C", "A", "B"}));
    SidebarModel model;
    Library library(&settings, &model);
    A featureA;
    B featureB;
    C featureC;
    D featureD;
    library.add(&featureB);
    library.add(&featureA);
    require(library.order() == QStringList({"A", "B"}), "saved identity order beats construction order with absent C");
    require(model.index(0, 0).data().toString() == "A", "actual SidebarModel restores requested first feature identity");
#ifdef SOURCE_ORDER_BASELINE
    return failures ? 1 : 0;
#else
    QPersistentModelIndex rootA(model.getFeatureRootIndex(&featureA));
    QPersistentModelIndex childA(model.index(0, 0, rootA));
    QPersistentModelIndex nestedA(model.index(0, 0, childA));
    model.setDefaultSelection(rootA.row());
    SidebarView view;
    view.setModel(&model);
    QObject::connect(&model, &SidebarModel::selectIndex, &view, &SidebarView::selectIndex);
    library.m_pSidebarWidget = &view;
    view.setRootIndex(childA);
    view.setCurrentIndex(nestedA);
    library.add(&featureC);
    require(library.order() == QStringList({"C", "A", "B"}), "late source inserted at persisted identity position");
    require(rootA.row() == 1 && rootA.data().toString() == "A", "persistent root follows coordinated move");
    require(childA.parent() == rootA && nestedA.parent() == childA, "persistent descendants retain ancestry");
    require(view.rootIndex() == childA && view.currentIndex() == nestedA, "folder and selection survive lazy source arrival");
    require(model.getDefaultSelection() == rootA, "default feature identity survives move");
    bool arraysAgree = true;
    int moves = 0;
    QObject::connect(&model, &QAbstractItemModel::rowsMoved, &view, [&] {
        ++moves;
        for (int row = 0; row < model.rowCount(); ++row) {
            arraysAgree &= model.index(row, 0).data().toString() == library.m_features.at(row)->identity;
        }
    });
    library.saveSidebarSourceOrder({"B", "C", "A"});
    require(moves > 0 && arraysAgree, "rowsMoved observers see both native feature arrays coordinated");
    require(rootA.row() == 2 && childA.parent() == rootA, "moving downward to final boundary preserves indexes");
    require(model.getDefaultSelection() == rootA, "default survives downward move");
    int rejectedCallbacks = 0;
    auto rejected = [&] { ++rejectedCallbacks; };
    require(!model.moveLibraryFeature(-1, 0, rejected) &&
            !model.moveLibraryFeature(0, model.rowCount(), rejected) &&
            !model.moveLibraryFeature(0, 0, rejected) &&
            !model.moveLibraryFeature(0, 1, {}) && rejectedCallbacks == 0,
            "invalid boundary self and missing coordination moves rejected");
    library.saveSidebarSourceOrder({"A", "B", "C"});
    require(rootA.row() == 0 && rootA.data().toString() == "A", "upward first boundary retains identity");
    model.pressed(rootA);
    library.saveSidebarSourceOrder({"C", "B", "A"});
    const int activations = featureA.activations;
    QTest::qWait(330);
    require(featureA.activations == activations + 1 && featureC.activations == 0,
            "delayed activation follows moved persistent feature not row number");
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceA"), false);
    library.applySidebarSourceVisibility();
    require(!view.rootIndex().isValid() && view.currentIndex().data().toString() == "C",
            "hidden active folder returns to visible native source");
    require(model.getDefaultSelection().data().toString() == "C", "hidden default falls back without losing preference");
    settings.setValue(ConfigKey(kConfigGroup, "SidebarDefaultSource"), "A");
    library.saveSidebarSourceOrder({"B", "A", "C"});
    require(view.isRowHidden(model.getFeatureRootIndex(&featureA).row(), {}) &&
            !view.isRowHidden(model.getFeatureRootIndex(&featureB).row(), {}),
            "hidden flags follow source identity after reorder");
    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == "A",
            "source order leaves owner default identity unchanged");
    require(SourceOrder::decode("[\"A\",\"A\",null,7,\"\",\"B\"]") == QStringList({"A", "B"}),
            "duplicate empty and nonstring saved identities ignored");
    require(SourceOrder::decode("not json").isEmpty() && SourceOrder::decode("{}").isEmpty(),
            "malformed serialization safely falls back");
    require(SourceOrder::present({"missing", "B", "A"}, {"A", "D", "B", "D"}) ==
            QStringList({"B", "A", "D"}), "absent and new source identities reconcile deterministically");
    require(SourceOrder::mergePresent({"absent", "A", "B"}, {"B", "B", "A"}) ==
            QStringList({"absent", "B", "A"}), "duplicate incoming order identities cannot duplicate native source slots");
    {
        Settings freshSettings(path);
        SidebarModel freshModel;
        Library fresh(&freshSettings, &freshModel);
        fresh.add(&featureC);
        fresh.add(&featureA);
        fresh.add(&featureB);
        fresh.add(&featureD);
        require(fresh.order() == QStringList({"B", "A", "C", "D"}),
                "fresh QSettings and SidebarModel reconstruct from reordered input plus new source");
    }
    LibraryInterface::VisibilityMenu chooser;
    QStringList published;
    auto* list = LibraryInterface::addSourceOrder(&chooser, {"A", "B", "C"},
            {"Alpha", "Beta", "Gamma"}, [&](const QStringList& order) {
                published = order;
                library.saveSidebarSourceOrder(order);
            });
    chooser.show();
    QApplication::processEvents();
    require(list->dragDropMode() == QAbstractItemView::InternalMove, "persistent Sources chooser exposes native internal drag");
    require(list->model()->moveRows({}, 0, 1, {}, 3), "Qt chooser accepts native drag-model move to final position");
    require(published == QStringList({"B", "C", "A"}) && library.order() == published,
            "chooser move dispatches actual Library and SidebarModel ordering");
    require(chooser.isVisible(), "Sources chooser remains open after drag-model move");
    list->setCurrentRow(2);
    const auto buttons = chooser.findChildren<QPushButton*>();
    buttons.first()->click();
    require(chooser.isVisible() && published == QStringList({"B", "A", "C"}),
            "Up provides touch and keyboard alternative without closing chooser");
    buttons.last()->click();
    require(chooser.isVisible() && published == QStringList({"B", "C", "A"}),
            "multiple owner changes remain visible until explicit Close");
    require(SourceOrder::decode(SourceOrder::encode({"a,quote\"", "日本語", "A"})) ==
            QStringList({"a,quote\"", "日本語", "A"}), "stable identity JSON escapes and Unicode round trip");
    library.m_sidebarSources.prepend({"ghost", "Unavailable optional source",
            ConfigKey(kConfigGroup, "SidebarSourceghost"), nullptr, {}});
    library.saveSidebarSourceOrder({"ghost", "A", "B", "C"});
    for (const auto& source : library.m_sidebarSources) {
        settings.setValue(source.preference, false);
    }
    library.applySidebarSourceVisibility();
    require(!view.isRowHidden(model.getFeatureRootIndex(&featureA).row(), {}) &&
            settings.getValue(ConfigKey(kConfigGroup, "SidebarSourceA"), false),
            "all-hidden recovery chooses instantiated source when first ordered optional source is absent");
    require(!library.m_sidebarSources.first().feature,
            "reordering and safety recovery do not eagerly construct optional sources");
    auto* close = chooser.addAction("Close", &chooser, &QMenu::close);
    close->trigger();
    require(!chooser.isVisible(), "explicit Close still ends persistent chooser");
    if (argc > 1 && QString::fromUtf8(argv[1]) == "holdout") {
        require(SourceOrder::mergePresent({"absent1", "C", "absent2", "A", "B"}, {"B", "C", "A"}) ==
                QStringList({"absent1", "B", "absent2", "C", "A"}), "HOLDOUT absent identities keep slots across present reorder");
        library.add(&featureD);
        QPersistentModelIndex childD(model.index(0, 0, model.getFeatureRootIndex(&featureD)));
        featureD.children.removeRows(0, 1);
        require(!childD.isValid() && rootA.isValid(), "HOLDOUT real lazy child removal invalidates only removed indexes");
        featureD.children.insertTreeItemRows({}, 0);
        require(model.getFeatureRootIndex(&featureD).isValid(), "HOLDOUT empty lazy insertion preserves feature identity");
        std::vector<std::unique_ptr<TreeItem>> lateRows;
        auto late = TreeItem::newRoot(&featureD);
        late->setLabel("lazy replacement");
        lateRows.push_back(std::move(late));
        featureD.children.insertTreeItemRows(std::move(lateRows), 0);
        QPersistentModelIndex lateIndex(model.index(0, 0, model.getFeatureRootIndex(&featureD)));
        require(lateIndex.data().toString() == "lazy replacement", "HOLDOUT actual lazy child insertion translates after source movement");
        library.saveSidebarSourceOrder({"D", "C", "B", "A"});
        require(rootA.row() == 3 && nestedA.parent().parent() == rootA,
                "HOLDOUT multi-move churn preserves nested persistent ancestry");
        require(lateIndex.parent().row() == 0 && lateIndex.data().toString() == "lazy replacement",
                "HOLDOUT newly inserted child persistent index survives parent reordering");
    }
    for (const auto& source : library.m_sidebarSources) {
        settings.setValue(source.preference, source.id == "A");
    }
    library.applySidebarSourceVisibility();
    library.m_pLibraryWidget = &view;
    library.showSidebarSourcesMenu();
    auto* nativeMenu = library.m_pSidebarSourcesMenu.data();
    QApplication::processEvents();
    library.showSidebarSourcesMenu();
    require(library.m_pSidebarSourcesMenu == nativeMenu && nativeMenu->isVisible(),
            "actual Library Sources menu is a visible singleton");
    auto* nativeList = nativeMenu->findChild<QListWidget*>("MixpiSourceOrder");
    require(nativeList && nativeList->model()->moveRows({}, 0, 1, {}, nativeList->count()),
            "actual Library chooser native order list accepts move");
    auto checkboxes = nativeMenu->findChildren<QCheckBox*>();
    for (auto* checkbox : checkboxes) {
        if (checkbox->text() == "B") {
            if (!checkbox->isChecked()) { checkbox->click(); }
            checkbox->click();
            require(settings.getValue(ConfigKey(kConfigGroup, "SidebarSourceB"), true) == checkbox->isChecked(),
                    "actual visibility callback uses stable identity after source reorder");
        }
    }
    require(nativeMenu->isVisible(), "actual native chooser visibility change remains open after ordering");
    bool lastProtected = false;
    for (auto* checkbox : checkboxes) {
        if (checkbox->text() == "A") {
            lastProtected = checkbox->isChecked() && !checkbox->isEnabled();
            checkbox->click();
            require(checkbox->isChecked(), "actual last visible checkbox cannot hide source after reordering");
        }
    }
    require(lastProtected, "actual reordered chooser retains dynamic last-visible protection");
    auto menus = nativeMenu->findChildren<QMenu*>();
    require(menus.size() == 1, "actual native chooser retains default-source submenu");
    QMetaObject::invokeMethod(menus.first(), "aboutToShow");
    bool hiddenDisabled = false;
    bool defaultRetained = false;
    for (auto* action : menus.first()->actions()) {
        if (action->text() == "B") {
            hiddenDisabled = !action->isEnabled();
        }
        if (action->text() == "A") {
            defaultRetained = action->isChecked() && action->isEnabled();
        }
    }
    require(hiddenDisabled, "actual default chooser disallows hidden source after native reorder");
    require(defaultRetained, "actual default chooser retains stable checked identity across moves");
    nativeMenu->actions().last()->trigger();
    require(!nativeMenu->isVisible(), "actual native Sources Close ends chooser");
    QApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
    require(!library.m_pSidebarSourcesMenu, "native Sources singleton pointer clears after deferred deletion");
    E featureE;
    int constructions = 0;
    library.m_sidebarSources.append({"E", "E", ConfigKey(kConfigGroup, "SidebarSourceE"), nullptr,
            [&] { ++constructions; return &featureE; }});
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceE"), false);
    library.showSidebarSourcesMenu();
    auto* lazyMenu = library.m_pSidebarSourcesMenu.data();
    auto* lazyList = lazyMenu->findChild<QListWidget*>("MixpiSourceOrder");
    require(constructions == 0, "opening persistent source order chooser preserves lazy factories");
    lazyList->model()->moveRows({}, lazyList->count() - 1, 1, {}, 0);
    require(constructions == 0, "reordering hidden optional source does not instantiate it");
    for (auto* checkbox : lazyMenu->findChildren<QCheckBox*>()) {
        if (checkbox->text() == "E") { checkbox->click(); }
    }
    require(constructions == 1 && library.order().first() == "E" &&
            model.index(0, 0).data().toString() == "E", "actual checkbox lazy factory inserts feature into persisted native position");
    lazyMenu->actions().last()->trigger();
    QApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
    settings.setValue(ConfigKey(kConfigGroup, "SidebarDefaultSource"), "E");
    const int previousE = featureE.activations;
    library.onSkinLoadFinished();
    require(view.currentIndex().data().toString() == "E" && featureE.activations == previousE + 1,
            "actual skin-load handler activates stable owner default after reordered lazy input");
    settings.setValue(ConfigKey(kConfigGroup, "SidebarDefaultSource"), "unavailable");
    library.onSkinLoadFinished();
    require(view.currentIndex() == model.getDefaultSelection() &&
            settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == "unavailable",
            "actual skin-load missing default falls back without deleting owner identity");
    settings.setValue(ConfigKey(kConfigGroup, "SidebarDefaultSource"), "A");
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceA"), false);
    library.onSkinLoadFinished();
    require(view.currentIndex().data().toString() == "E" &&
            settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == "A",
            "actual skin-load hidden default uses visible fallback and retains preference");
    touchSidebarChecks();
    return failures ? 1 : 0;
#endif
}
