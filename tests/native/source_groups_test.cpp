// R-9 step 3: grouped Sources. The real WLibrarySidebar at the Sources
// screen size (800x384) with the real SidebarModel, wired by the exact
// connects from Library::bindSidebarWidget, and the actual Library methods
// (sourceGroupTiles, mapSourceGroups, driveRows, applySidebarSourceVisibility,
// refreshSidebarSourceEdit, ...) from the patched library.cpp. Substitutes:
// the features (named trees), the settings and the controls.
#include <QApplication>
#include <QDir>
#include <QFileInfo>
#include <QLabel>
#include <QPointer>
#include <QPushButton>
#include <QScopedPointer>
#include <QScrollArea>
#include <QSettings>
#include <QTemporaryDir>
#include <QTest>
#include <QTimer>
#include <iostream>
#include <memory>

#include "control/controlobject.h"
#include "library/libraryfeature.h"
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
};

#include "library_sample_methods.h"

void settle() {
    for (int round = 0; round < 4; ++round) {
        QApplication::processEvents();
    }
}

std::unique_ptr<TreeItem> item(const QString& label, const QVariant& data) {
    return std::make_unique<TreeItem>(label, data);
}

QStringList tileNames(WLibrarySidebar& sidebar) {
    QStringList names;
    for (auto* tile : sidebar.sourceTiles()) {
        names.append(tile->accessibleName());
    }
    return names;
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
    const QString stick = QDir(home.path()).filePath("media/STICK");
    const QString mantacore = QDir(home.path()).filePath("media/MANTACORE");
    for (const auto& path : {samples, stick, mantacore}) {
        QDir().mkpath(path);
    }
    // The owner hid Crates, History and Serato before grouping.
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceCrateFeature"), false);
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceSetlogFeature"), false);
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceSeratoFeature"), false);

    SidebarModel model;
    Library library(&settings, &model);
    library.m_samplesPath = samples;
    LibraryFeature tracks("Tracks");
    LibraryFeature playlists("Playlists");
    LibraryFeature crates("Crates");
    LibraryFeature autodj("Auto DJ");
    LibraryFeature computer("Computer");
    LibraryFeature recordings("Recordings");
    LibraryFeature history("History");
    LibraryFeature analyse("Analyse");
    LibraryFeature rekordbox("Rekordbox");
    LibraryFeature serato("Serato");
    playlists.children.getRootItem()->appendChild("Warm up", 1);
    playlists.children.getRootItem()->appendChild("Edits", 2);
    {
        auto* root = computer.children.getRootItem();
        root->appendChild("Quick Links", QUICK_LINK_NODE);
        root->appendChild("Removable Devices", DEVICE_NODE);
        root->appendChild("/", "/");
        root->appendChild("Samples", QString(samples + "/"));
    }
    // Same order as Library: Tracks first, Rekordbox and Serato last.
    library.add("MixxxLibraryFeature", &tracks);
    library.add("AutoDJFeature", &autodj);
    library.add("PlaylistFeature", &playlists);
    library.add("CrateFeature", &crates);
    library.add("BrowseFeature", &computer);
    library.add("RecordingFeature", &recordings);
    library.add("SetlogFeature", &history);
    library.add("AnalysisFeature", &analyse);
    library.add("RekordboxFeature", &rekordbox);
    library.add("SeratoFeature", &serato);

    WLibrarySidebar sidebar;
    sidebar.setModel(&model);
    {
        WLibrarySidebar* pSidebarWidget = &sidebar;
        SidebarModel* m_pSidebarModel = &model;
        auto connect = [](auto&&... arguments) { return QObject::connect(arguments...); };
#include "sidebar_activation_wiring.inc"
    }
    QObject::connect(&model, &SidebarModel::selectIndex, &sidebar, &WLibrarySidebar::selectIndex);
    QString shown;
    int activations = 0;
    LibraryFeature::shown = [&](const QString& list) {
        shown = list;
        ++activations;
        // Library::slotShowTrackModel: a list is in Tracks now.
        sidebar.noteSourceShown();
    };
    library.m_pSidebarWidget = &sidebar;
    {
        // The lines from Library::bindSidebarWidget (the runner points them
        // at this Library).
        Library* self = &library;
        WLibrarySidebar* pSidebarWidget = &sidebar;
#include "grouped_binding.inc"
    }
    QObject::connect(&model, &QAbstractItemModel::modelReset, &sidebar,
            [&library] { library.applySidebarSourceVisibility(); });
    ControlObject screen(ConfigKey("[MixPi]", "screen"));
    ControlObject sidebarVisible(ConfigKey("[Sidebar]", "sidebar_visible"));
    sidebar.enableTouchNavigation();
    sidebar.resize(800, 384);
    sidebar.show();
    library.applySidebarSourceVisibility();
    settle();

    // The one-time mapping of the owner's choices.
    require(settings.getValue(ConfigKey(kConfigGroup, "SourceGroupsMapped"), false) &&
                    settings.getValue(ConfigKey(kConfigGroup, "SourceGroupThisPi"), false) &&
                    settings.getValue(ConfigKey(kConfigGroup, "SourceGroupDrives"), false),
            "the mapping runs once and keeps This Pi and drives on");
    require(sidebar.hasSourceScreen() && library.groupedSources(), "an 800 px touch sidebar groups Sources");
    require(tileNames(sidebar) == QStringList({"This Pi", "Recordings", "Folders", "Samples", "More"}),
            "without a drive the tiles are This Pi, Recordings, Folders, Samples, More");
    require(!tileNamed(sidebar, "History"), "the one-time mapping keeps a hidden source hidden (History)");
    require(sidebar.selectedSourceTile() == LibraryInterface::SourceGroups::kThisPi &&
                    sidebar.sourceTiles().first()->isChecked(),
            "without a drive the first tile is This Pi, selected");
    require(shownRows(sidebar) == QStringList({"Tracks", "Auto DJ", "Playlists"}),
            "This Pi shows exactly its features, minus hidden ones (Crates)");
    require(sidebar.sourceCrumb() == "This Pi" && !sidebar.findChild<QPushButton*>("MixpiSourceBack")->isEnabled(),
            "the crumb says This Pi; Back is off");
    auto* more = tileNamed(sidebar, "More");
    require(more && more->findChild<QLabel*>("MixpiSourceTileSub")->text() == "Analyse",
            "More holds the other sources that are on (Analyse; not Serato, not Rekordbox)");
    bool sized = true;
    for (auto* tile : sidebar.sourceTiles()) {
        sized &= tile->height() == 64 && tile->width() >= 200 && tile->width() <= 264;
    }
    require(sized, "tiles are 64 px high in the 264 px rail");

    // A source hidden by a tile is not a hidden source.
    const QModelIndex recordingsRow = library.sourceRow("RecordingFeature");
    sidebar.selectionModel()->setCurrentIndex(recordingsRow, QItemSelectionModel::ClearAndSelect);
    const int before = activations;
    library.applySidebarSourceVisibility();
    settle();
    require(activations == before && sidebar.currentIndex() == recordingsRow,
            "a row This Pi does not show is not a hidden context: nothing is reopened");

    // Drill in and back within This Pi.
    const QModelIndex playlistsRow = library.sourceRow("PlaylistFeature");
    QTest::mouseClick(sidebar.viewport(), Qt::LeftButton, {}, sidebar.visualRect(playlistsRow).center());
    settle();
    require(sidebar.rootIndex() == playlistsRow && sidebar.sourceCrumb() == "This Pi › Playlists",
            "a row with children drills in; the crumb is This Pi › Playlists");
    sidebar.findChild<QPushButton*>("MixpiSourceBack")->click();
    settle();
    require(!sidebar.rootIndex().isValid() && shownRows(sidebar) == QStringList({"Tracks", "Auto DJ", "Playlists"}),
            "Back returns to This Pi's rows");

    // A rekordbox drive comes: its tile is first.
    auto drive = item("MANTACORE", QVariantList{mantacore, QString(), QStringLiteral("rev-1")});
    drive->appendChild("Friday set", 11);
    drive->appendChild("Grime", 12);
    {
        std::vector<std::unique_ptr<TreeItem>> rows;
        rows.push_back(std::move(drive));
        rekordbox.children.insertTreeItemRows(std::move(rows), 0);
    }
    settle();
    require(tileNames(sidebar).value(0) == "MANTACORE" &&
                    sidebar.sourceTiles().first()->findChild<QLabel*>("MixpiSourceTileSub")->text() ==
                            QString::fromUtf8("USB drive · rekordbox"),
            "with a drive the first tile is the drive");
    sidebar.sourceTiles().first()->click();
    settle();
    const QModelIndex driveRow = model.index(0, 0, library.sourceRow("RekordboxFeature"));
    require(shown == "Rekordbox/MANTACORE" && sidebar.rootIndex() == driveRow,
            "a tap on the drive tile opens it and shows that drive's rows");
    require(shownRows(sidebar) == QStringList({"Friday set", "Grime"}) &&
                    sidebar.sourceCrumb() == "MANTACORE" && sidebar.sourceTiles().first()->isChecked(),
            "its rows are the drive's node; the crumb names the drive; its tile is lit");
    require(!sidebar.findChild<QPushButton*>("MixpiSourceBack")->isEnabled(),
            "Back is off at the drive: it does not go up to all drives");
    screen.setAndConfirm(1);
    sidebarVisible.setAndConfirm(1);
    const QModelIndex friday = model.index(0, 0, driveRow);
    QTest::mouseClick(sidebar.viewport(), Qt::LeftButton, {}, sidebar.visualRect(friday).center());
    settle();
    require(shown == "Rekordbox/Friday set" && screen.get() == 0 && sidebarVisible.get() == 0,
            "a tap on a drive playlist opens it in Tracks and closes Sources");

    // A drive opened in Computer joins after it, in plug-in order.
    {
        std::vector<std::unique_ptr<TreeItem>> rows;
        rows.push_back(item(stick, stick));
        computer.children.insertTreeItemRows(std::move(rows), computer.children.rowCount());
    }
    settle();
    require(tileNames(sidebar).mid(0, 2) == QStringList({"MANTACORE", "STICK"}) &&
                    tileNamed(sidebar, "STICK")->findChild<QLabel*>("MixpiSourceTileSub")->text() == "USB drive",
            "a drive opened in Computer gets a tile, in plug-in order");

    // Unplug while the drive tile is selected.
    sidebar.sourceTiles().first()->click();
    settle();
    require(sidebar.selectedSourceTile() == QString("drive:" + QDir::cleanPath(mantacore)),
            "the drive tile is selected again");
    rekordbox.children.removeRows(0, 1);
    settle();
    bool valid = true;
    for (int tile = 0; tile < sidebar.sourceTiles().size(); ++tile) {
        valid &= !sidebar.sourceTiles().at(tile)->accessibleName().isEmpty();
    }
    require(sidebar.selectedSourceTile() == LibraryInterface::SourceGroups::kThisPi &&
                    tileNamed(sidebar, "This Pi")->isChecked() && !tileNamed(sidebar, "MANTACORE"),
            "unplugged while selected: This Pi is selected and the drive tile is gone");
    require(valid && !sidebar.rootIndex().isValid() && sidebar.sourceCrumb() == "This Pi" &&
                    !sidebar.findChild<QPushButton*>("MixpiSourceBack")->isEnabled() &&
                    shownRows(sidebar) == QStringList({"Tracks", "Auto DJ", "Playlists"}),
            "nothing dangles: top level, This Pi's rows, Back off");
    QDir(stick).removeRecursively();
    sidebar.sourcesChanged();
    settle();
    require(!tileNamed(sidebar, "STICK"), "a Computer drive whose folder is gone loses its tile");

    // A node tile without children (Recordings) shows its own row.
    tileNamed(sidebar, "Recordings")->click();
    settle();
    require(shown == "Recordings" && sidebar.sourceCrumb() == "Recordings",
            "a tap on Recordings opens it");

    // Sources edit lists the tiles.
    QWidget tracksPane;
    library.m_pLibraryWidget = &tracksPane;
    library.showSidebarSourcesMenu();
    settle();
    auto* list = static_cast<LibraryInterface::SourceEditList*>(library.m_pSidebarSourceEdit.data());
    auto rowNames = [&list] {
        QStringList names;
        for (auto* row : list->rows()) {
            names.append(row->findChild<QPushButton*>("MixpiSourceEditName")->text());
        }
        return names;
    };
    auto rowNamed = [&list](const QString& prefix) -> QWidget* {
        for (auto* row : list->rows()) {
            if (row->findChild<QPushButton*>("MixpiSourceEditName")->text().startsWith(prefix)) {
                return row;
            }
        }
        return nullptr;
    };
    const QString dot = QString::fromUtf8("· ");
    const QStringList expected{"USB drives (each drive)", "This Pi", dot + "Tracks", dot + "Playlists",
            dot + "Crates", dot + "Auto DJ", "Recordings", "History", "Folders", "Samples", "More",
            dot + "Analyse", dot + "Serato"};
    if (!list || rowNames() != expected) {
        std::cout << "OBSERVE edit rows " << (list ? rowNames().join(" | ").toStdString() : "none")
                  << std::endl;
    }
    require(list && rowNames() == expected,
            "Sources edit lists the tiles in order, This Pi's and More's sources below them");
    if (!list || rowNames() != expected) {
        std::cout << "FAILED " << failures << std::endl;
        return 1;
    }
    auto* trackRow = rowNamed(dot + "Tracks");
    require(trackRow && trackRow->findChild<QPushButton*>("MixpiSourceEditUp")->isHidden() &&
                    !trackRow->findChild<QCheckBox*>("MixpiSourceEditSwitch")->isHidden(),
            "a source row inside a group has a switch, no Up or Down");
    require(!rowNamed("USB drives")->findChild<QPushButton*>("MixpiSourceEditUp")->isEnabled() &&
                    rowNamed("This Pi")->findChild<QPushButton*>("MixpiSourceEditUp")->isEnabled() &&
                    !rowNamed("More")->findChild<QPushButton*>("MixpiSourceEditDown")->isEnabled(),
            "Up and Down move between tile rows only");
    rowNamed("Recordings")->findChild<QPushButton*>("MixpiSourceEditDown")->click();
    settle();
    require(library.sourceGroupOrder().mid(2, 2) == QStringList({"SetlogFeature", "RecordingFeature"}) &&
                    rowNames().indexOf("History") < rowNames().indexOf("Recordings"),
            "Down moves a tile and saves the tile order");
    rowNamed("This Pi")->findChild<QPushButton*>("MixpiSourceEditDown")->click();
    settle();
    require(rowNames().mid(1, 6) == QStringList({"History", "This Pi", dot + "Tracks", dot + "Playlists",
                                                dot + "Crates", dot + "Auto DJ"}),
            "a group moves with its source rows");
    rowNamed("History")->findChild<QCheckBox*>("MixpiSourceEditSwitch")->click();
    settle();
    require(settings.getValue(ConfigKey(kConfigGroup, "SidebarSourceSetlogFeature"), false),
            "the History switch writes its source's own key");
    rowNamed(dot + "Crates")->findChild<QCheckBox*>("MixpiSourceEditSwitch")->click();
    settle();
    rowNamed("USB drives")->findChild<QCheckBox*>("MixpiSourceEditSwitch")->click();
    settle();
    require(!settings.getValue(ConfigKey(kConfigGroup, "SourceGroupDrives"), true),
            "the drives switch writes the group's key");
    rowNamed("This Pi")->findChild<QPushButton*>("MixpiSourceEditName")->click();
    list->startButton()->click();
    settle();
    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == "MixxxLibraryFeature",
            "Start here on This Pi starts at Tracks");
    library.showSidebarSourcesMenu();
    settle();
    require(!sidebar.isSourcesEditing() &&
                    tileNames(sidebar) == QStringList({"History", "This Pi", "Recordings", "Folders",
                                                "Samples", "More"}),
            "DONE: the rail shows the new order with History");
    tileNamed(sidebar, "This Pi")->click();
    settle();
    require(shownRows(sidebar) == QStringList({"Tracks", "Auto DJ", "Playlists", "Crates"}),
            "a source switched on inside This Pi shows there");
    {
        std::vector<std::unique_ptr<TreeItem>> rows;
        rows.push_back(item("MANTACORE", QVariantList{mantacore, QString(), QStringLiteral("rev-2")}));
        rekordbox.children.insertTreeItemRows(std::move(rows), 0);
    }
    settle();
    require(!tileNamed(sidebar, "MANTACORE"), "with the drives switch off, a drive gets no tile");

    // The mapping runs once; a group whose sources are all hidden starts hidden.
    settings.setValue(ConfigKey(kConfigGroup, "SourceGroupThisPi"), true);
    library.mapSourceGroups();
    require(settings.getValue(ConfigKey(kConfigGroup, "SourceGroupThisPi"), false),
            "the mapping does not run again");
    for (const auto& id : LibraryInterface::SourceGroups::thisPi()) {
        settings.setValue(ConfigKey(kConfigGroup, "SidebarSource" + id), false);
    }
    settings.remove(ConfigKey(kConfigGroup, "SourceGroupsMapped"));
    library.mapSourceGroups();
    require(!settings.getValue(ConfigKey(kConfigGroup, "SourceGroupThisPi"), true),
            "a tile whose sources were all hidden starts hidden");

    // A narrow sidebar keeps one tile per source and no filter.
    sidebar.resize(300, 384);
    settle();
    bool none = true;
    for (int row = 0; row < model.rowCount(); ++row) {
        none &= sidebar.isRowHidden(row, {}) == sidebar.isSourceRowHidden(row);
    }
    require(!sidebar.hasSourceScreen() && !library.groupedSources() && none,
            "a narrow touch sidebar has no tiles and hides only the owner's hidden sources");

    std::cout << (failures ? "FAILED " : "OK ") << failures << std::endl;
    return failures ? 1 : 0;
}
