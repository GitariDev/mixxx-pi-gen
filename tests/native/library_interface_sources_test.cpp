#include <QApplication>
#include <QAbstractItemModelTester>
#include <QDir>
#include <QFileInfo>
#include <QFile>
#include <QFontInfo>
#include <QImage>
#include <QLabel>
#include <QScrollArea>
#include <QMouseEvent>
#include <QPersistentModelIndex>
#include <QHeaderView>
#include <QPointer>
#include <QScrollBar>
#include <QSettings>
#include <QTemporaryDir>
#include <QTest>
#include <algorithm>
#include <iostream>
#include <memory>
#include <utility>

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
#include <QStandardItemModel>
#include <QTableView>

#include "library/tabledelegates/bpmdelegate.h"
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
    // mixxx-source-groups.patch: the owner's hidden sources (no tiles here,
    // so they are the view's hidden rows), and no grouped Sources screen.
    void setSourceRowHidden(int row, bool hidden) { setRowHidden(row, QModelIndex(), hidden); }
    bool isSourceRowHidden(int row) const { return isRowHidden(row, QModelIndex()); }
    bool hasSourceScreen() const { return false; }
    // The Sources screen hooks the Library calls; the real WLibrarySidebar
    // is checked in sourceScreenChecks().
    int sourceChanges = 0;
    QPointer<QWidget> panel;
    bool editing = false;
    void sourcesChanged() { ++sourceChanges; }
    void noteSourceShown() {}
    void setSourcesEditPanel(QWidget* pPanel) {
        panel = pPanel;
        pPanel->setParent(this);
        pPanel->setGeometry(rect());
        pPanel->setVisible(editing);
    }
    bool isSourcesEditing() const { return editing; }
    void setSourcesEditing(bool on) {
        editing = on && panel;
        if (panel) {
            panel->setGeometry(rect());
            panel->setVisible(editing);
        }
    }
    // DONE (false) and the close ✕ (true, Sources closes too).
    int closes = 0;
    void endSourcesEditing(bool close) {
        setSourcesEditing(false);
        closes += close ? 1 : 0;
    }
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
#ifdef MIXPI_SOURCES_SCREEN
    QPointer<QWidget> m_pSidebarSourceEdit;
#else
    QPointer<QMenu> m_pSidebarSourcesMenu;
#endif
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
#ifdef MIXPI_SOURCES_SCREEN
    void refreshSidebarSourceEdit();
#endif
#ifdef MIXPI_SOURCE_GROUPS
    bool groupedSources() const;
    QStringList sourceGroupOrder() const;
    bool sourceGroupVisible(const QString& tile) const;
    void moveSourceGroup(const QString& tile, int direction);
    // The grouped edit list reads these; this fixture has no grouped Sources
    // (tests/native/source_groups_test.cpp checks them).
    QModelIndex sourceRow(const QString&) const { return {}; }
    QList<QModelIndex> driveRows() { return {}; }
#endif
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
#ifdef MIXPI_SOURCES_SCREEN
void Library::refreshSidebarSourceEdit() {}
#endif
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

    // F-6 (council round 1): a press that moves the drag distance from where
    // it started is a drag and opens nothing, even when it is released on the
    // row it started on.
    const int distance = QApplication::startDragDistance();
    std::cout << "OBSERVE drag distance " << distance << " px" << std::endl;
    auto path = [&](const QList<QPoint>& points, int pause) {
        mouse(viewport, QEvent::MouseButtonPress, points.first(), Qt::LeftButton);
        for (int index = 1; index < points.size(); ++index) {
            mouse(viewport, QEvent::MouseMove, points[index], Qt::LeftButton);
            if (pause) {
                QTest::qWait(pause);
            }
        }
        mouse(viewport, QEvent::MouseButtonRelease, points.last(), Qt::NoButton);
        QTest::qWait(350);
    };
    const int shownBefore = opened();
    const QPoint start = centre(row(3));
    const QPoint across = start + QPoint(100, 0);
    require(sidebar.indexAt(across) == row(3), "the horizontal drag fixture stays on one row");
    path({start, start + QPoint(25, 0), start + QPoint(50, 0), start + QPoint(75, 0), across}, 15);
    require(opened() == shownBefore && highlighted(row(1)),
            "touch horizontal drag that ends on the pressed row opens nothing");
    const QPoint second = centre(row(2));
    path({second, second + QPoint(0, 10), centre(row(3)), centre(row(4)), centre(row(3)),
                 second + QPoint(0, 10), second}, 25);
    require(opened() == shownBefore && highlighted(row(1)),
            "touch out-and-back drag released on the pressed row opens nothing");
    path({start, start + QPoint(distance, 0), start}, 15);
    require(opened() == shownBefore && highlighted(row(1)),
            "a move of exactly the drag distance and back opens nothing");
    drag(4, 2, 10, 30);
    require(opened() == shownBefore && highlighted(row(1)),
            "touch slow vertical drag across rows opens nothing");

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

    // F-6 (council round 1), back at the source list: a real touch drag
    // along one row opens nothing; a tap with jitter under the drag distance
    // opens its source once and selects it.
    sidebar.returnToSourceRoot();
    QApplication::processEvents();
    const int afterTaps = opened();
    const QPoint along = centre(row(4));
    QTest::touchEvent(&sidebar, device).press(0, viewport->mapTo(&sidebar, along));
    for (int step = 1; step <= 4; ++step) {
        QTest::touchEvent(&sidebar, device).move(0, viewport->mapTo(&sidebar, along + QPoint(25 * step, 0)));
        QTest::qWait(15);
    }
    QTest::touchEvent(&sidebar, device).release(0, viewport->mapTo(&sidebar, along + QPoint(100, 0)));
    QTest::qWait(350);
    require(opened() == afterTaps, "synthetic touch horizontal drag along one row opens nothing");
    const QPoint jitter = centre(row(4));
    path({jitter, jitter + QPoint(distance - 1, 0), jitter + QPoint(0, 2), jitter + QPoint(2, 1)}, 10);
    require(e.activations == 1 && opened() == afterTaps + 1, "a tap with jitter under the drag distance opens its source once");
    require(LibraryFeature::shown == &e && highlighted(model.getFeatureRootIndex(&e)),
            "after a jittery tap the selected row equals the shown source");
}
// F-6 (acceptance finding 6): the touch Sources list has no horizontal scroll
// bar, so it does not take a row; long names elide. The vertical scroll bar
// stays. The desktop (non-touch) sidebar keeps the pinned behaviour.
void sidebarWidthChecks() {
    const QString longName = QStringLiteral("REKORDBOX (MANTACORE) with a source name far too long for the pane");
    std::vector<std::unique_ptr<LibraryFeature>> features;
    SidebarModel model;
    features.push_back(std::make_unique<LibraryFeature>(longName));
    for (int index = 0; index < 11; ++index) {
        features.push_back(std::make_unique<LibraryFeature>(QStringLiteral("SOURCE %1").arg(index)));
    }
    for (auto& feature : features) {
        model.addLibraryFeature(feature.get());
    }
    auto build = [&](WLibrarySidebar& sidebar, bool touch) {
        sidebar.setModel(&model);
        if (touch) {
            sidebar.enableTouchNavigation();
        }
        sidebar.resize(288, 160);
        sidebar.show();
        QApplication::processEvents();
    };
    WLibrarySidebar desktop;
    build(desktop, false);
    std::cout << "OBSERVE desktop Sources column " << desktop.header()->sectionSize(0)
              << " px in a " << desktop.viewport()->width() << " px viewport, horizontal max "
              << desktop.horizontalScrollBar()->maximum() << std::endl;
    require(desktop.horizontalScrollBarPolicy() == Qt::ScrollBarAsNeeded &&
                    desktop.horizontalScrollBar()->maximum() > 0,
            "desktop Sources list keeps the pinned horizontal scrolling for a long name");
    WLibrarySidebar sidebar;
    build(sidebar, true);
    const QModelIndex longIndex = model.getFeatureRootIndex(features.front().get());
    std::cout << "OBSERVE touch Sources column " << sidebar.header()->sectionSize(0)
              << " px in a " << sidebar.viewport()->width() << " px viewport, horizontal bar "
              << (sidebar.horizontalScrollBar()->isVisible() ? "shown" : "hidden")
              << ", long row right edge " << sidebar.visualRect(longIndex).right() << std::endl;
    require(sidebar.horizontalScrollBarPolicy() == Qt::ScrollBarAlwaysOff &&
                    !sidebar.horizontalScrollBar()->isVisible(),
            "touch Sources list has no horizontal scroll bar");
    require(sidebar.header()->sectionSize(0) <= sidebar.viewport()->width() &&
                    sidebar.visualRect(longIndex).right() < sidebar.viewport()->width(),
            "touch Sources column fits the list width, so a long name elides");
    require(sidebar.verticalScrollBarPolicy() != Qt::ScrollBarAlwaysOff &&
                    sidebar.verticalScrollBar()->isVisible() &&
                    sidebar.verticalScrollBar()->maximum() > 0,
            "touch Sources list keeps its vertical scroll bar");
    const int before = sidebar.verticalScrollBar()->value();
    sidebar.verticalScrollBar()->setValue(sidebar.verticalScrollBar()->maximum());
    require(sidebar.verticalScrollBar()->value() > before, "the vertical scroll bar still scrolls the list");
}

// F-7 follow-up: the real BPMDelegate (CheckboxDelegate) on a BPM cell whose
// check state is bpm_lock, as in BaseTrackTableModel.
struct BpmProbe : BPMDelegate {
    using BPMDelegate::BPMDelegate;
    bool drawsLock(const QModelIndex& index) const {
        QStyleOptionViewItem option;
        initStyleOption(&option, index);
        return option.features.testFlag(QStyleOptionViewItem::HasCheckIndicator);
    }
};

void bpmLockChecks() {
    QStandardItemModel tracks(3, 2);
    for (int row = 0; row < 3; ++row) {
        tracks.setItem(row, 0, new QStandardItem(QString("Track %1").arg(row)));
        auto* bpm = new QStandardItem("128.0");
        bpm->setFlags(Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsUserCheckable);
        bpm->setCheckState(Qt::Unchecked);
        tracks.setItem(row, 1, bpm);
    }
    int lockChanges = 0;
    QObject::connect(&tracks, &QStandardItemModel::dataChanged, &tracks,
            [&](const QModelIndex&, const QModelIndex&, const QList<int>& roles) {
                lockChanges += roles.isEmpty() || roles.contains(Qt::CheckStateRole) ? 1 : 0;
            });
    QTableView table;
    table.setModel(&tracks);
    auto* delegate = new BpmProbe(&table);
    table.setItemDelegateForColumn(1, delegate);
    table.resize(400, 200);
    table.show();
    QApplication::processEvents();
    auto* viewport = table.viewport();
    const QModelIndex cell = tracks.index(1, 1);
    // Where the pinned code hit-tests the lock: the table's own style.
    QStyleOptionViewItem option;
    option.initFrom(&table);
    option.rect = table.visualRect(cell);
    option.features = QStyleOptionViewItem::HasCheckIndicator | QStyleOptionViewItem::HasDisplay;
    option.text = "128.0";
    const QPoint lockPoint = table.style()->subElementRect(
            QStyle::SE_ItemViewItemCheckIndicator, &option, &table).center();
    auto tap = [&](QPoint point) {
        mouse(viewport, QEvent::MouseButtonPress, point, Qt::LeftButton);
        mouse(viewport, QEvent::MouseButtonRelease, point, Qt::NoButton);
        QApplication::processEvents();
    };
    auto locked = [&] { return tracks.item(1, 1)->checkState() == Qt::Checked; };

    // Desktop skins (no touch navigation): pinned behaviour, a click on the
    // lock toggles bpm_lock. This also proves the fixture hits the lock.
    require(!QCoreApplication::instance()->property("mixpiTouchNavigation").toBool(),
            "BPM desktop: no touch skin flag before a touch sidebar exists");
    require(delegate->drawsLock(cell), "BPM desktop: the lock check box is drawn");
    tap(lockPoint);
    require(locked() && lockChanges == 1, "BPM desktop: a click on the lock still toggles bpm_lock");
    tracks.item(1, 1)->setCheckState(Qt::Unchecked);
    lockChanges = 0;

    {
        // The touch skin: the real sidebar with TouchNavigation enabled.
        SidebarModel model;
        WLibrarySidebar sidebar;
        sidebar.setModel(&model);
        sidebar.enableTouchNavigation();
        require(!delegate->drawsLock(cell), "BPM touch: no lock check box is drawn");
        tap(lockPoint);
        tap(lockPoint);
        tap(lockPoint);
        tap(table.visualRect(cell).center());
        mouse(viewport, QEvent::MouseButtonDblClick, lockPoint, Qt::LeftButton);
        mouse(viewport, QEvent::MouseButtonRelease, lockPoint, Qt::NoButton);
        table.setCurrentIndex(cell);
        table.setFocus();
        QTest::keyClick(&table, Qt::Key_Space);
        QApplication::processEvents();
        require(!locked() && lockChanges == 0,
                "BPM touch: taps at the old lock position, the cell centre, a double tap and Space leave bpm_lock unchanged");
        // The track menu's Lock BPM changes the track; the model then reports
        // the new bpm_lock. That path does not go through the delegate.
        tracks.setData(cell, Qt::Checked, Qt::CheckStateRole);
        require(locked() && lockChanges == 1, "BPM touch: a lock change from outside the cell (track menu) still applies");
        tap(lockPoint);
        require(locked() && lockChanges == 1, "BPM touch: a tap does not unlock a locked track either");
        tracks.setData(cell, Qt::Unchecked, Qt::CheckStateRole);
    }
    QApplication::processEvents();
    require(!QCoreApplication::instance()->property("mixpiTouchNavigation").toBool() &&
                    delegate->drawsLock(cell),
            "BPM: after the touch sidebar is gone (skin change) desktop behaviour returns");
}

#ifdef MIXPI_SOURCES_SCREEN
#include "control/controlobject.h"

// Agreed UI s5 (build C, U-4): the Sources side menu and the full-screen
// edit list. The real style sheets are the style of the widgets checked
// here: the menu block (pioneered-menus.qss) and the Sources rules
// (mixpi-sources-menu.qss), which load after it.
QString menusStyle() {
    QString style;
    for (const char* path : {MIXPI_MENUS_QSS, MIXPI_SOURCES_QSS}) {
        QFile file(QString::fromUtf8(path));
        if (file.open(QIODevice::ReadOnly)) {
            style += QString::fromUtf8(file.readAll()) + QStringLiteral("\n");
        }
    }
    return style;
}

double meanLuminance(const QImage& image) {
    double total = 0;
    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            const QColor colour = image.pixelColor(x, y);
            total += 0.299 * colour.red() + 0.587 * colour.green() + 0.114 * colour.blue();
        }
    }
    return image.isNull() ? 255 : total / (image.width() * image.height());
}

QWidget* editRow(LibraryInterface::SourceEditList* list, const QString& id) {
    return list ? list->row(id) : nullptr;
}

template<typename T>
T* part(LibraryInterface::SourceEditList* list, const QString& id, const char* name) {
    auto* row = editRow(list, id);
    return row ? row->findChild<T*>(name) : nullptr;
}

// A finger drag on a widget that may move under it (a scrolling list).
void dragOn(QWidget* widget, int dy, int steps) {
    const QPoint start = widget->mapToGlobal(widget->rect().center());
    auto send = [widget](QEvent::Type type, QPoint global, Qt::MouseButtons buttons) {
        QMouseEvent event(type, QPointF(widget->mapFromGlobal(global)), QPointF(global),
                type == QEvent::MouseMove ? Qt::NoButton : Qt::LeftButton, buttons, Qt::NoModifier);
        QApplication::sendEvent(widget, &event);
    };
    send(QEvent::MouseButtonPress, start, Qt::LeftButton);
    for (int step = 1; step <= steps; ++step) {
        send(QEvent::MouseMove, start + QPoint(0, dy * step / steps), Qt::LeftButton);
    }
    send(QEvent::MouseButtonRelease, start + QPoint(0, dy), Qt::NoButton);
    QApplication::processEvents();
}

void tap(QAbstractButton* button) {
    QTest::mouseClick(button, Qt::LeftButton, {}, button->rect().center());
    QApplication::processEvents();
}

// R-10 and agreed UI s5: Sources edit through the actual Library methods.
void editListChecks(Library& library, Settings& settings, SidebarView& view, SidebarModel& model,
        E& featureE, int& constructions) {
    library.m_sidebarSources.append({"E", "E", ConfigKey(kConfigGroup, "SidebarSourceE"), nullptr,
            [&] { ++constructions; return &featureE; }});
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceE"), false);
    view.setStyleSheet(menusStyle());
    view.resize(800, 432);
    view.show();
    auto rowOf = [&](const QString& title) {
        for (int row = 0; row < model.rowCount(); ++row) {
            if (model.index(row, 0).data().toString() == title) {
                return row;
            }
        }
        return -1;
    };
    library.showSidebarSourcesMenu();
    QApplication::processEvents();
    auto* list = dynamic_cast<LibraryInterface::SourceEditList*>(library.m_pSidebarSourceEdit.data());
    require(list && view.isSourcesEditing() && list->isVisible() && list->geometry() == view.rect(),
            "EDIT shows the Sources edit list");
    if (!list) {
        return;
    }
    require(view.findChildren<QWidget*>("MixpiSourcesEdit").size() == 1 &&
                    view.findChildren<QMenu*>().isEmpty() && !QApplication::activePopupWidget() &&
                    !list->findChild<QListWidget*>(),
            "Sources edit is one list: no menu, no second order list");
    require(constructions == 0, "opening Sources edit keeps optional sources unloaded");
    require(list->rows().size() == library.m_sidebarSources.size(),
            "Sources edit has one row per source, hidden ones too");
    auto* title = list->findChild<QLabel*>("MixpiSourcesEditTitle");
    auto* hint = list->findChild<QLabel*>("MixpiSourcesEditHint");
    auto* done = list->doneButton();
    auto* close = list->closeButton();
    const QRect doneBox(done->mapTo(list, QPoint()), done->size());
    const QRect closeBox(close->mapTo(list, QPoint()), close->size());
    std::cout << "OBSERVE edit header DONE " << doneBox.x() << ',' << doneBox.y() << ' ' << doneBox.width()
              << 'x' << doneBox.height() << ", close " << closeBox.x() << ',' << closeBox.y() << ' '
              << closeBox.width() << 'x' << closeBox.height() << std::endl;
    require(title && title->text() == "EDIT SOURCES" && hint &&
                    hint->text() == QString::fromUtf8(
                                            "Switch sources on or off, set the order, ★ where Tracks starts.") &&
                    done->text() == "DONE" && done->size() == QSize(96, 48) && close->size() == QSize(48, 48) &&
                    closeBox.right() == list->width() - 5 && doneBox.right() + 9 == closeBox.left(),
            "the header has EDIT SOURCES, the hint, DONE and the close ✕ at the right");
    bool sized = true;
    for (auto* row : list->rows()) {
        sized &= row->height() == 52;
        for (const char* name : {"MixpiSourcesEditUp", "MixpiSourcesEditDown"}) {
            auto* button = row->findChild<QPushButton*>(name);
            sized &= button && button->size() == QSize(84, 48);
        }
        auto* star = row->findChild<QPushButton*>("MixpiSourcesEditStar");
        sized &= star && star->size() == QSize(48, 48);
        auto* toggle = row->findChild<QCheckBox*>("MixpiSourcesEditSwitch");
        sized &= toggle && toggle->size() == QSize(88, 48);
        for (auto* label : row->findChildren<QLabel*>()) {
            sized &= QFontInfo(label->font()).pixelSize() >= 13;
        }
    }
    require(sized, "edit rows are 52 px; ★ 48x48, the toggle 88x48, ▲ UP and ▼ DOWN 84x48; text 13 px or more");
    auto* firstUp = list->rows().first()->findChild<QPushButton*>("MixpiSourcesEditUp");
    auto* lastDown = list->rows().last()->findChild<QPushButton*>("MixpiSourcesEditDown");
    require(firstUp->text() == QString::fromUtf8("▲ UP") && lastDown->text() == QString::fromUtf8("▼ DOWN") &&
                    !firstUp->isEnabled() && !lastDown->isEnabled(),
            "UP is off on the first row and DOWN on the last");
    const QString grabs = qEnvironmentVariable("MIXPI_SOURCES_GRAB_DIR");
    if (!grabs.isEmpty()) {
        list->grab().save(grabs + "/sources-edit-list.png");
    }
    const double luminance = meanLuminance(list->grab().toImage());
    std::cout << "OBSERVE Sources edit mean luminance " << luminance << std::endl;
    require(luminance < 64, "a grab of Sources edit is dark");

    // Each switch writes the same key as the old check box.
    auto* switchB = part<QCheckBox>(list, "B", "MixpiSourcesEditSwitch");
    require(switchB && !switchB->isChecked() && editRow(list, "B")->property("off").toBool(),
            "a hidden source's switch is off and its row is dimmed");
    auto* dimName = part<QLabel>(list, "B", "MixpiSourcesEditName");
    auto* litName = part<QLabel>(list, "A", "MixpiSourcesEditName");
    std::cout << "OBSERVE off name " << dimName->palette().color(QPalette::WindowText).name().toStdString()
              << ", on name " << litName->palette().color(QPalette::WindowText).name().toStdString() << std::endl;
    require(dimName->palette().color(QPalette::WindowText) == QColor("#73767c") &&
                    litName->palette().color(QPalette::WindowText) == QColor("#e4e7ec"),
            "the row that is off is dimmed (its text at 45%)");
    tap(switchB);
    require(settings.getValue(ConfigKey(kConfigGroup, "SidebarSourceB"), false) &&
                    !view.isRowHidden(rowOf("B"), {}),
            "a switch writes the same SidebarSource key as before and shows the source");
    QApplication::processEvents();
    require(!editRow(list, "B")->property("off").toBool() &&
                    part<QCheckBox>(list, "B", "MixpiSourcesEditSwitch")->property("on").toBool(),
            "a row switched on is not dimmed and its toggle reads ON");
    tap(part<QCheckBox>(list, "B", "MixpiSourcesEditSwitch"));
    require(!settings.getValue(ConfigKey(kConfigGroup, "SidebarSourceB"), true) &&
                    view.isRowHidden(rowOf("B"), {}),
            "switching a source off hides it with the same key");
    auto* switchA = part<QCheckBox>(list, "A", "MixpiSourcesEditSwitch");
    require(switchA && switchA->isChecked() && !switchA->isEnabled(),
            "the last visible source's switch is disabled");
    tap(switchA);
    require(settings.getValue(ConfigKey(kConfigGroup, "SidebarSourceA"), false) &&
                    !view.isRowHidden(rowOf("A"), {}),
            "a tap on the last visible switch changes nothing");

    // ▲ UP and ▼ DOWN change the saved order.
    QStringList ids;
    for (const auto& source : library.m_sidebarSources) {
        ids.append(source.id);
    }
    const QString second = ids.at(1);
    tap(part<QPushButton>(list, second, "MixpiSourcesEditUp"));
    QStringList moved = ids;
    moved.move(1, 0);
    QStringList now;
    for (const auto& source : library.m_sidebarSources) {
        now.append(source.id);
    }
    require(now == moved && SourceOrder::decode(settings.getValueString(
                                    ConfigKey(kConfigGroup, "SidebarSourceOrder"))).mid(0, moved.size()) == moved,
            "Up moves a source and saves the order");
    require(!part<QPushButton>(list, second, "MixpiSourcesEditUp")->isEnabled(),
            "the moved row is first now and has no UP");
    tap(part<QPushButton>(list, second, "MixpiSourcesEditDown"));
    now.clear();
    for (const auto& source : library.m_sidebarSources) {
        now.append(source.id);
    }
    require(now == ids, "Down moves it back and saves the order");

    // ★: Tracks starts at that source.
    tap(part<QCheckBox>(list, "B", "MixpiSourcesEditSwitch"));
    tap(part<QPushButton>(list, "B", "MixpiSourcesEditStar"));
    auto* starB = part<QPushButton>(list, "B", "MixpiSourcesEditStar");
    auto* subB = part<QLabel>(list, "B", "MixpiSourcesEditSub");
    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == "B" && starB &&
                    starB->text() == QString::fromUtf8("★") && starB->property("start").toBool() &&
                    subB && subB->text() == "TRACKS STARTS HERE" &&
                    part<QPushButton>(list, "A", "MixpiSourcesEditStar")->text() == QString::fromUtf8("☆"),
            "★ on a row writes the start source; that row is lit and reads TRACKS STARTS HERE");
    require(!part<QPushButton>(list, "ghost", "MixpiSourcesEditStar")->isEnabled(),
            "★ is off for a source that is off or not loaded");

    // An optional source: moving it does not load it; switching it on does.
    while (library.m_sidebarSources.first().id != "E") {
        auto* up = part<QPushButton>(list, "E", "MixpiSourcesEditUp");
        if (!up || !up->isEnabled()) {
            break;
        }
        tap(up);
    }
    require(constructions == 0 && library.m_sidebarSources.first().id == "E",
            "moving an optional source to the top does not load it");
    tap(part<QCheckBox>(list, "E", "MixpiSourcesEditSwitch"));
    require(constructions == 1 && library.order().first() == "E" && model.index(0, 0).data().toString() == "E",
            "switching an optional source on loads it once, at its saved place");

    // A drag on the list scrolls it and presses nothing (the C-1 rule).
    view.resize(800, 240);
    view.setSourcesEditing(true);
    QApplication::processEvents();
    auto* down = part<QPushButton>(list, "A", "MixpiSourcesEditDown");
    QStringList beforeDrag;
    for (const auto& source : library.m_sidebarSources) {
        beforeDrag.append(source.id);
    }
    const int scrolled = list->area()->verticalScrollBar()->value();
    dragOn(down, -60, 6);
    QStringList afterDrag;
    for (const auto& source : library.m_sidebarSources) {
        afterDrag.append(source.id);
    }
    std::cout << "OBSERVE Sources edit scrolled " << scrolled << " -> "
              << list->area()->verticalScrollBar()->value() << std::endl;
    require(afterDrag == beforeDrag && list->area()->verticalScrollBar()->value() > scrolled,
            "a drag on Sources edit scrolls it and presses nothing");
    require(list->area()->verticalScrollBar()->isVisible() && list->area()->verticalScrollBar()->width() == 24,
            "a long edit list shows its 24 px scroll bar");

    // DONE and the close ✕.
    tap(list->doneButton());
    require(!view.isSourcesEditing() && !list->isVisible() && view.closes == 0,
            "DONE ends Sources edit and shows the menu again");
    library.showSidebarSourcesMenu();
    QApplication::processEvents();
    tap(list->closeButton());
    require(!view.isSourcesEditing() && !list->isVisible() && view.closes == 1,
            "the close ✕ ends Sources edit and closes Sources");
    library.showSidebarSourcesMenu();
    library.showSidebarSourcesMenu();
    QApplication::processEvents();
    require(!view.isSourcesEditing() && !list->isVisible(),
            "the skin's EDIT LIST / DONE control still opens and ends Sources edit");
    view.hide();
    view.setStyleSheet(QString());
}

// Agreed UI s5: the real WLibrarySidebar as the Sources side menu, 320x380 at
// the right of an 800x480 screen, under #LibraryWrapper as in the skin.
void sourceScreenChecks() {
    const QStringList names{"Tracks", "Playlists", "Crates", "Computer", "Recordings", "History",
            "Analyse", "Rekordbox", "Serato"};
    std::vector<std::unique_ptr<LibraryFeature>> features;
    SidebarModel model;
    for (const auto& name : names) {
        features.push_back(std::make_unique<LibraryFeature>(name));
    }
    // Twelve more playlists, so the list inside Playlists scrolls; Mixxx
    // labels a playlist "name (count) duration".
    for (int number = 1; number <= 12; ++number) {
        features[1]->children.getRootItem()->appendChild(
                QStringLiteral("Friday %1 (%2) 1:0%1:00").arg(number).arg(number * 4));
    }
    // Recordings has no lists: it cannot be entered.
    features[4]->children.setRootItem(TreeItem::newRoot(features[4].get()));
    // A drive whose playlists still load shows nothing when it is opened.
    features[7]->showsList = false;
    for (auto& feature : features) {
        model.addLibraryFeature(feature.get());
    }
    LibraryFeature::shown = nullptr;
    LibraryFeature::listShown = false;
    QWidget screen800;
    screen800.setObjectName("MixpiScreen");
    screen800.resize(800, 480);
    screen800.setStyleSheet(menusStyle());
    QWidget wrapper(&screen800);
    wrapper.setObjectName("LibraryWrapper");
    wrapper.setGeometry(0, 0, 800, 480);
    WLibrarySidebar sidebar(&wrapper);
    sidebar.setModel(&model);
    {
        WLibrarySidebar* pSidebarWidget = &sidebar;
        SidebarModel* m_pSidebarModel = &model;
        auto connect = [](auto&&... arguments) { return QObject::connect(arguments...); };
#include "sidebar_activation_wiring.inc"
    }
    QObject::connect(&model, &SidebarModel::selectIndex, &sidebar, &WLibrarySidebar::selectIndex);
    // What Library::slotShowTrackModel and slotSwitchToView tell the sidebar.
    QObject::connect(&sidebar, &WLibrarySidebar::clicked, &sidebar, [&sidebar] {
        if (std::exchange(LibraryFeature::listShown, false)) {
            sidebar.noteSourceShown();
        }
    });
    sidebar.sourceSubline = [](const QModelIndex& index) {
        return QStringLiteral("Sub ") + index.data().toString();
    };
    int editRequests = 0;
    sidebar.sourcesEditRequested = [&editRequests] { ++editRequests; };
    auto rowOf = [&](const QString& title) {
        for (int row = 0; row < model.rowCount(); ++row) {
            if (model.index(row, 0).data().toString() == title) {
                return row;
            }
        }
        return -1;
    };
    // As Library: hidden sources stay hidden after a model reset.
    QObject::connect(&model, &QAbstractItemModel::modelReset, &sidebar, [&] {
        sidebar.setRowHidden(rowOf("Analyse"), {}, true);
        sidebar.sourcesChanged();
    });
    sidebar.enableTouchNavigation();
    sidebar.setGeometry(480, 100, 320, 380);
    screen800.show();
    sidebar.setRowHidden(rowOf("Analyse"), {}, true);
    sidebar.sourcesChanged();
    QTest::qWait(20);
    auto* screen = ControlObject::getControl(ConfigKey("[MixPi]", "screen"));
    auto* sidebarVisible = ControlObject::getControl(ConfigKey("[Sidebar]", "sidebar_visible"));
    auto* sampleLoad = ControlObject::getControl(ConfigKey("[MixPi]", "sample_load"));
    auto* editing = ControlObject::getControl(ConfigKey("[Library]", "sidebar_sources_editing"));
    auto* viewport = sidebar.viewport();
    auto* top = sidebar.findChild<QScrollArea*>("MixpiSourcesMenuTop");
    auto* header = sidebar.findChild<QWidget*>("MixpiSourcesMenuHeader");
    auto* back = sidebar.findChild<QPushButton*>("MixpiSourcesMenuBack");
    auto* edit = sidebar.findChild<QPushButton*>("MixpiSourcesMenuEdit");
    auto* place = sidebar.findChild<QLabel*>("MixpiSourcesMenuPlace");
    require(sidebar.hasSourceScreen() && sidebar.property("mixpiSourceMenu").toBool() && top && header &&
                    back && edit && place,
            "a 320 px touch sidebar is the Sources side menu");
    if (!top || !header || !back || !edit || !place) {
        return;
    }
    const QRect backBox(back->mapTo(&sidebar, QPoint()), back->size());
    const QRect editBox(edit->mapTo(&sidebar, QPoint()), edit->size());
    std::cout << "OBSERVE header " << header->geometry().x() << ',' << header->geometry().y() << ' '
              << header->width() << 'x' << header->height() << ", BACK " << backBox.x() << ',' << backBox.y()
              << ", EDIT " << editBox.x() << ',' << editBox.y() << std::endl;
    require(header->geometry() == QRect(1, 0, 319, 52) && back->size() == QSize(88, 48) &&
                    edit->size() == QSize(88, 48) && backBox.topLeft() == QPoint(9, 2) &&
                    editBox.left() == backBox.right() + 9 && back->text() == "BACK" && edit->text() == "EDIT" &&
                    back->isVisible() && edit->isVisible() && !place->isVisible() && back->isEnabled(),
            "at the top level the 52 px header has BACK and EDIT, 88x48 each");
    require(!back->icon().isNull() && !edit->icon().isNull() &&
                    LibraryInterface::SourceGlyphs::svg("back").contains("M15 5l-7 7 7 7") &&
                    LibraryInterface::SourceGlyphs::svg("edit").contains("M3 6h10M3 11h8M3 16h5"),
            "BACK and EDIT carry their icons: a chevron, and a pencil on a list");
    require(top->isVisible() && top->geometry() == QRect(1, 52, 319, 328),
            "the top level fills the panel under the header");
    QStringList tileNames;
    bool tilesSized = true;
    for (auto* tile : sidebar.sourceTiles()) {
        tileNames.append(tile->accessibleName());
        tilesSized &= tile->height() == 52 && tile->width() >= 290;
    }
    QStringList visible = names;
    visible.removeAll("Analyse");
    require(tileNames == visible, "the top level lists the visible sources in saved order and skips hidden ones");
    require(tilesSized, "top-level rows are 52 px and as wide as the panel");
    auto* firstTile = sidebar.sourceTiles().value(0);
    require(firstTile && firstTile->findChild<QLabel*>("MixpiSourcesMenuName")->text() == "Tracks" &&
                    firstTile->findChild<QLabel*>("MixpiSourcesMenuSub")->text() == "Sub Tracks" &&
                    firstTile->findChild<QWidget*>("MixpiSourcesMenuIcon"),
            "a row has the icon, the title and its small line");
    auto chevron = [&](const QString& name) {
        auto* tile = sidebar.sourceTiles().value(visible.indexOf(name));
        auto* mark = tile ? tile->findChild<QWidget*>("MixpiSourcesMenuChevron") : nullptr;
        return mark && !mark->isHidden();
    };
    require(chevron("Playlists") && !chevron("Recordings"), "› only on rows that can be entered");
    auto* icon = firstTile->findChild<QWidget*>("MixpiSourcesMenuIcon");
    require(icon->palette().color(QPalette::WindowText) == QColor("#d6784a"),
            "source icons are in the source colour (deck 2 orange)");

    // A tap on a source: inside it, BACK and the place.
    auto* playlists = features[1].get();
    const int screenWrites = screen->writes;
    int before = playlists->activations;
    tap(sidebar.sourceTiles().at(1));
    const QModelIndex rootP = model.getFeatureRootIndex(playlists);
    require(playlists->activations == before + 1 && sidebar.rootIndex() == rootP && model.rowCount(rootP) == 13,
            "a tap on a source shows that source's lists");
    require(sidebar.isSourceMenuInside() && !top->isVisible() && place->isVisible() && !edit->isVisible() &&
                    place->text() == "Playlists" && back->isVisible() && back->isEnabled(),
            "inside a source the header has BACK and the place name");
    require(sidebar.sourceTiles().at(1)->isChecked() && !sidebar.sourceTiles().at(0)->isChecked(),
            "the current source is marked at the top level");
    require(screen->writes == screenWrites, "a source with lists keeps Sources open");
    require(viewport->geometry().topLeft() == QPoint(1, 52) &&
                    sidebar.visualRect(model.index(0, 0, rootP)).height() == 52,
            "inside rows are 52 px under the header");
    const auto counted = LibraryInterface::sourceLabelCount(QStringLiteral("Afro house (48) 3:12:00"));
    require(counted.first == "Afro house" && counted.second == "48" &&
                    LibraryInterface::sourceLabelCount("Warm-up (31)").second == "31" &&
                    LibraryInterface::sourceLabelCount("Tracks").second.isEmpty(),
            "a row's count sits at the right, apart from its name");
    auto* scroll = sidebar.verticalScrollBar();
    const QRect barBox(scroll->mapTo(&sidebar, QPoint()), scroll->size());
    std::cout << "OBSERVE list scroll bar " << barBox.x() << ',' << barBox.y() << ' ' << barBox.width() << 'x'
              << barBox.height() << " max " << scroll->maximum() << std::endl;
    require(scroll->isVisible() && scroll->maximum() > 0 && barBox.width() == 24 && barBox.right() == 319 &&
                    barBox.top() >= 52,
            "a list longer than the panel shows a 24 px scroll bar at the menu's right edge");
    const QModelIndex currentRow = model.index(3, 0, rootP);
    sidebar.selectionModel()->setCurrentIndex(currentRow, QItemSelectionModel::ClearAndSelect);
    const QImage rows = viewport->grab().toImage();
    const QRect currentBox = sidebar.visualRect(currentRow);
    const QColor edgeColour = rows.pixelColor(1, currentBox.center().y());
    const QColor currentFill = rows.pixelColor(40, currentBox.center().y());
    const QColor otherFill = rows.pixelColor(40, sidebar.visualRect(model.index(4, 0, rootP)).center().y());
    std::cout << "OBSERVE current row edge " << edgeColour.name().toStdString() << " fill "
              << currentFill.name().toStdString() << ", other " << otherFill.name().toStdString() << std::endl;
    require(edgeColour == QColor("#a3c45e") && currentFill == QColor("#1d222a") && otherFill == QColor("#161a20"),
            "the current row has the accent edge and the surface-2 background");
    auto tapRow = [&](const QModelIndex& index) {
        const QPoint centre = sidebar.visualRect(index).center();
        mouse(viewport, QEvent::MouseButtonPress, centre, Qt::LeftButton);
        mouse(viewport, QEvent::MouseButtonRelease, centre, Qt::NoButton);
        QApplication::processEvents();
    };
    const QModelIndex folder = model.index(0, 0, rootP);
    tapRow(folder);
    require(sidebar.rootIndex() == folder && sidebar.sourceCrumb() == "Playlists › folder" &&
                    place->toolTip() == "Playlists › folder",
            "a tap on a row with children drills in; the place shows the path");
    screen->set(1);
    sidebarVisible->set(1);
    const int writesScreen = screen->writes;
    const int writesVisible = sidebarVisible->writes;
    before = playlists->activations;
    tapRow(model.index(0, 0, folder));
    QTest::qWait(350);
    require(playlists->activations == before + 1 && screen->get() == 0 && sidebarVisible->get() == 0 &&
                    screen->writes == writesScreen + 1 && sidebarVisible->writes == writesVisible + 1,
            "a tap on a list without children opens it once and closes Sources (each control written once)");
    tap(back);
    require(sidebar.rootIndex() == rootP && sidebar.isSourceMenuInside() && place->text() == "Playlists",
            "BACK goes up one level");

    // A drag over three rows scrolls the list and opens nothing.
    before = playlists->activations;
    const int topValue = scroll->value();
    const QPoint start = sidebar.visualRect(model.index(4, 0, rootP)).center();
    mouse(viewport, QEvent::MouseButtonPress, start, Qt::LeftButton);
    for (int step = 1; step <= 12; ++step) {
        mouse(viewport, QEvent::MouseMove, start - QPoint(0, 14 * step), Qt::LeftButton);
        QTest::qWait(10);
    }
    mouse(viewport, QEvent::MouseButtonRelease, start - QPoint(0, 168), Qt::NoButton);
    QTest::qWait(350);
    std::cout << "OBSERVE list scrolled " << topValue << " -> " << scroll->value() << std::endl;
    require(playlists->activations == before && scroll->value() > topValue && sidebar.rootIndex() == rootP,
            "a drag over three rows scrolls the list and opens nothing");
    scroll->setValue(0);
    tap(back);
    require(!sidebar.isSourceMenuInside() && top->isVisible() && edit->isVisible() && !place->isVisible(),
            "BACK at a source's own level returns to the top level");

    // A drive that is still loading shows nothing yet: Sources stays open.
    auto* rekordbox = features[7].get();
    tap(sidebar.sourceTiles().at(visible.indexOf("Rekordbox")));
    const QModelIndex rootR = model.getFeatureRootIndex(rekordbox);
    tapRow(model.index(0, 0, rootR));
    screen->set(1);
    const int writesBefore = screen->writes;
    before = rekordbox->activations;
    tapRow(model.index(0, 0, model.index(0, 0, rootR)));
    require(rekordbox->activations == before + 1 && screen->get() == 1 && screen->writes == writesBefore,
            "a row that shows nothing yet (a drive still loading) keeps Sources open");
    tap(back);
    tap(back);
    require(!sidebar.isSourceMenuInside(), "BACK twice from a drive's list is the top level");

    // Load sample's SOURCES… (agreed UI s7): a pick returns to Load sample.
    // The menu closes ([MixPi],screen 0) and never writes sample_load, so the
    // skin shows Load sample again.
    sampleLoad->set(1);
    const int sampleWrites = sampleLoad->writes;
    screen->set(1);
    sidebarVisible->set(1);
    tap(sidebar.sourceTiles().at(visible.indexOf("Recordings")));
    require(screen->get() == 0 && sidebarVisible->get() == 0 && sampleLoad->get() == 1 &&
                    sampleLoad->writes == sampleWrites && !sidebar.isSourceMenuInside(),
            "a pick from Load sample's SOURCES… closes Sources and leaves sample_load: Load sample shows again");
    sampleLoad->set(0);

    // BACK at the top level closes Sources.
    screen->set(1);
    sidebarVisible->set(1);
    tap(back);
    require(screen->get() == 0 && sidebarVisible->get() == 0, "BACK at the top level closes Sources");

    // EDIT asks for the edit list.
    tap(edit);
    require(editRequests == 1, "EDIT opens the edit list (the Library's showSidebarSourcesMenu)");

    // A drag on the top level scrolls it and opens no source.
    auto* topBar = top->verticalScrollBar();
    std::cout << "OBSERVE top level scroll range " << topBar->maximum() << std::endl;
    int opened = 0;
    for (auto& feature : features) {
        opened += feature->activations;
    }
    dragOn(sidebar.sourceTiles().at(2), -40, 4);
    int openedAfter = 0;
    for (auto& feature : features) {
        openedAfter += feature->activations;
    }
    require(openedAfter == opened && topBar->value() == std::min(40, topBar->maximum()) && topBar->maximum() > 0,
            "a drag on the top level scrolls it and opens no source");
    require(topBar->isVisible() && topBar->width() == 24,
            "a top level longer than the panel shows its 24 px scroll bar");
    topBar->setValue(0);

    // The top level follows visibility and order.
    sidebar.setRowHidden(rowOf("Analyse"), {}, false);
    sidebar.sourcesChanged();
    QTest::qWait(20);
    require(sidebar.sourceTiles().size() == names.size(), "a source switched on gets its row");
    sidebar.setRowHidden(rowOf("Analyse"), {}, true);
    sidebar.sourcesChanged();
    model.moveLibraryFeature(rowOf("Serato"), 0, [] {});
    QTest::qWait(20);
    require(sidebar.sourceTiles().size() == visible.size() &&
                    sidebar.sourceTiles().first()->accessibleName() == "Serato",
            "the top level follows a new saved order");

    // A model reset while inside (USB hot-plug): back to the top, no crash.
    tap(sidebar.sourceTiles().at(1 + visible.indexOf("Playlists")));
    const QModelIndex rootAgain = model.getFeatureRootIndex(playlists);
    tapRow(model.index(0, 0, rootAgain));
    require(sidebar.rootIndex().isValid() && sidebar.rootIndex().parent() == rootAgain,
            "the reset fixture is inside a Playlists folder");
    auto replacement = TreeItem::newRoot(playlists);
    replacement->appendChild("after the reset");
    playlists->children.setRootItem(std::move(replacement));
    QTest::qWait(20);
    bool tilesValid = true;
    for (auto* tile : sidebar.sourceTiles()) {
        tilesValid &= rowOf(tile->accessibleName()) >= 0;
    }
    require(!sidebar.rootIndex().isValid() && !sidebar.isSourceMenuInside() && top->isVisible() &&
                    sidebar.sourceTiles().size() == visible.size() && tilesValid,
            "a model reset while inside returns to the top level and rebuilds the rows");
    tap(sidebar.sourceTiles().at(1 + visible.indexOf("Playlists")));
    require(sidebar.rootIndex() == model.getFeatureRootIndex(playlists) &&
                    model.index(0, 0, sidebar.rootIndex()).data().toString() == "after the reset",
            "after the reset a tap opens the new lists");

    // Sources edit is full screen under the top bar.
    auto* panel = new QWidget;
    sidebar.setSourcesEditPanel(panel);
    sidebar.setSourcesEditing(true);
    QApplication::processEvents();
    require(sidebar.isSourcesEditing() && panel->isVisible() && panel->parentWidget() == &screen800 &&
                    panel->geometry() == QRect(0, 48, 800, 432) && editing->get() == 1,
            "Sources edit is full screen under the top bar and the editing control is 1");
    screen->set(1);
    sidebarVisible->set(1);
    sidebar.endSourcesEditing(false);
    QApplication::processEvents();
    require(!panel->isVisible() && editing->get() == 0 && screen->get() == 1 && sidebarVisible->get() == 1,
            "DONE shows the Sources menu again");
    sidebar.setSourcesEditing(true);
    sidebar.endSourcesEditing(true);
    QApplication::processEvents();
    require(!panel->isVisible() && editing->get() == 0 && screen->get() == 0 && sidebarVisible->get() == 0,
            "the close ✕ ends Sources edit and closes Sources");
    screen800.resize(800, 444);
    QApplication::processEvents();
    require(panel->geometry() == QRect(0, 48, 800, 396), "the edit list follows the screen size");
    sidebar.setSourcesEditing(true);
    sidebar.hide();
    require(!sidebar.isSourcesEditing() && editing->get() == 0 && !panel->isVisible(),
            "closing Sources ends Sources edit");
    sidebar.show();

    // A narrow touch sidebar (the Pioneered touch skin's 260 px pane) keeps
    // the one-list layout.
    sidebar.setGeometry(540, 100, 260, 380);
    QApplication::processEvents();
    require(!sidebar.hasSourceScreen() && !top->isVisible() && !header->isVisible() &&
                    viewport->geometry().top() < 52,
            "a narrow touch sidebar keeps the one-list layout");
    sidebar.setGeometry(480, 100, 320, 380);
    QApplication::processEvents();
    require(sidebar.hasSourceScreen() && header->isVisible() && viewport->geometry().topLeft() == QPoint(1, 52),
            "widening it again shows the Sources menu");
}
#endif
#endif

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    const QStringList arguments = application.arguments();
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
    if (arguments.contains("holdout")) {
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
    E featureE;
    int constructions = 0;
#ifdef MIXPI_SOURCES_SCREEN
    // R-10: one edit list replaces the Sources menu.
    editListChecks(library, settings, view, model, featureE, constructions);
#else
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
#endif
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
    bpmLockChecks();
    touchSidebarChecks();
    sidebarWidthChecks();
#ifdef MIXPI_SOURCES_SCREEN
    if (arguments.contains("sources-screen")) {
        sourceScreenChecks();
    }
#endif
    return failures ? 1 : 0;
#endif
}
