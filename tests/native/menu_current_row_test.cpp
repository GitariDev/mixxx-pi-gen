// Council round 9 (Opus), wave J17: the Sources menu's current-row edge stays
// on the list the table shows (AGREED-UI-SPEC 2a "the Sources menu's
// current-row edge follows the source in view", 2e, m-sources-sub.png).
//
// The setup is menu_place_fix_test.cpp's (wave J16): the real WLibrarySidebar
// as the 320x380 menu at the right of an 800x480 screen, the real
// SidebarModel wired by the exact connects from Library::bindSidebarWidget,
// the actual Library methods from the patched library.cpp and the actual
// rekordbox playlist tree builder with the drive's Tracks row. A drive opens
// as Library::openRemovableSourceAsync opens it.
//
// The fault (acceptance P, o9-1..o9-5): with A - MAIN PLAYLIST in view, a tap
// on the empty part of the open menu (a focus-in) cleared the current row,
// and the next ☰ put the edge on TRACKS (J16's restore).
// Built by tests/native/menu_current_row_runner.py (--baseline: without
// mixxx-menu-current-row.patch).
#include <QApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFocusEvent>
#include <QLabel>
#include <QLineEdit>
#include <QPointer>
#include <QPushButton>
#include <QScrollArea>
#include <QSettings>
#include <QTemporaryDir>
#include <QTest>
#include <QTimer>
#include <iostream>
#include <memory>

#include "control/controlobject.h"
#include "library/libraryfeature.h"
#include "library/mixpistartdrive.h"
#include "library/sidebarmodel.h"
#include "library/sourceorder.h"
#include "library/treeitem.h"
#include "preferences/configobject.h"
#include "widget/libraryinterface.h"
#include "widget/wlibrarysidebar.h"

#define QUICK_LINK_NODE "::mixxx_quick_lnk_node::"
#define DEVICE_NODE "::mixxx_device_node::"

int failures = 0;
void require(bool condition, const char* name) {
    std::cout << (condition ? "PASS " : "FAIL ") << name << std::endl;
    failures += !condition;
}

LibraryFeature::LibraryFeature(QString name)
        : identity(std::move(name)) {
    children.setRootItem(TreeItem::newRoot(this));
}

struct Settings {
    QSettings settings;
    explicit Settings(const QString& path)
            : settings(path, QSettings::IniFormat) {
    }
    QString getValueString(const ConfigKey& key) {
        return settings.value(key.key).toString();
    }
    bool getValue(const ConfigKey& key, bool fallback) {
        return settings.value(key.key, fallback).toBool();
    }
    void setValue(const ConfigKey& key, const QVariant& value) {
        settings.setValue(key.key, value);
    }
    void remove(const ConfigKey& key) {
        settings.remove(key.key);
    }
};
const QString kConfigGroup = "Library";

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
    WLibrarySidebar* m_pSidebarWidget = nullptr;
    QWidget* m_pLibraryWidget = nullptr;
    QObject* m_pSidebarKeyboard = nullptr;
    QPointer<QWidget> m_pSidebarSourceEdit;
    QFont m_trackTableFont;
    int m_iTrackTableRowHeight = 24;
    bool m_editMetadataSelectedClick = false;
    QList<SidebarSource> m_sidebarSources;
    QList<LibraryFeature*> m_features;
    QString m_samplesPath;
    QStringList m_driveOrder;

    Library(Settings* settings, SidebarModel* model)
            : m_pConfig(settings), m_pSidebarModel(model) {
    }
    void add(const QString& id, LibraryFeature* feature) {
        m_sidebarSources.append({id, feature->identity,
                ConfigKey(kConfigGroup, "SidebarSource" + id), feature, {}});
        m_features.append(feature);
        m_pSidebarModel->addLibraryFeature(feature);
    }
    void addFeature(LibraryFeature* feature) {
        add(feature->identity, feature);
    }
    void setTrackTableFont(const QFont&) {}
    void setTrackTableRowHeight(int) {}
    void setSelectedClick(bool) {}

    void applySidebarSourceOrder();
    void saveSidebarSourceOrder(const QStringList& identities);
    void applySidebarSourceVisibility();
    void showSidebarSourcesMenu();
    void refreshSidebarSourceEdit();
    QModelIndex sourceRow(const QString& id) const;
    QList<QModelIndex> driveRows();
    LibraryInterface::BrowsePlace sampleSourcePlace(int source);
    bool groupedSources() const;
    QList<LibraryInterface::SourceTile> sourceGroupTiles();
    QStringList sourceGroupOrder() const;
    bool sourceGroupVisible(const QString& tile) const;
    void mapSourceGroups();
    void moveSourceGroup(const QString& tile, int direction);
    bool showStartTile(const QString& start);
    struct StartDrive {
        int requests = 0;
        void openStartDrive() {
            ++requests;
        }
    };
    StartDrive* m_pMixpiMedia = nullptr;
    void onSkinLoadFinished();
};

#include "library_sample_methods.h"
#include "rekordbox_playlist_tree.inc"

// A rekordbox drive as RekordboxFeature makes it: the device row, its
// playlist tree from the actual buildPlaylistTree, and the actual
// driveTracksRow first. The lists: Afro house 48, Warm-up 31, and the folder
// Playlists with Deep cuts 17.
std::unique_ptr<TreeItem> rekordboxDrive(const QString& path, const QString& revision) {
    QSqlDatabase database = QSqlDatabase::database(QStringLiteral("rekordbox"));
    if (!database.isValid()) {
        database = QSqlDatabase::addDatabase(QStringLiteral("QSQLITE"), QStringLiteral("rekordbox"));
        database.setDatabaseName(QStringLiteral(":memory:"));
        database.open();
        createPlaylistsTable(database, kRekordboxPlaylistsTable);
        createPlaylistTracksTable(database, kRekordboxPlaylistTracksTable);
        QSqlQuery(database).exec(QStringLiteral(
                "CREATE TABLE rekordbox_library (id INTEGER PRIMARY KEY, rb_id INTEGER, device TEXT)"));
    }
    QSqlQuery(database).exec(QStringLiteral("DELETE FROM rekordbox_playlists"));
    QSqlQuery(database).exec(QStringLiteral("DELETE FROM rekordbox_playlist_tracks"));
    QSqlQuery(database).exec(QStringLiteral("DELETE FROM rekordbox_library"));
    QSqlQuery library(database);
    library.prepare(QStringLiteral("INSERT INTO rekordbox_library (rb_id, device) VALUES (:rb_id, :device)"));
    for (int track = 1; track <= 60; ++track) {
        library.bindValue(QStringLiteral(":rb_id"), track);
        library.bindValue(QStringLiteral(":device"), path);
        library.exec();
    }
    QMap<uint32_t, QString> names;
    QMap<uint32_t, bool> folders;
    QMap<uint32_t, QMap<uint32_t, uint32_t>> tree;
    QMap<uint32_t, QMap<uint32_t, uint32_t>> entries;
    const struct {
        uint32_t id;
        uint32_t parent;
        const char* name;
        bool folder;
        uint32_t tracks;
    } lists[] = {{1, 0, "Playlists", true, 0}, {2, 0, "Afro house", false, 48}, {3, 0, "Warm-up", false, 31},
            {4, 1, "Deep cuts", false, 17}};
    for (const auto& list : lists) {
        names[list.id] = QString::fromLatin1(list.name);
        folders[list.id] = list.folder;
        tree[list.parent][static_cast<uint32_t>(tree[list.parent].size())] = list.id;
        for (uint32_t entry = 1; entry <= list.tracks; ++entry) {
            entries[list.id][entry] = entry;
        }
    }
    auto drive = std::make_unique<TreeItem>(path.section('/', -1), QVariantList{path, QString(), revision});
    buildPlaylistTree(database, drive.get(), 0, names, folders, tree, entries, path, path,
            std::make_shared<mixxx::rekordbox::ImportOperation>());
    // RekordboxFeature::addDriveTracksRows adds it first once the import is done.
    drive->insertChild(0, driveTracksRow(*drive));
    return drive;
}

void settle() {
    for (int round = 0; round < 4; ++round) {
        QApplication::processEvents();
    }
}

QPushButton* tileNamed(WLibrarySidebar& sidebar, const QString& name) {
    for (auto* tile : sidebar.sourceTiles()) {
        if (tile->accessibleName() == name) {
            return tile;
        }
    }
    return nullptr;
}

QStringList shownRows(WLibrarySidebar& sidebar) {
    QStringList rows;
    auto* model = sidebar.model();
    for (int row = 0; row < model->rowCount(sidebar.rootIndex()); ++row) {
        if (!sidebar.isRowHidden(row, sidebar.rootIndex())) {
            rows.append(model->index(row, 0, sidebar.rootIndex()).data().toString());
        }
    }
    return rows;
}

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    QTemporaryDir home;
    Settings settings(QDir(home.path()).filePath("mixxx.cfg"));
    const QString samples = QDir(home.path()).filePath("Music/Samples");
    const QString gander = QDir(home.path()).filePath("media/GANDER1");
    const QString ixian = QDir(home.path()).filePath("media/IXIAN");
    const QString stick = QDir(home.path()).filePath("media/STICK");
    for (const auto& path : {samples, gander, ixian, stick}) {
        QDir().mkpath(path);
    }
    QDir().mkpath(stick + "/Sets");

    SidebarModel model;
    Library library(&settings, &model);
    library.m_samplesPath = samples;
    LibraryFeature tracks("Tracks");
    LibraryFeature playlists("Playlists");
    LibraryFeature autodj("Auto DJ");
    LibraryFeature computer("Computer");
    LibraryFeature recordings("Recordings");
    LibraryFeature history("History");
    LibraryFeature rekordbox("Rekordbox");
    playlists.children.getRootItem()->appendChild("Warm up", 1);
    history.children.getRootItem()->appendChild("2026-11-15", 3);
    {
        auto* root = computer.children.getRootItem();
        root->appendChild("Quick Links", QUICK_LINK_NODE);
        root->appendChild("Removable Devices", DEVICE_NODE);
        root->appendChild("/", "/");
        root->appendChild("Samples", QString(samples + "/"));
    }
    library.add("MixxxLibraryFeature", &tracks);
    library.add("AutoDJFeature", &autodj);
    library.add("PlaylistFeature", &playlists);
    library.add("BrowseFeature", &computer);
    library.add("RecordingFeature", &recordings);
    library.add("SetlogFeature", &history);
    library.add("RekordboxFeature", &rekordbox);

    QWidget screen;
    screen.setObjectName("MixpiFixtureScreen");
    screen.resize(800, 480);
    QWidget wrapper(&screen);
    wrapper.setObjectName("LibraryWrapper");
    wrapper.setGeometry(0, 0, 800, 480);
    QObject::connect(&model, &QAbstractItemModel::modelReset, &library,
            [&library] { library.applySidebarSourceVisibility(); });
    ControlObject screenControl(ConfigKey("[MixPi]", "screen"));
    ControlObject sidebarVisible(ConfigKey("[Sidebar]", "sidebar_visible"));
    ControlObject editing(ConfigKey("[Library]", "sidebar_sources_editing"));
    editing.setReadOnly();
    QString shown;
    int activations = 0;
    std::unique_ptr<WLibrarySidebar> menu;
    LibraryFeature::shown = [&](const QString& list) {
        shown = list;
        ++activations;
        if (menu) {
            menu->noteSourceShown();
        }
    };
    screen.show();
    settle();

    // A sidebar as the skin makes it at a Mixxx start: under #LibraryWrapper,
    // hidden, with no width until ☰ shows it (the layout gives it 320 px).
    // Each check that needs "☰ never shown" starts a new one.
    auto newMenu = [&] {
        menu.reset();
        settle();
        menu = std::make_unique<WLibrarySidebar>(&wrapper);
        WLibrarySidebar& sidebar = *menu;
        sidebar.hide();
        sidebar.setModel(&model);
        {
            WLibrarySidebar* pSidebarWidget = &sidebar;
            SidebarModel* m_pSidebarModel = &model;
            auto connect = [](auto&&... arguments) { return QObject::connect(arguments...); };
#include "sidebar_activation_wiring.inc"
        }
        QObject::connect(&model, &SidebarModel::selectIndex, &sidebar, &WLibrarySidebar::selectIndex);
        library.m_pSidebarWidget = &sidebar;
        {
            Library* self = &library;
            WLibrarySidebar* pSidebarWidget = &sidebar;
#include "grouped_binding.inc"
        }
        sidebar.sourcesEditRequested = [&library] {
            library.showSidebarSourcesMenu();
        };
        sidebar.enableTouchNavigation();
        sidebar.setGeometry(480, 100, 0, 380);
        library.applySidebarSourceVisibility();
        settle();
    };
    auto back = [&] {
        return menu->findChild<QPushButton*>("MixpiSourcesMenuBack");
    };
    auto edit = [&] {
        return menu->findChild<QPushButton*>("MixpiSourcesMenuEdit");
    };
    auto place = [&] {
        return menu->findChild<QLabel*>("MixpiSourcesMenuPlace");
    };
    // ☰: the skin shows the sidebar, then its layout gives it the menu's
    // width (the order the card has the first time).
    auto openMenu = [&] {
        screenControl.setAndConfirm(1);
        sidebarVisible.setAndConfirm(1);
        menu->show();
        settle();
        menu->setGeometry(480, 100, 320, 380);
        settle();
    };
    auto closeMenu = [&] {
        menu->hide();
        screenControl.setAndConfirm(0);
        sidebarVisible.setAndConfirm(0);
        settle();
    };
    const QModelIndex rekordboxRow = library.sourceRow("RekordboxFeature");
    auto driveRowOf = [&](const QString& name) {
        for (int row = 0; row < rekordbox.children.rowCount(); ++row) {
            if (rekordbox.children.index(row, 0).data().toString() == name) {
                return row;
            }
        }
        return -1;
    };
    auto sidebarDrive = [&](const QString& name) {
        return model.index(driveRowOf(name), 0, rekordboxRow);
    };
    auto plug = [&](const QString& path, const char* revision) {
        std::vector<std::unique_ptr<TreeItem>> rows;
        rows.push_back(rekordboxDrive(path, QString::fromLatin1(revision)));
        rekordbox.children.insertTreeItemRows(std::move(rows), rekordbox.children.rowCount());
        settle();
    };
    auto pull = [&](const QString& name) {
        // An eject from the Media page and a pull both end in discovery
        // removing the drive's row (onRekordboxDevicesFound).
        const int row = driveRowOf(name);
        if (row >= 0) {
            rekordbox.children.removeRows(row, 1);
        }
        settle();
    };
    // OPEN, BROWSE or the ping's LOAD (start: the ★ start).
    auto openDrive = [&](const QString& name, bool start) {
        const QModelIndex featureDrive = rekordbox.children.index(driveRowOf(name), 0);
        rekordbox.activateChild(featureDrive);
        emit rekordbox.featureSelect(&rekordbox, featureDrive);
        library.applySidebarSourceVisibility();
        settle();
        if (start) {
            menu->followShownSource();
        } else {
            menu->openShownSource();
        }
        settle();
        emit rekordbox.featureSelect(&rekordbox, rekordbox.children.index(0, 0, featureDrive));
        settle();
    };
    auto edgeDrawnOn = [&](const QModelIndex& index) {
        const QImage image = menu->viewport()->grab().toImage();
        const QRect row = menu->visualRect(index);
        return row.isValid() && image.pixelColor(row.left() + 1, row.center().y()) == menu->menuAccentColor();
    };
    auto edges = [&] {
        int count = 0;
        for (auto* tile : menu->sourceTiles()) {
            count += tile->isChecked() ? 1 : 0;
        }
        return count;
    };
    // Inside "NAME › rekordbox" with the edge on Tracks only (m-sources-sub.png).
    auto insideOnTracks = [&](const QString& name) {
        const QModelIndex driveNode = sidebarDrive(name);
        const QModelIndex tracksRow = model.index(0, 0, driveNode);
        const QString crumb = name + QString::fromUtf8(" › rekordbox");
        const bool inside = menu->hasSourceScreen() && menu->isSourceMenuInside() &&
                menu->rootIndex() == driveNode && menu->sourceCrumb() == crumb && place() &&
                place()->isVisible() && place()->text() == crumb && !edit()->isVisible() &&
                shownRows(*menu).value(0) == "Tracks";
        const bool edge = menu->currentIndex() == tracksRow && edgeDrawnOn(tracksRow) &&
                !edgeDrawnOn(model.index(2, 0, driveNode));
        std::cout << "OBSERVE screen " << menu->hasSourceScreen() << " inside " << menu->isSourceMenuInside()
                  << " place '" << menu->sourceCrumb().toStdString() << "' current '"
                  << menu->currentIndex().data().toString().toStdString() << "'" << std::endl;
        return inside && edge;
    };
    auto topWithoutEdge = [&] {
        const bool top = !menu->isSourceMenuInside() && edit()->isVisible() && !place()->isVisible();
        std::cout << "OBSERVE top " << !menu->isSourceMenuInside() << " edges " << edges() << " current '"
                  << menu->currentIndex().data().toString().toStdString() << "'" << std::endl;
        return top && edges() == 0 && !menu->currentIndex().isValid();
    };

    plug(gander, "rev-g1");
    plug(ixian, "rev-i1");
    const QString savedStart = settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource"));
    const QModelIndex ganderNode = sidebarDrive("GANDER1");
    auto ganderRow = [&](int row) {
        return model.index(row, 0, sidebarDrive("GANDER1"));
    };
    // The drive's rows: Tracks, Playlists (a folder), Afro house, Warm-up.
    require(ganderRow(0).data().toString() == "Tracks" && ganderRow(1).data().toString() == "Playlists" &&
                    ganderRow(2).data().toString().startsWith("Afro house") && ganderNode.isValid(),
            "the drive's rows: Tracks, Playlists (folder), Afro house");
    // The search box: focus that is not the menu's (the menu is not focused
    // when ☰ opens it).
    QLineEdit search(&screen);
    search.setGeometry(0, 50, 400, 40);
    search.show();
    screen.activateWindow();
    const bool active = QTest::qWaitForWindowActive(&screen);
    std::cout << "OBSERVE window active " << active << std::endl;

    // Inside the drive with only this row edged, and drawn.
    auto insideOn = [&](const QModelIndex& index) {
        const QModelIndex node = sidebarDrive("GANDER1");
        const bool inside = menu->hasSourceScreen() && menu->isSourceMenuInside() && menu->rootIndex() == node &&
                menu->sourceCrumb() == QString::fromUtf8("GANDER1 › rekordbox");
        int drawn = 0;
        for (int row = 0; row < model.rowCount(node); ++row) {
            drawn += edgeDrawnOn(model.index(row, 0, node)) ? 1 : 0;
        }
        std::cout << "OBSERVE inside " << menu->isSourceMenuInside() << " place '"
                  << menu->sourceCrumb().toStdString() << "' current '"
                  << menu->currentIndex().data().toString().toStdString() << "' edges drawn " << drawn
                  << std::endl;
        return inside && index.isValid() && menu->currentIndex() == index && edgeDrawnOn(index) && drawn == 1;
    };
    auto tap = [&](const QModelIndex& index) {
        QTest::mouseClick(menu->viewport(), Qt::LeftButton, {}, menu->visualRect(index).center());
        settle();
    };
    // The empty part of the open menu: below the drive's four rows.
    auto emptyPoint = [&] {
        return QPoint(menu->viewport()->width() / 2, menu->viewport()->height() - 12);
    };
    // The focus elsewhere, so a press on the menu is its focus-in
    // (Qt::MouseFocusReason), as the first press after ☰ on the card.
    auto focusElsewhere = [&] {
        search.setFocus(Qt::OtherFocusReason);
        settle();
        return search.hasFocus() && !menu->hasFocus();
    };
    // A list picked in the open menu by a tap; a list without children
    // closes the menu.
    auto pick = [&](int row) {
        openMenu();
        tap(ganderRow(row));
        closeMenu();
    };
    auto resetModel = [&] {
        // A sidebar model reset (a feature's tree rebuilt): rebuildSourceRail
        // enters the drive again with nothing current.
        history.children.setRootItem(TreeItem::newRoot(&history));
        history.children.getRootItem()->appendChild("2026-11-15", 3);
        settle();
        return !menu->currentIndex().isValid();
    };

    // A menu shown once, then OPEN: inside, the edge on TRACKS (J5, J16).
    newMenu();
    openMenu();
    closeMenu();
    openDrive("GANDER1", false);
    openMenu();
    require(insideOnTracks("GANDER1"), "start: OPEN, inside GANDER1 › rekordbox, the edge on TRACKS");
    closeMenu();

    // (a) Afro house picked (on the card: A - MAIN PLAYLIST), then the
    // current row goes three ways; the next ☰ has the edge on Afro house.
    {
        pick(2);
        const bool picked = shown.startsWith("Rekordbox/") && menu->currentIndex() == ganderRow(2);
        openMenu();
        require(picked && insideOn(ganderRow(2)), "(a) Afro house picked: ☰ has the edge on it (o9-3)");
        closeMenu();
    }
    {
        const QString before = shown;
        const int count = activations;
        QFocusEvent focus(QEvent::FocusIn, Qt::MouseFocusReason);
        QApplication::sendEvent(menu.get(), &focus);
        settle();
        openMenu();
        require(insideOn(ganderRow(2)),
                "J17 (a) Afro house in view, a focus-in, then ☰: current = Afro house, not TRACKS");
        require(shown == before && activations == count, "J17 (a) focus-in: the table is not changed");
        closeMenu();
    }
    {
        const QString before = shown;
        const int count = activations;
        menu->selectionModel()->clearCurrentIndex();
        settle();
        const bool cleared = !menu->currentIndex().isValid();
        openMenu();
        require(cleared && insideOn(ganderRow(2)),
                "J17 (a) Afro house in view, clearCurrentIndex(), then ☰: current = Afro house, not TRACKS");
        require(shown == before && activations == count, "J17 (a) clearCurrentIndex: the table is not changed");
        closeMenu();
    }
    {
        const QString before = shown;
        const int count = activations;
        const bool cleared = resetModel();
        openMenu();
        require(cleared && insideOn(ganderRow(2)),
                "J17 (a) Afro house in view, a sidebar model reset, then ☰: current = Afro house, not TRACKS");
        require(shown == before && activations == count, "J17 (a) model reset: the table is not changed");
        closeMenu();
    }

    // (b) The open menu: a tap and a drag on its empty part, and a drag of
    // its rows, keep the edge (o9-4: no row had it).
    {
        openMenu();
        const QString before = shown;
        const int count = activations;
        const bool elsewhere = focusElsewhere();
        QTest::mousePress(menu->viewport(), Qt::LeftButton, {}, emptyPoint());
        settle();
        const bool focused = menu->hasFocus();
        const bool keptPressed = menu->currentIndex() == ganderRow(2);
        QTest::mouseRelease(menu->viewport(), Qt::LeftButton, {}, emptyPoint());
        settle();
        std::cout << "OBSERVE empty tap: focus elsewhere first " << elsewhere << ", menu focused " << focused
                  << ", current '" << menu->currentIndex().data().toString().toStdString() << "'" << std::endl;
        require(elsewhere && focused && keptPressed && insideOn(ganderRow(2)) && menu->isVisible(),
                "J17 (b) a tap on the empty part of the open menu (its focus-in): the edge stays on Afro house");
        require(shown == before && activations == count, "J17 (b) the empty tap: the table is not changed");
        closeMenu();
        openMenu();
        require(insideOn(ganderRow(2)), "J17 (b) then ✕ and ☰: the edge on Afro house, not TRACKS (o9-5)");
        if (const QString directory = qEnvironmentVariable("MIXPI_SOURCES_GRAB_DIR"); !directory.isEmpty()) {
            screen.grab().save(directory + "/j17-menu-after-empty-tap.png");
        }
        closeMenu();
    }
    {
        openMenu();
        const QString before = shown;
        const int count = activations;
        const bool elsewhere = focusElsewhere();
        const QPoint from = emptyPoint();
        QTest::mousePress(menu->viewport(), Qt::LeftButton, {}, from);
        settle();
        const bool focused = menu->hasFocus();
        QTest::mouseMove(menu->viewport(), from - QPoint(0, 60));
        settle();
        QTest::mouseMove(menu->viewport(), from - QPoint(0, 120));
        settle();
        QTest::mouseRelease(menu->viewport(), Qt::LeftButton, {}, from - QPoint(0, 120));
        settle();
        require(elsewhere && focused && insideOn(ganderRow(2)) && menu->isVisible(),
                "J17 (b) a drag from the empty part of the open menu: the edge stays on Afro house");
        require(shown == before && activations == count, "J17 (b) the drag: the table is not changed");
        closeMenu();
    }
    {
        openMenu();
        const QString before = shown;
        const int count = activations;
        const bool elsewhere = focusElsewhere();
        const QPoint from = menu->visualRect(ganderRow(3)).center();
        QTest::mousePress(menu->viewport(), Qt::LeftButton, {}, from);
        settle();
        const bool focused = menu->hasFocus();
        QTest::mouseMove(menu->viewport(), from - QPoint(0, 40));
        settle();
        QTest::mouseMove(menu->viewport(), from - QPoint(0, 90));
        settle();
        QTest::mouseRelease(menu->viewport(), Qt::LeftButton, {}, from - QPoint(0, 90));
        settle();
        require(elsewhere && focused && insideOn(ganderRow(2)) && menu->isVisible(),
                "J17 (b) a drag of the menu's rows (from Warm-up): the edge stays on Afro house, nothing opens");
        require(shown == before && activations == count, "J17 (b) the row drag: the table is not changed");
        closeMenu();
    }

    // (a) A folder row: the folder current after BACK (build B), then a
    // model reset; the next ☰ has the edge on the folder.
    {
        openMenu();
        tap(ganderRow(1));
        const bool entered = menu->rootIndex() == ganderRow(1);
        back()->click();
        settle();
        const bool backOnFolder = menu->rootIndex() == sidebarDrive("GANDER1") &&
                menu->currentIndex() == ganderRow(1);
        closeMenu();
        const bool cleared = resetModel();
        openMenu();
        require(entered && backOnFolder && cleared && insideOn(ganderRow(1)),
                "J17 (a) the folder current (BACK), a model reset, then ☰: current = the folder, not TRACKS");
        closeMenu();
    }
    // A list of another level in view (Deep cuts, inside the folder), then a
    // model reset (the menu lands on the drive's own level): no row of that
    // level shows it, so the current row stays as it is (none), not TRACKS.
    {
        openMenu();
        if (menu->rootIndex() != ganderRow(1)) {
            tap(ganderRow(1));
        }
        const QModelIndex deep = model.index(0, 0, ganderRow(1));
        const bool deepRow = deep.data().toString().startsWith("Deep cuts");
        tap(deep);
        const bool picked = menu->currentIndex() == deep;
        closeMenu();
        const bool cleared = resetModel();
        openMenu();
        const QModelIndex node = sidebarDrive("GANDER1");
        int drawn = 0;
        for (int row = 0; row < model.rowCount(node); ++row) {
            drawn += edgeDrawnOn(model.index(row, 0, node)) ? 1 : 0;
        }
        std::cout << "OBSERVE Deep cuts then reset: root '" << menu->rootIndex().data().toString().toStdString()
                  << "' current '" << menu->currentIndex().data().toString().toStdString() << "' drawn " << drawn
                  << std::endl;
        require(deepRow && picked && cleared && menu->isSourceMenuInside() && menu->rootIndex() == node &&
                        !menu->currentIndex().isValid() && drawn == 0,
                "J17 a list of another level (Deep cuts), a model reset, then ☰: the current row stays as it is (none), not TRACKS");
        closeMenu();
    }

    // (c) TRACKS in view: a focus-in keeps it current, and ☰ edges TRACKS
    // (J16 unchanged).
    {
        openMenu();
        tap(ganderRow(0));
        closeMenu();
        const bool tracksShown = shown == "Rekordbox/Tracks" && menu->currentIndex() == ganderRow(0);
        QFocusEvent focus(QEvent::FocusIn, Qt::MouseFocusReason);
        QApplication::sendEvent(menu.get(), &focus);
        settle();
        const bool kept = menu->currentIndex() == ganderRow(0);
        openMenu();
        std::cout << "OBSERVE TRACKS tapped: shown '" << shown.toStdString() << "' kept " << kept << std::endl;
        require(tracksShown && kept && insideOnTracks("GANDER1"),
                "J17 (c) TRACKS in view, a focus-in keeps it current, then ☰: the edge on TRACKS");
        closeMenu();
        menu->selectionModel()->clearCurrentIndex();
        settle();
        openMenu();
        require(insideOnTracks("GANDER1"),
                "J17 (c) TRACKS in view, clearCurrentIndex(), then ☰: TRACKS (J16 unchanged)");
        closeMenu();
        resetModel();
        openMenu();
        require(insideOnTracks("GANDER1"), "J17 (c) TRACKS in view, a model reset, then ☰: TRACKS (J16 unchanged)");
        closeMenu();
    }

    // (d) J16's first OPEN, J4, J5 and BACK.
    newMenu();
    openDrive("IXIAN", false);
    openMenu();
    require(insideOnTracks("IXIAN"),
            "J17 (d) OPEN before ☰ was ever shown: the first ☰ opens inside IXIAN › rekordbox, the edge on TRACKS (J16 unchanged)");
    closeMenu();
    openDrive("GANDER1", false);
    pick(2);
    const bool afroBeforeEject = menu->currentIndex() == ganderRow(2);
    pull("GANDER1");
    openMenu();
    require(afroBeforeEject && topWithoutEdge() && !tileNamed(*menu, "GANDER1"),
            "J17 (d) J4: Afro house in view, then the eject: ☰ at the top level, no edge, nothing current");
    closeMenu();
    plug(gander, "rev-g2");
    openDrive("GANDER1", false);
    openMenu();
    require(insideOnTracks("GANDER1"),
            "J17 (d) the drive back and OPEN: inside GANDER1 › rekordbox, the edge on TRACKS (J5 unchanged)");
    back()->click();
    settle();
    require(!menu->isSourceMenuInside() && tileNamed(*menu, "GANDER1") && tileNamed(*menu, "GANDER1")->isChecked() &&
                    edges() == 1,
            "J17 (d) then BACK: the top level, the edge on GANDER1 only (build E)");
    closeMenu();
    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == savedStart,
            "J17 does not change the saved start (★)");

    // The desktop sidebar (no touch navigation): a focus-in still clears the
    // current row (upstream).
    {
        menu.reset();
        settle();
        WLibrarySidebar desktop(&wrapper);
        desktop.setModel(&model);
        desktop.setGeometry(0, 100, 240, 380);
        desktop.show();
        settle();
        desktop.selectionModel()->setCurrentIndex(library.sourceRow("PlaylistFeature"),
                QItemSelectionModel::ClearAndSelect | QItemSelectionModel::Rows);
        const bool set = desktop.currentIndex().isValid();
        QFocusEvent focus(QEvent::FocusIn, Qt::MouseFocusReason);
        QApplication::sendEvent(&desktop, &focus);
        settle();
        require(set && !desktop.currentIndex().isValid(),
                "desktop sidebar: a focus-in still clears the current row (unchanged)");
    }

    std::cout << "OK " << failures << std::endl;
    return failures ? 1 : 0;
}
