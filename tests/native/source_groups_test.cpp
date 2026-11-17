// R-9 step 3 and agreed UI s5: grouped Sources in the side menu. The real
// WLibrarySidebar as the 320x380 menu at the right of an 800x480 screen (under
// #LibraryWrapper, as in the skin) with the real SidebarModel, wired by the
// exact connects from Library::bindSidebarWidget, and the actual Library
// methods (sourceGroupTiles, mapSourceGroups, driveRows,
// applySidebarSourceVisibility, refreshSidebarSourceEdit, ...) from the
// patched library.cpp. Substitutes: the features (named trees), the settings
// and the controls. With MIXPI_QSS_DIR set, the screen carries the skin's
// style sheets in their installed order; with MIXPI_SOURCES_GRAB_DIR set, the
// menu and the edit list are rendered there at 800x480.
#include <QApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QLabel>
#include <QPointer>
#include <QPushButton>
#include <QScopedPointer>
#include <QScrollArea>
#include <QScrollBar>
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

QString tileSub(WLibrarySidebar& sidebar, const QString& name) {
    auto* tile = tileNamed(sidebar, name);
    auto* sub = tile ? tile->findChild<QLabel*>("MixpiSourcesMenuSub") : nullptr;
    return sub ? sub->text() : QStringLiteral("<none>");
}

QString tileGlyph(WLibrarySidebar& sidebar, const QString& name) {
    auto* tile = tileNamed(sidebar, name);
    auto* icon = tile ? dynamic_cast<LibraryInterface::SourceGlyph*>(tile->findChild<QWidget*>("MixpiSourcesMenuIcon")) : nullptr;
    return icon ? icon->glyph() : QStringLiteral("<none>");
}

bool tileEnterable(WLibrarySidebar& sidebar, const QString& name) {
    auto* tile = tileNamed(sidebar, name);
    auto* mark = tile ? tile->findChild<QWidget*>("MixpiSourcesMenuChevron") : nullptr;
    return mark && !mark->isHidden();
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

// The skin's style sheets in their installed order (pioneered-touch.py,
// then mixpi-performance.py).
QString skinStyle() {
    const QString directory = qEnvironmentVariable("MIXPI_QSS_DIR");
    QString style;
    if (directory.isEmpty()) {
        return style;
    }
    for (const char* name : {"pioneered-menus.qss", "mixpi-sources-menu.qss", "pioneered-touch.qss",
                 "mixpi-performance.qss"}) {
        QFile file(QDir(directory).filePath(QString::fromLatin1(name)));
        if (file.open(QIODevice::ReadOnly)) {
            style += QString::fromUtf8(file.readAll()) + QStringLiteral("\n");
        }
    }
    return style;
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
    history.children.getRootItem()->appendChild("2026-11-15", 3);
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

    // The 800x480 screen: the skin's root carries the style sheets; the menu
    // is 320x380 at x 480-800, y 100-480 (m-sources-top.png).
    QWidget screen;
    screen.setObjectName("MixpiFixtureScreen");
    screen.resize(800, 480);
    screen.setStyleSheet(skinStyle() +
            QStringLiteral("#MixpiFixtureScreen { background-color: #0d1014; }"
                           "#MixpiFixtureNote { color: #7f8896; font-size: 13px; }"));
    QWidget wrapper(&screen);
    wrapper.setObjectName("LibraryWrapper");
    wrapper.setGeometry(0, 0, 800, 480);
    QLabel note(QStringLiteral("Top bar, Tracks header, table, strip and load row: the skin (wave C2)."),
            &wrapper);
    note.setObjectName("MixpiFixtureNote");
    note.setGeometry(12, 52, 460, 40);
    WLibrarySidebar sidebar(&wrapper);
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
    // As Library::bindSidebarWidget (tests/test_sources_screen.py checks the
    // line in library.cpp): EDIT opens the edit list.
    sidebar.sourcesEditRequested = [&library] {
        library.showSidebarSourcesMenu();
    };
    QObject::connect(&model, &QAbstractItemModel::modelReset, &sidebar,
            [&library] { library.applySidebarSourceVisibility(); });
    ControlObject screenControl(ConfigKey("[MixPi]", "screen"));
    ControlObject sidebarVisible(ConfigKey("[Sidebar]", "sidebar_visible"));
    // As Library: read-only for the skin, which reads it for EDIT LIST / DONE.
    ControlObject editing(ConfigKey("[Library]", "sidebar_sources_editing"));
    editing.setReadOnly();
    sidebar.enableTouchNavigation();
    sidebar.setGeometry(480, 100, 320, 380);
    screen.show();
    library.applySidebarSourceVisibility();
    settle();
    auto* back = sidebar.findChild<QPushButton*>("MixpiSourcesMenuBack");
    auto* edit = sidebar.findChild<QPushButton*>("MixpiSourcesMenuEdit");
    auto* place = sidebar.findChild<QLabel*>("MixpiSourcesMenuPlace");
    if (!back || !edit || !place) {
        std::cout << "FAIL the Sources menu has its header" << std::endl;
        return 1;
    }

    // The one-time mapping of the owner's choices.
    require(settings.getValue(ConfigKey(kConfigGroup, "SourceGroupsMapped"), false) &&
                    settings.getValue(ConfigKey(kConfigGroup, "SourceGroupThisPi"), false) &&
                    settings.getValue(ConfigKey(kConfigGroup, "SourceGroupDrives"), false),
            "the mapping runs once and keeps This Pi and drives on");
    require(sidebar.hasSourceScreen() && library.groupedSources(), "a 320 px touch sidebar is the grouped Sources menu");
    require(tileNames(sidebar) == QStringList({"This Pi", "Recordings", "Folders", "Samples", "More"}),
            "without a drive the rows are This Pi, Recordings, Folders, Samples, More");
    require(!tileNamed(sidebar, "History"), "the one-time mapping keeps a hidden source hidden (History)");
    require(sidebar.selectedSourceTile() == LibraryInterface::SourceGroups::kThisPi &&
                    sidebar.sourceTiles().first()->isChecked() && !sidebar.isSourceMenuInside(),
            "without a drive This Pi is the current source; the menu opens at the top level");
    require(shownRows(sidebar) == QStringList({"Tracks", "Auto DJ", "Playlists"}),
            "This Pi shows exactly its features, minus hidden ones (Crates)");
    require(back->isVisible() && back->isEnabled() && edit->isVisible() && !place->isVisible(),
            "at the top level the header has BACK and EDIT");
    require(tileSub(sidebar, "More") == "Analyse",
            "More holds the other sources that are on (Analyse; not Serato, not Rekordbox)");
    require(tileSub(sidebar, "Folders") == "Browse files and drives" &&
                    tileSub(sidebar, "Samples") == "Sounds for the pads" &&
                    tileSub(sidebar, "This Pi") == QString::fromUtf8("Tracks · Playlists · Auto DJ"),
            "each row has its small line");
    bool sized = true;
    for (auto* tile : sidebar.sourceTiles()) {
        sized &= tile->height() == 52 && tile->width() >= 290 && tile->width() <= 319;
    }
    require(sized, "rows are 52 px in the 320 px menu");
    require(tileGlyph(sidebar, "This Pi") == "pi" && tileGlyph(sidebar, "Folders") == "folder" &&
                    tileGlyph(sidebar, "Samples") == "samples" && tileGlyph(sidebar, "More") == "more" &&
                    tileGlyph(sidebar, "Recordings").isEmpty(),
            "the rows carry the mockups' icons (Recordings keeps its own)");
    auto* piIcon = dynamic_cast<LibraryInterface::SourceGlyph*>(tileNamed(sidebar, "This Pi")->findChild<QWidget*>("MixpiSourcesMenuIcon"));
    require(piIcon && !piIcon->drawn().isNull(), "a mockup icon is drawn (the SVG reader is present)");
    require(tileEnterable(sidebar, "This Pi") && tileEnterable(sidebar, "Folders") &&
                    tileEnterable(sidebar, "More") && !tileEnterable(sidebar, "Samples") &&
                    !tileEnterable(sidebar, "Recordings"),
            "› only on rows that can be entered");

    // A source hidden by a tile is not a hidden source.
    const QModelIndex recordingsRow = library.sourceRow("RecordingFeature");
    sidebar.selectionModel()->setCurrentIndex(recordingsRow, QItemSelectionModel::ClearAndSelect);
    const int before = activations;
    library.applySidebarSourceVisibility();
    settle();
    require(activations == before && sidebar.currentIndex() == recordingsRow,
            "a row This Pi does not show is not a hidden context: nothing is reopened");

    // Inside This Pi: drill in and back.
    tileNamed(sidebar, "This Pi")->click();
    settle();
    require(sidebar.isSourceMenuInside() && place->isVisible() && !edit->isVisible() &&
                    sidebar.sourceCrumb() == "This Pi" && place->text() == "This Pi" &&
                    shownRows(sidebar) == QStringList({"Tracks", "Auto DJ", "Playlists"}),
            "a tap on This Pi goes inside it: BACK, the place, its sources");
    const QModelIndex playlistsRow = library.sourceRow("PlaylistFeature");
    QTest::mouseClick(sidebar.viewport(), Qt::LeftButton, {}, sidebar.visualRect(playlistsRow).center());
    settle();
    require(sidebar.rootIndex() == playlistsRow && sidebar.sourceCrumb() == "This Pi › Playlists",
            "a row with children drills in; the place is This Pi › Playlists");
    back->click();
    settle();
    require(!sidebar.rootIndex().isValid() && sidebar.isSourceMenuInside() &&
                    shownRows(sidebar) == QStringList({"Tracks", "Auto DJ", "Playlists"}),
            "BACK returns to This Pi's rows");
    back->click();
    settle();
    require(!sidebar.isSourceMenuInside() && edit->isVisible(), "BACK again returns to the top level");

    // A rekordbox drive comes: its row is first.
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
                    tileSub(sidebar, "MANTACORE") == QString::fromUtf8("USB · rekordbox") &&
                    tileGlyph(sidebar, "MANTACORE") == "usb" && tileEnterable(sidebar, "MANTACORE"),
            "with a drive the first row is the drive (USB · rekordbox, the USB icon, ›)");
    sidebar.sourceTiles().first()->click();
    settle();
    const QModelIndex driveRow = model.index(0, 0, library.sourceRow("RekordboxFeature"));
    require(shown == "Rekordbox/MANTACORE" && sidebar.rootIndex() == driveRow && sidebar.isSourceMenuInside(),
            "a tap on the drive opens it and goes inside");
    require(shownRows(sidebar) == QStringList({"Friday set", "Grime"}) &&
                    sidebar.sourceCrumb() == "MANTACORE" && sidebar.sourceTiles().first()->isChecked(),
            "its rows are the drive's node; the place names the drive; it is the current source");
    back->click();
    settle();
    require(!sidebar.isSourceMenuInside() && tileNames(sidebar).value(0) == "MANTACORE",
            "BACK at the drive goes to the top level, not up to all drives");
    sidebar.sourceTiles().first()->click();
    settle();
    screenControl.setAndConfirm(1);
    sidebarVisible.setAndConfirm(1);
    const QModelIndex friday = model.index(0, 0, driveRow);
    QTest::mouseClick(sidebar.viewport(), Qt::LeftButton, {}, sidebar.visualRect(friday).center());
    settle();
    require(shown == "Rekordbox/Friday set" && screenControl.get() == 0 && sidebarVisible.get() == 0,
            "a tap on a drive playlist opens it in Tracks and closes Sources");

    // A drive opened in Computer joins after it, in plug-in order.
    {
        std::vector<std::unique_ptr<TreeItem>> rows;
        rows.push_back(item(stick, stick));
        computer.children.insertTreeItemRows(std::move(rows), computer.children.rowCount());
    }
    settle();
    require(tileNames(sidebar).mid(0, 2) == QStringList({"MANTACORE", "STICK"}) && tileSub(sidebar, "STICK") == "USB",
            "a drive opened in Computer gets a row (USB), in plug-in order");

    // Unplug while the drive is selected.
    sidebar.sourceTiles().first()->click();
    settle();
    require(sidebar.selectedSourceTile() == QString("drive:" + QDir::cleanPath(mantacore)),
            "the drive is selected again");
    rekordbox.children.removeRows(0, 1);
    settle();
    bool valid = true;
    for (int tile = 0; tile < sidebar.sourceTiles().size(); ++tile) {
        valid &= !sidebar.sourceTiles().at(tile)->accessibleName().isEmpty();
    }
    require(sidebar.selectedSourceTile() == LibraryInterface::SourceGroups::kThisPi &&
                    tileNamed(sidebar, "This Pi")->isChecked() && !tileNamed(sidebar, "MANTACORE"),
            "unplugged while selected: This Pi is selected and the drive's row is gone");
    require(valid && !sidebar.rootIndex().isValid() && !sidebar.isSourceMenuInside() &&
                    sidebar.sourceCrumb() == "This Pi" && edit->isVisible() &&
                    shownRows(sidebar) == QStringList({"Tracks", "Auto DJ", "Playlists"}),
            "nothing dangles: the top level, This Pi current, its rows below");
    QDir(stick).removeRecursively();
    sidebar.sourcesChanged();
    settle();
    require(!tileNamed(sidebar, "STICK"), "a Computer drive whose folder is gone loses its row");

    // A node tile without children (Recordings) opens its own list.
    screenControl.setAndConfirm(1);
    tileNamed(sidebar, "Recordings")->click();
    settle();
    require(shown == "Recordings" && screenControl.get() == 0 && !sidebar.isSourceMenuInside(),
            "a tap on Recordings opens it and closes Sources; the menu stays at the top level");

    // EDIT: the full-screen edit list, listing the tiles.
    screenControl.setAndConfirm(1);
    sidebarVisible.setAndConfirm(1);
    QWidget tracksPane;
    library.m_pLibraryWidget = &tracksPane;
    edit->click();
    settle();
    auto* list = static_cast<LibraryInterface::SourceEditList*>(library.m_pSidebarSourceEdit.data());
    require(list && list->isVisible() && sidebar.isSourcesEditing() && editing.get() == 1,
            "EDIT opens the edit list and [Library],sidebar_sources_editing is 1");
    if (!list) {
        std::cout << "FAILED " << failures << std::endl;
        return 1;
    }
    require(list->parentWidget() == &screen && list->geometry() == QRect(0, 48, 800, 432),
            "the edit list is full screen under the top bar");
    auto rowNames = [&list] {
        QStringList names;
        for (auto* row : list->rows()) {
            names.append(row->findChild<QLabel*>("MixpiSourcesEditName")->text());
        }
        return names;
    };
    auto rowPart = [&list](const QString& id, const char* name) -> QWidget* {
        auto* row = list->row(id);
        return row ? row->findChild<QWidget*>(name) : nullptr;
    };
    auto rowSub = [&list](const QString& id) {
        auto* row = list->row(id);
        auto* sub = row ? row->findChild<QLabel*>("MixpiSourcesEditSub") : nullptr;
        return sub ? sub->text() : QStringLiteral("<none>");
    };
    namespace Groups = LibraryInterface::SourceGroups;
    const QStringList expected{"USB drives (each drive)", "This Pi", "Recordings", "History", "Folders",
            "Samples", "More"};
    if (rowNames() != expected) {
        std::cout << "OBSERVE edit rows " << rowNames().join(" | ").toStdString() << std::endl;
    }
    require(rowNames() == expected, "the edit list has one row per Sources row, in order (no member rows)");
    require(rowSub(Groups::kThisPi) == "TRACKS STARTS HERE" &&
                    static_cast<QPushButton*>(rowPart(Groups::kThisPi, "MixpiSourcesEditStar"))->text() ==
                            QString::fromUtf8("★") &&
                    rowSub(Groups::kMore) == "Analyse" && rowSub(Groups::kFolders) == "Browse files and drives" &&
                    rowSub(Groups::kHistory) == "Played tracks by date" && rowSub(Groups::kDrives) == "USB",
            "each row has its line; Tracks starts at This Pi (★, TRACKS STARTS HERE)");
    bool glyphs = true;
    for (const auto& id : {Groups::kDrives, Groups::kThisPi, Groups::kHistory, Groups::kFolders,
                 Groups::kSamples, Groups::kMore}) {
        auto* icon = static_cast<LibraryInterface::SourceGlyph*>(rowPart(id, "MixpiSourcesEditIcon"));
        glyphs &= icon && icon->glyph() == Groups::glyph(id) && !icon->glyph().isEmpty();
    }
    require(glyphs, "each row has the icon it has in the menu");
    require(list->row(Groups::kHistory)->property("off").toBool() &&
                    !list->row(Groups::kThisPi)->property("off").toBool(),
            "a row that is off (History) is dimmed");
    require(!static_cast<QPushButton*>(rowPart(Groups::kDrives, "MixpiSourcesEditUp"))->isEnabled() &&
                    static_cast<QPushButton*>(rowPart(Groups::kThisPi, "MixpiSourcesEditUp"))->isEnabled() &&
                    !static_cast<QPushButton*>(rowPart(Groups::kMore, "MixpiSourcesEditDown"))->isEnabled(),
            "UP is off on the first row and DOWN on the last");
    static_cast<QPushButton*>(rowPart(Groups::kRecordings, "MixpiSourcesEditDown"))->click();
    settle();
    require(library.sourceGroupOrder().mid(2, 2) == QStringList({"SetlogFeature", "RecordingFeature"}) &&
                    rowNames().indexOf("History") < rowNames().indexOf("Recordings"),
            "Down moves a row and saves the order");
    static_cast<QPushButton*>(rowPart(Groups::kThisPi, "MixpiSourcesEditDown"))->click();
    settle();
    require(rowNames().mid(1, 3) == QStringList({"History", "This Pi", "Recordings"}),
            "This Pi moves down past History");
    static_cast<QCheckBox*>(rowPart(Groups::kHistory, "MixpiSourcesEditSwitch"))->click();
    settle();
    require(settings.getValue(ConfigKey(kConfigGroup, "SidebarSourceSetlogFeature"), false) &&
                    !list->row(Groups::kHistory)->property("off").toBool(),
            "the History switch writes its source's own key and the row is no longer dimmed");
    static_cast<QCheckBox*>(rowPart(Groups::kDrives, "MixpiSourcesEditSwitch"))->click();
    settle();
    require(!settings.getValue(ConfigKey(kConfigGroup, "SourceGroupDrives"), true),
            "the drives switch writes the group's key");
    require(!static_cast<QPushButton*>(rowPart(Groups::kSamples, "MixpiSourcesEditStar"))->isEnabled() &&
                    !static_cast<QPushButton*>(rowPart(Groups::kDrives, "MixpiSourcesEditStar"))->isEnabled(),
            "★ is off where Tracks cannot start (Samples, drives)");
    static_cast<QPushButton*>(rowPart(Groups::kHistory, "MixpiSourcesEditStar"))->click();
    settle();
    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == "SetlogFeature" &&
                    rowSub(Groups::kHistory) == "TRACKS STARTS HERE" &&
                    rowSub(Groups::kThisPi) == QString::fromUtf8("Tracks · Playlists · Auto DJ"),
            "★ on History: Tracks starts at History");
    static_cast<QPushButton*>(rowPart(Groups::kThisPi, "MixpiSourcesEditStar"))->click();
    settle();
    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == "MixxxLibraryFeature",
            "★ on This Pi starts at Tracks");
    static_cast<QPushButton*>(rowPart(Groups::kMore, "MixpiSourcesEditStar"))->click();
    settle();
    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == "AnalysisFeature" &&
                    rowSub(Groups::kMore) == "TRACKS STARTS HERE",
            "★ on More starts at its first source that is on (Analyse)");
    static_cast<QPushButton*>(rowPart(Groups::kThisPi, "MixpiSourcesEditStar"))->click();
    settle();
    list->doneButton()->click();
    settle();
    require(!sidebar.isSourcesEditing() &&
                    tileNames(sidebar) == QStringList({"History", "This Pi", "Recordings", "Folders",
                                                "Samples", "More"}),
            "DONE: the menu shows the new order with History");
    require(editing.get() == 0 && !list->isVisible() && screenControl.get() == 1 && sidebarVisible.get() == 1,
            "DONE sets [Library],sidebar_sources_editing to 0 and Sources stays open");
    edit->click();
    settle();
    require(editing.get() == 1 && list->isVisible(), "EDIT again: the control is 1 again");
    // A model reset (USB hot-plug) while the list is open: the control
    // follows what is shown.
    recordings.children.setRootItem(TreeItem::newRoot(&recordings));
    settle();
    require(editing.get() == (sidebar.isSourcesEditing() && list->isVisible() ? 1 : 0),
            "after a model reset the control matches the shown edit list");
    list->closeButton()->click();
    settle();
    require(editing.get() == 0 && !list->isVisible() && screenControl.get() == 0 && sidebarVisible.get() == 0,
            "the close ✕ ends the edit list and closes Sources");
    edit->click();
    settle();
    sidebar.hide();
    settle();
    require(editing.get() == 0 && !sidebar.isSourcesEditing() && !list->isVisible(),
            "closing Sources (the sidebar hides) ends the edit list");
    sidebar.show();
    settle();
    require(editing.get() == 0 && !list->isVisible(), "Sources opens again on the menu, not the edit list");
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceCrateFeature"), true);
    library.applySidebarSourceVisibility();
    settle();
    tileNamed(sidebar, "This Pi")->click();
    settle();
    require(shownRows(sidebar) == QStringList({"Tracks", "Auto DJ", "Playlists", "Crates"}),
            "a source switched on inside This Pi shows there");
    back->click();
    settle();
    {
        std::vector<std::unique_ptr<TreeItem>> rows;
        auto again = item("MANTACORE", QVariantList{mantacore, QString(), QStringLiteral("rev-2")});
        again->appendChild("Tracks", 21);
        again->appendChild("Playlists", 22)->appendChild("Afro house", 23);
        for (const char* name : {"Warm-up", "Peak time", "Closing", "Afro tech"}) {
            again->appendChild(QString::fromLatin1(name), 24);
        }
        again->appendChild("History", 25)->appendChild("2026-11-15", 26);
        rows.push_back(std::move(again));
        rekordbox.children.insertTreeItemRows(std::move(rows), 0);
    }
    settle();
    require(!tileNamed(sidebar, "MANTACORE"), "with the drives switch off, a drive gets no row");

    // The renders (agreed UI s5): the state of m-sources-top.png, a list with
    // counts and a scroll bar, and m-sources-edit.png.
    const QString grabs = qEnvironmentVariable("MIXPI_SOURCES_GRAB_DIR");
    {
        settings.setValue(ConfigKey(kConfigGroup, "SourceGroupDrives"), true);
        settings.setValue(ConfigKey(kConfigGroup, "SourceGroupOrder"),
                SourceOrder::encode({Groups::kThisPi, Groups::kDrives, Groups::kHistory, Groups::kFolders,
                        Groups::kSamples, Groups::kMore, Groups::kRecordings}));
        settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceRecordingFeature"), false);
        for (const auto& id : {"AutoDJFeature", "PlaylistFeature", "CrateFeature"}) {
            settings.setValue(ConfigKey(kConfigGroup, QStringLiteral("SidebarSource") + id), false);
        }
        settings.setValue(ConfigKey(kConfigGroup, "SidebarDefaultSource"), "MixxxLibraryFeature");
        // Mixxx labels a playlist "name (count) duration".
        auto* lists = playlists.children.getRootItem();
        const QList<QPair<QString, int>> named{{"Afro house", 48}, {"Warm-up", 31}, {"Peak time", 26},
                {"Closing", 22}, {"Afro tech", 40}, {"Deep cuts", 17}, {"Amapiano", 35}, {"Edits", 12}};
        for (const auto& [name, count] : named) {
            lists->appendChild(QStringLiteral("%1 (%2) 2:%3:00").arg(name).arg(count).arg(count % 60, 2, 10,
                                                                                         QLatin1Char('0')),
                    count);
        }
        library.applySidebarSourceVisibility();
        sidebar.sourcesChanged();
        settle();
        tileNamed(sidebar, "This Pi")->click();
        settle();
        back->click();
        settle();
        require(tileNames(sidebar) == QStringList({"This Pi", "MANTACORE", "History", "Folders", "Samples", "More"}) &&
                        tileSub(sidebar, "This Pi") == "Tracks" && !sidebar.isSourceMenuInside(),
                "the render state matches m-sources-top.png (This Pi, MANTACORE, History, Folders, Samples, More)");
        if (!grabs.isEmpty()) {
            screen.grab().save(grabs + "/c1-sources-top.png");
        }
        // Inside a source with a long list: This Pi › Playlists.
        settings.setValue(ConfigKey(kConfigGroup, "SidebarSourcePlaylistFeature"), true);
        library.applySidebarSourceVisibility();
        settle();
        tileNamed(sidebar, "This Pi")->click();
        settle();
        const QModelIndex lists2 = library.sourceRow("PlaylistFeature");
        QTest::mouseClick(sidebar.viewport(), Qt::LeftButton, {}, sidebar.visualRect(lists2).center());
        settle();
        const QModelIndex afro = model.index(2, 0, lists2);
        sidebar.selectionModel()->setCurrentIndex(afro, QItemSelectionModel::ClearAndSelect);
        settle();
        auto* scroll = sidebar.verticalScrollBar();
        require(sidebar.rootIndex() == lists2 && scroll->isVisible() && scroll->maximum() > 0 &&
                        scroll->width() == 24 && place->text() == QString::fromUtf8("This Pi › Playlists"),
                "inside a long list: the place, and the 24 px scroll bar at the right edge");
        if (!grabs.isEmpty()) {
            screen.grab().save(grabs + "/c1-sources-sub.png");
        }
        // Inside the drive (rekordbox lists carry no count in Mixxx).
        back->click();
        back->click();
        settle();
        if (auto* mantacoreTile = tileNamed(sidebar, "MANTACORE")) {
            mantacoreTile->click();
            settle();
            if (!grabs.isEmpty()) {
                screen.grab().save(grabs + "/c1-sources-drive.png");
            }
            back->click();
            settle();
        }
        // The edit list in the state of m-sources-edit.png (Folders off).
        settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceBrowseFeature"), false);
        settings.setValue(ConfigKey(kConfigGroup, "SidebarSourcePlaylistFeature"), false);
        library.applySidebarSourceVisibility();
        settle();
        edit->click();
        settle();
        require(list->isVisible() &&
                        rowNames().mid(0, 6) == QStringList({"This Pi", "MANTACORE", "History", "Folders",
                                                        "Samples", "More"}) &&
                        rowSub(Groups::kDrives) == QString::fromUtf8("USB · rekordbox") &&
                        list->row(Groups::kFolders)->property("off").toBool(),
                "the edit render state matches m-sources-edit.png (MANTACORE by name, Folders off)");
        if (!grabs.isEmpty()) {
            screen.grab().save(grabs + "/c1-sources-edit.png");
        }
        list->doneButton()->click();
        settle();
    }

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

    // A narrow sidebar (the Pioneered touch skin's 260 px pane) keeps one row
    // per source and no filter.
    sidebar.setGeometry(540, 100, 260, 380);
    settle();
    bool none = true;
    for (int row = 0; row < model.rowCount(); ++row) {
        none &= sidebar.isRowHidden(row, {}) == sidebar.isSourceRowHidden(row);
    }
    require(!sidebar.hasSourceScreen() && !library.groupedSources() && none,
            "a narrow touch sidebar has no grouped rows and hides only the owner's hidden sources");

    std::cout << (failures ? "FAILED " : "OK ") << failures << std::endl;
    return failures ? 1 : 0;
}
