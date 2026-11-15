#include <QApplication>
#include <QAbstractItemModelTester>
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

struct ConfigKey {
    QString key;
    ConfigKey(QString group, QString name) : key(group + "/" + name) {}
};
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
    return failures ? 1 : 0;
#endif
}
