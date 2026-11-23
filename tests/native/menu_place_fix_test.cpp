// Spec 2e (wave J16): ☰ after OPEN always opens inside the drive with the edge
// on TRACKS (council round 8, Opus; investigation-R8-edge).
//
// As source_groups_test.cpp: the real WLibrarySidebar as the 320x380 menu at
// the right of an 800x480 screen, the real SidebarModel wired by the exact
// connects from Library::bindSidebarWidget, the actual Library methods from
// the patched library.cpp and the actual rekordbox playlist tree builder with
// the drive's Tracks row (driveTracksRow). A drive opens as
// Library::openRemovableSourceAsync opens it: activateChild, featureSelect with
// the drive's row, openShownSource (the ★ start: followShownSource), then
// RekordboxFeature::selectShownDriveTracks's featureSelect with its Tracks row.
//
// Unlike source_groups_test.cpp, a menu here can be one that was never shown:
// as on the card, the hidden sidebar has no width until ☰ first shows it.
// Built by tests/native/menu_place_fix_runner.py (--baseline: without
// mixxx-menu-place-fix.patch).
#include <QApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFocusEvent>
#include <QLabel>
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

    // (a) Cause 1, reproduced on the card 2 of 2: after a Mixxx start, the
    // first OPEN before ☰ was ever shown. openShownSource returned early (the
    // sidebar was not the menu yet: no width), so ☰ opened at the top level
    // with the edge on the drive's tile.
    newMenu();
    require(!menu->hasSourceScreen() && menu->width() < LibraryInterface::kSourceScreenMinimumWidth,
            "a sidebar never shown is not the Sources menu yet (no width)");
    openDrive("GANDER1", false);
    require(shown == "Rekordbox/GANDER1", "OPEN: Tracks shows GANDER1");
    openMenu();
    require(insideOnTracks("GANDER1"),
            "J16 (a) OPEN before ☰ was ever shown: the first ☰ opens inside GANDER1 › rekordbox, the edge on TRACKS");
    if (const QString directory = qEnvironmentVariable("MIXPI_SOURCES_GRAB_DIR"); !directory.isEmpty()) {
        screen.grab().save(directory + "/j16-first-menu-after-open.png");
    }
    // BACK keeps build E: the top level, the edge on the drive only.
    back()->click();
    settle();
    require(!menu->isSourceMenuInside() && tileNamed(*menu, "GANDER1") &&
                    tileNamed(*menu, "GANDER1")->isChecked() && edges() == 1,
            "J16 (a) then BACK: the top level, the edge on GANDER1 only (build E)");
    closeMenu();

    // The same with the menu shown before the OPEN (J5, unchanged).
    newMenu();
    openMenu();
    closeMenu();
    openDrive("GANDER1", false);
    openMenu();
    require(insideOnTracks("GANDER1"), "J5 kept: OPEN after ☰ was shown once: inside GANDER1 › rekordbox, the edge on TRACKS");
    closeMenu();

    // BROWSE and the ping's LOAD take the same path: a second drive, never
    // shown before.
    newMenu();
    openDrive("IXIAN", false);
    openMenu();
    require(insideOnTracks("IXIAN"),
            "J16 (a) BROWSE or LOAD before ☰ was ever shown: the first ☰ opens inside IXIAN › rekordbox, the edge on TRACKS");
    closeMenu();

    // The ★ start keeps build I's menu (followShownSource): the top level,
    // the edge on the drive.
    newMenu();
    openDrive("GANDER1", true);
    openMenu();
    require(!menu->isSourceMenuInside() && tileNamed(*menu, "GANDER1") &&
                    tileNamed(*menu, "GANDER1")->isChecked() && edges() == 1,
            "★ start before ☰ was ever shown: the top level, the edge on the drive (kept)");
    closeMenu();

    // (c) J4 before ☰ was ever shown: OPEN, then the drive is ejected; the
    // remembered OPEN goes with it. The top level, nothing current (the top
    // level's own rules mark the tile it lands on, as before J16).
    newMenu();
    openDrive("IXIAN", false);
    pull("IXIAN");
    openMenu();
    std::cout << "OBSERVE J4 never shown: inside " << menu->isSourceMenuInside() << " edges " << edges()
              << " tile '" << menu->selectedSourceTile().toStdString() << "'" << std::endl;
    require(!menu->isSourceMenuInside() && edit()->isVisible() && !menu->currentIndex().isValid() &&
                    !tileNamed(*menu, "IXIAN"),
            "J16 (c) J4: OPEN, then an eject before ☰ was ever shown: ☰ at the top level, nothing current");
    closeMenu();
    plug(ixian, "rev-i2");

    // (b) Cause 2 (acceptance M 38-menu): inside the drive with the edge, the
    // current row goes while the place stays. The next ☰ has the edge on
    // TRACKS again; the table is not changed. (The menu was shown once
    // before the OPEN, so this is cause 2 alone.)
    newMenu();
    openMenu();
    closeMenu();
    openDrive("GANDER1", false);
    openMenu();
    require(insideOnTracks("GANDER1"), "(b) start: inside GANDER1 › rekordbox, the edge on TRACKS");
    closeMenu();
    {
        const QString before = shown;
        const int count = activations;
        menu->selectionModel()->clearCurrentIndex();
        settle();
        const bool cleared = !menu->currentIndex().isValid();
        openMenu();
        require(cleared && insideOnTracks("GANDER1"),
                "J16 (b) clearCurrentIndex(), then ☰: inside GANDER1 › rekordbox, current = TRACKS");
        require(shown == before && activations == count, "J16 (b) clearCurrentIndex: the table is not changed");
        closeMenu();
    }
    {
        const QString before = shown;
        const int count = activations;
        QFocusEvent focus(QEvent::FocusIn, Qt::MouseFocusReason);
        QApplication::sendEvent(menu.get(), &focus);
        settle();
        // Wave J17 (mixxx-menu-current-row.patch): in the touch menu a
        // focus-in no longer clears the current row, so TRACKS stays current
        // and is not restored. Either way ☰ has the edge on TRACKS.
        const bool cleared = !menu->currentIndex().isValid();
        std::cout << "OBSERVE focus-in cleared the current row " << cleared << std::endl;
        openMenu();
        require(insideOnTracks("GANDER1"),
                "J16 (b) a focus-in (clearCurrentIndex at :1429), then ☰: inside GANDER1 › rekordbox, current = TRACKS");
        require(shown == before && activations == count, "J16 (b) focus-in: the table is not changed");
        closeMenu();
    }
    {
        const QString before = shown;
        const int count = activations;
        // A sidebar model reset (a feature's tree rebuilt): rebuildSourceRail
        // enters the drive again with nothing current.
        history.children.setRootItem(TreeItem::newRoot(&history));
        history.children.getRootItem()->appendChild("2026-11-15", 3);
        settle();
        const bool cleared = !menu->currentIndex().isValid();
        openMenu();
        require(cleared && insideOnTracks("GANDER1"),
                "J16 (b) a sidebar model reset, then ☰: inside GANDER1 › rekordbox, current = TRACKS");
        require(shown == before && activations == count, "J16 (b) model reset: the table is not changed");
        closeMenu();
    }
    {
        // LOAD 1, play, pause, unload, Decks and back to Tracks: none of it
        // touches the menu; the next ☰ has the edge on TRACKS.
        openMenu();
        require(insideOnTracks("GANDER1"), "J16 (b) ☰ again with nothing in between: the edge stays on TRACKS");
        closeMenu();
    }
    {
        // A list of the drive picked in the menu keeps its edge (a tap).
        openMenu();
        const QModelIndex afro = model.index(2, 0, sidebarDrive("GANDER1"));
        const QString before = shown;
        QTest::mouseClick(menu->viewport(), Qt::LeftButton, {}, menu->visualRect(afro).center());
        settle();
        std::cout << "OBSERVE picked '" << shown.toStdString() << "' current '"
                  << menu->currentIndex().data().toString().toStdString() << "'" << std::endl;
        const bool picked = shown != before && shown.startsWith("Rekordbox/") && menu->currentIndex() == afro;
        closeMenu();
        openMenu();
        require(picked && menu->isSourceMenuInside() && menu->currentIndex() == afro && edgeDrawnOn(afro),
                "a playlist picked inside the drive: ☰ keeps the edge on it, not TRACKS");
        // Inside a folder of the drive: the folder row stays current (build B).
        const QModelIndex folder = model.index(1, 0, sidebarDrive("GANDER1"));
        QTest::mouseClick(menu->viewport(), Qt::LeftButton, {}, menu->visualRect(folder).center());
        settle();
        const bool entered = menu->rootIndex() == folder && menu->currentIndex() == folder;
        closeMenu();
        openMenu();
        require(entered && menu->rootIndex() == folder && menu->currentIndex() == folder,
                "inside a folder of the drive: ☰ keeps the folder current (build B)");
        back()->click();
        settle();
        require(menu->rootIndex() == sidebarDrive("GANDER1") && menu->currentIndex() == folder,
                "BACK from the folder: the drive's rows, the folder current (build B)");
        closeMenu();
    }
    {
        // This Pi › TRACKS picked: the menu is inside This Pi, not a drive,
        // and keeps its own edge.
        openMenu();
        while (menu->isSourceMenuInside()) {
            back()->click();
            settle();
        }
        tileNamed(*menu, "This Pi")->click();
        settle();
        QTest::mouseClick(menu->viewport(), Qt::LeftButton, {},
                menu->visualRect(library.sourceRow("MixxxLibraryFeature")).center());
        settle();
        const bool thisPi = shown == "Tracks";
        closeMenu();
        openMenu();
        require(thisPi && menu->isSourceMenuInside() && menu->sourceCrumb() == "This Pi" &&
                        menu->currentIndex() == library.sourceRow("MixxxLibraryFeature"),
                "This Pi › TRACKS picked: ☰ opens inside This Pi with its edge (unchanged)");
        closeMenu();
    }

    // (c) J4 with the menu shown: inside the drive with the edge, then the
    // eject: the top level, no edge on a row that is not in view.
    openDrive("GANDER1", false);
    openMenu();
    require(insideOnTracks("GANDER1"), "(c) start: OPEN, inside GANDER1 › rekordbox, the edge on TRACKS");
    closeMenu();
    pull("GANDER1");
    openMenu();
    require(topWithoutEdge() && !tileNamed(*menu, "GANDER1"),
            "J16 (c) J4: the eject with the drive's list in Tracks: ☰ at the top level, no edge, nothing current");
    closeMenu();
    // Another drive ejected leaves the menu alone.
    plug(gander, "rev-g2");
    openDrive("GANDER1", false);
    pull("IXIAN");
    openMenu();
    require(insideOnTracks("GANDER1"), "J4 kept: another drive ejected: inside GANDER1 › rekordbox, the edge on TRACKS");
    closeMenu();
    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == savedStart,
            "J16 does not change the saved start (★)");

    // A drive opened in Folders (no export) before ☰ was ever shown: the
    // first ☰ lands where it lands after ☰ was shown once (J5's folder case).
    auto openStick = [&] {
        {
            std::vector<std::unique_ptr<TreeItem>> rows;
            auto stickItem = std::make_unique<TreeItem>(stick, stick);
            stickItem->appendChild("Sets", QString(stick + "/Sets"));
            rows.push_back(std::move(stickItem));
            computer.children.insertTreeItemRows(std::move(rows), computer.children.rowCount());
        }
        settle();
        const QModelIndex featureStick = computer.children.index(computer.children.rowCount() - 1, 0);
        computer.activateChild(featureStick);
        emit computer.featureSelect(&computer, featureStick);
        library.applySidebarSourceVisibility();
        settle();
        menu->openShownSource();
        settle();
    };
    auto dropStick = [&] {
        computer.children.removeRows(computer.children.rowCount() - 1, 1);
        settle();
    };
    newMenu();
    openMenu();
    closeMenu();
    openStick();
    openMenu();
    const bool shownInside = menu->isSourceMenuInside();
    const QString shownCrumb = menu->sourceCrumb();
    const QString shownCurrent = menu->currentIndex().data().toString();
    closeMenu();
    dropStick();
    newMenu();
    openStick();
    openMenu();
    std::cout << "OBSERVE folder J5 inside " << shownInside << " '" << shownCrumb.toStdString() << "' current '"
              << shownCurrent.toStdString() << "'; J16 inside " << menu->isSourceMenuInside() << " '"
              << menu->sourceCrumb().toStdString() << "' current '"
              << menu->currentIndex().data().toString().toStdString() << "'" << std::endl;
    require(menu->isSourceMenuInside() == shownInside && menu->sourceCrumb() == shownCrumb &&
                    menu->currentIndex().data().toString() == shownCurrent &&
                    shownCrumb.startsWith(QStringLiteral("STICK")),
            "J16 (a) folder drive opened before ☰ was ever shown: the first ☰ lands as J5 does (STICK)");
    closeMenu();
    dropStick();

    menu.reset();
    std::cout << "OK " << failures << std::endl;
    return failures ? 1 : 0;
}
