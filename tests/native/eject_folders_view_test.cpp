// Spec 2e, as 2g applies it (build J, wave J10; owner: "Let just land on the
// top menu instead"): a drive's folder shown through Folders (Removable
// Devices, a Quick Link or /), then the drive ejected from the Media page or
// pulled out: the table shows none of its rows, and the Sources menu lands on
// its top level with nothing current, as J4 does for a rekordbox drive.
//
// The real WLibrarySidebar as the 320x380 menu with the real SidebarModel,
// wired as in source_groups_test.cpp, and the actual Library methods
// (sourceGroupTiles, noteBrowsePlaceShown, releaseGoneFolder, ...). From the
// patched browsefeature.cpp: the actual BrowseFeature::activateChild,
// refreshMediaLifecycle, pruneRemovableDirectories, releaseGoneFolder and the
// mount table helpers (their table pointed at the fixture's file); from
// browsetablemodel.h the actual BrowseTableModel::releasePath; from
// mixpimedia.h the actual MixpiMedia::tick (a drive pulled out: the mount
// table changes) and ejectFinished (a clean eject), with the mount table
// they read pointed at the fixture's file. Stand-ins: the other features,
// the folder table (it lists a folder's .mp3 files, as BrowseThread does, and
// skips an empty path before it clears the rows, as BrowseThread does), the
// settings and the controls. An eject runs as the Media page runs it:
// releaseViews (refreshMediaLifecycle, pruneRemovableDirectories), the
// unmount (the drive's line leaves the mount table), then ejectFinished.
// tests/native/eject_folders_view_runner.py builds this; BASELINE is the
// source without mixxx-eject-folders-view.patch.
#include <QApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonObject>
#include <QLabel>
#include <QPointer>
#include <QPushButton>
#include <QSet>
#include <QSettings>
#include <QStandardItemModel>
#include <QTemporaryDir>
#include <QTest>
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
// Mixxx's own platform define (CMake sets it on Linux).
#ifndef __LINUX__
#define __LINUX__ 1
#endif

int failures = 0;
void require(bool condition, const char* name) {
    std::cout << (condition ? "PASS " : "FAIL ") << name << std::endl;
    failures += !condition;
}

// The mount table the production code reads (/proc/self/mountinfo there).
QString kFixtureMountTable;

LibraryFeature::LibraryFeature(QString name)
        : identity(std::move(name)) {
    children.setRootItem(TreeItem::newRoot(this));
}

namespace mixxx {
// FileInfo and FileAccess as BrowseFeature::activateChild uses them.
class FileInfo {
  public:
    FileInfo() = default;
    explicit FileInfo(const QString& path)
            : m_path(path) {
    }
    bool hasLocation() const {
        return !m_path.isEmpty();
    }
    bool isDir() const {
        return QFileInfo(m_path).isDir();
    }
    QString location() const {
        return QFileInfo(m_path).absoluteFilePath();
    }

  private:
    QString m_path;
};
class FileAccess {
  public:
    FileAccess() = default;
    explicit FileAccess(FileInfo info)
            : m_info(std::move(info)) {
    }
    const FileInfo& info() const {
        return m_info;
    }
    bool isReadable() const {
        return m_info.isDir();
    }

  private:
    FileInfo m_info;
};
} // namespace mixxx
struct Sandbox {
    static bool askForAccess(mixxx::FileInfo*) {
        return false;
    }
};

// The folder table: BrowseTableModel over BrowseThread. A folder's .mp3
// files replace the rows; an empty path is skipped before the rows are
// cleared (BrowseThread::populateModel returns first).
class BrowseTableModel : public QStandardItemModel {
  public:
    QString m_currentDirectory;
    void setPath(mixxx::FileAccess path) {
        if (path.info().hasLocation() && path.info().isDir()) {
            m_currentDirectory = path.info().location();
            removeRows(0, rowCount());
            const QStringList files = QDir(m_currentDirectory).entryList({"*.mp3"}, QDir::Files, QDir::Name);
            for (const auto& file : files) {
                appendRow(new QStandardItem(file));
            }
        } else {
            m_currentDirectory = {};
        }
    }
    QStringList shown() const {
        QStringList rows;
        for (int row = 0; row < rowCount(); ++row) {
            rows.append(item(row)->text());
        }
        return rows;
    }
#ifndef BASELINE
#include "browse_release.inc"
#endif
};

// FolderTreeModel as BrowseFeature uses it: the feature's tree.
struct FolderTreeModel {
    TreeItemModel* model;
    TreeItem* getRootItem() const {
        return model->getRootItem();
    }
    QModelIndex index(int row, int column, const QModelIndex& parent = {}) const {
        return model->index(row, column, parent);
    }
    int rowCount(const QModelIndex& parent = {}) const {
        return model->rowCount(parent);
    }
    QVariant data(const QModelIndex& index, int role) const {
        return model->data(index, role);
    }
    bool removeRows(int row, int count, const QModelIndex& parent = {}) {
        return model->removeRows(row, count, parent);
    }
    void deferDirectoryProbes() {
    }
    void triggerRepaint(const QModelIndex& = {}) {
    }
};

// Computer (BrowseFeature) in the sidebar: the stand-in feature's tree, with
// the actual BrowseFeature methods.
class BrowseFeature : public LibraryFeature {
  public:
    explicit BrowseFeature(const QString& name)
            : LibraryFeature(name) {
    }
    BrowseTableModel m_browseModel;
    int m_proxyModel = 0;
    FolderTreeModel m_folders{&children};
    FolderTreeModel* m_pSidebarModel = &m_folders;
    QStringList m_removableDirectories;
    QString m_shownFolder;
    QString m_shownMount;
    // J11 (mixxx-removable-rows-fix.patch): the mount points last seen.
    QStringList m_seenMounts;
    // Library::slotShowTrackModel / slotSwitchToView.
    std::function<void()> trackModelShown;
    void saveModelState() {
    }
    void showTrackModel(int*) {
        if (trackModelShown) {
            trackModelShown();
        }
    }
    void disableSearch() {
    }
    void enableCoverArtDisplay(bool) {
    }
    void activateChild(const QModelIndex& index);
    void refreshMediaLifecycle();
    void pruneRemovableDirectories();
#ifndef BASELINE
    QString releaseGoneFolder();
#endif
};

#include "browse_production.inc"

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
    struct SampleBrowser {
        void shown(const LibraryInterface::BrowsePlace&) {
        }
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
    BrowseFeature* m_pBrowseFeature = nullptr;
    std::unique_ptr<SampleBrowser> m_pSampleBrowser;
    std::unique_ptr<LibraryInterface::BrowsePlace> m_pShownPlace =
            std::make_unique<LibraryInterface::BrowsePlace>();

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
    void noteBrowsePlaceShown();
#ifndef BASELINE
    void releaseGoneFolder();
#endif
};

#include "library_sample_methods.h"

// The Media page's owner (MixpiMedia): the actual tick and ejectFinished.
class MixpiMedia {
  public:
    struct Page {
        void hideSheet() {
        }
        void setEjectFailed(const QString&) {
        }
    };
    struct Strip {
        void driveGone(const QString&) {
        }
        void showSafe(const QString&, const QString&) {
        }
    };
    struct Handover {
        void ejected(const QStringList&) {
        }
    };
    std::function<void()> mountsChanged;
    QByteArray m_mounts;
    QString m_ejectingIdentity;
    QStringList m_ejectPaths;
    QString m_ejectSysfs;
    QString m_ejectDiskseq;
    QString m_ejectName;
    QStringList m_ejectUsers;
    QString m_safeIdentity;
    QString m_safeName;
    QString m_safeSysfs;
    QString m_safeDiskseq;
    QJsonObject m_snapshot;
    QSet<QString> m_present;
    std::unique_ptr<QSet<QString>> m_opened = std::make_unique<QSet<QString>>();
    std::unique_ptr<Handover> m_handover = std::make_unique<Handover>();
    Page* m_page = nullptr;
    std::unique_ptr<Strip> m_strip = std::make_unique<Strip>();
    int observations = 0;
    void observeNow() {
        ++observations;
    }
    void refresh() {
    }
    bool ensureWidgets() {
        return true;
    }
    static bool driveGone(const QString&, const QString&) {
        return false;
    }
#include "media_production.inc"
};

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

QByteArray treeDigest(const QString& path) {
    QCryptographicHash hash(QCryptographicHash::Sha256);
    QDirIterator files(path, QDir::Files | QDir::Hidden | QDir::System, QDirIterator::Subdirectories);
    QStringList names;
    while (files.hasNext()) {
        names.append(files.next());
    }
    names.sort();
    for (const auto& name : names) {
        QFile file(name);
        file.open(QIODevice::ReadOnly);
        hash.addData(name.toUtf8());
        hash.addData(QByteArray::number(QFileInfo(name).lastModified().toMSecsSinceEpoch()));
        hash.addData(file.readAll());
    }
    return hash.result();
}

void touch(const QString& path) {
    QDir().mkpath(QFileInfo(path).path());
    QFile file(path);
    file.open(QIODevice::WriteOnly);
    file.write("mp3");
}

// A mountinfo line (the mount point is the fifth field, a space as \040).
QByteArray mountLine(int id, const QString& point, const QString& source) {
    QByteArray escaped = QFile::encodeName(point);
    escaped.replace(" ", "\\040");
    return QByteArray::number(id) + " 1 8:" + QByteArray::number(id) + " / " + escaped +
            " rw,nosuid,nodev,relatime shared:" + QByteArray::number(id) + " - vfat " +
            source.toUtf8() + " rw\n";
}

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    QTemporaryDir home;
    Settings settings(QDir(home.path()).filePath("mixxx.cfg"));
    const QString user = QDir(home.path()).filePath("media/pi");
    const QString gander = user + "/GANDER1";
    const QString mantacore = user + "/MANTACORE";
    const QString stick = user + "/DJ STICK";
    const QString samples = QDir(home.path()).filePath("Music/Samples");
    const QString album = gander + "/Contents/21 Savage Metro Boomin Drake/SAVAGE MODE II";
    touch(album + "/43 - Mr. Right Now.mp3");
    touch(mantacore + "/Contents/Afro/01 - Afro One.mp3");
    touch(stick + "/Edits/07 - Edit Seven.mp3");
    touch(samples + "/kick.mp3");
    const QByteArray ganderBefore = treeDigest(gander);
    const QByteArray mantacoreBefore = treeDigest(mantacore);
    const QByteArray stickBefore = treeDigest(stick);
    kFixtureMountTable = QDir(home.path()).filePath("mountinfo");
    // The mount table: / (the Pi), and the mounted drives.
    QStringList mounted;
    auto writeMounts = [&] {
        QFile table(kFixtureMountTable);
        table.open(QIODevice::WriteOnly | QIODevice::Truncate);
        table.write(mountLine(21, "/", "/dev/mmcblk0p2"));
        int id = 40;
        for (const auto& point : std::as_const(mounted)) {
            ++id;
            table.write(mountLine(id, point, QStringLiteral("/dev/sd%1").arg(id)));
        }
    };
    mounted = {gander, mantacore, stick};
    writeMounts();
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceCrateFeature"), false);
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceSetlogFeature"), false);
    settings.setValue(ConfigKey(kConfigGroup, "SidebarSourceSeratoFeature"), false);
    settings.setValue(ConfigKey(kConfigGroup, "SidebarDefaultSource"), "MixxxLibraryFeature");
    const QString savedStart = settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource"));

    SidebarModel model;
    Library library(&settings, &model);
    library.m_samplesPath = samples;
    LibraryFeature tracks("Tracks");
    LibraryFeature playlists("Playlists");
    LibraryFeature crates("Crates");
    LibraryFeature autodj("Auto DJ");
    BrowseFeature computer("Computer");
    LibraryFeature recordings("Recordings");
    LibraryFeature history("History");
    LibraryFeature analyse("Analyse");
    LibraryFeature rekordbox("Rekordbox");
    LibraryFeature serato("Serato");
    library.m_pBrowseFeature = &computer;
    playlists.children.getRootItem()->appendChild("Warm up", 1);
    // Computer's rows as BrowseFeature makes them, with the folders read
    // (onLazyChildExpandation): Removable Devices lists the drives, / goes
    // down to them, a Quick Link names a folder on GANDER1.
    auto folder = [](TreeItem* parent, const QString& path) {
        return parent->appendChild(QFileInfo(path).fileName(), QVariant(path + "/"));
    };
    // A drive's row under Removable Devices (createRemovableDevices), with
    // its folders read.
    auto deviceRow = [&](const QString& drive) {
        auto row = std::make_unique<TreeItem>(QFileInfo(drive).fileName(), QVariant(drive + "/"));
        if (drive == gander) {
            folder(folder(folder(row.get(), gander + "/Contents"),
                           gander + "/Contents/21 Savage Metro Boomin Drake"),
                    album);
        } else if (drive == mantacore) {
            folder(folder(row.get(), mantacore + "/Contents"), mantacore + "/Contents/Afro");
        } else {
            folder(row.get(), stick + "/Edits");
        }
        return row;
    };
    {
        auto* root = computer.children.getRootItem();
        TreeItem* links = root->appendChild("Quick Links", QUICK_LINK_NODE);
        links->appendChild("SAVAGE MODE II", QVariant(album + "/"));
        TreeItem* devices = root->appendChild("Removable Devices", DEVICE_NODE);
        std::vector<std::unique_ptr<TreeItem>> rows;
        for (const auto& drive : {gander, mantacore, stick}) {
            rows.push_back(deviceRow(drive));
        }
        devices->insertChildren(0, std::move(rows));
        root->appendChild("/", "/");
        root->appendChild("Samples", QString(samples + "/"));
    }
    // / read down to DJ STICK (onLazyChildExpandation when it is opened).
    auto readSlash = [&] {
        const QModelIndex slash = computer.children.index(2, 0);
        computer.children.removeRows(0, computer.children.rowCount(slash), slash);
        auto media = std::make_unique<TreeItem>("media", QVariant(QDir(home.path()).filePath("media") + "/"));
        folder(folder(folder(media.get(), user), stick), stick + "/Edits");
        std::vector<std::unique_ptr<TreeItem>> rows;
        rows.push_back(std::move(media));
        computer.children.insertTreeItemRows(std::move(rows), 0, slash);
    };
    readSlash();
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

    QWidget screen;
    screen.resize(800, 480);
    QWidget wrapper(&screen);
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
    // Library::slotShowTrackModel (and slotSwitchToView): a list is in
    // Tracks now; its place is the current row.
    auto trackModelShown = [&] {
        sidebar.noteSourceShown();
        library.noteBrowsePlaceShown();
    };
    computer.trackModelShown = trackModelShown;
    // SidebarModel::clicked activates the feature's row: Computer's rows
    // through the actual BrowseFeature::activateChild.
    auto featureIndex = [&](const QModelIndex& index) {
        QList<int> rows;
        for (QModelIndex step = index; step.parent().isValid(); step = step.parent()) {
            rows.prepend(step.row());
        }
        QModelIndex found;
        for (int row : rows) {
            found = computer.children.index(row, 0, found);
        }
        return found;
    };
    LibraryFeature::shown = [&](const QString& list) {
        if (list.startsWith("Computer/")) {
            computer.activateChild(featureIndex(sidebar.currentIndex()));
        } else {
            trackModelShown();
        }
    };
    library.m_pSidebarWidget = &sidebar;
    {
        Library* self = &library;
        WLibrarySidebar* pSidebarWidget = &sidebar;
#include "grouped_binding.inc"
    }
    QObject::connect(&model, &QAbstractItemModel::modelReset, &sidebar,
            [&library] { library.applySidebarSourceVisibility(); });
    ControlObject screenControl(ConfigKey("[MixPi]", "screen"));
    ControlObject sidebarVisible(ConfigKey("[Sidebar]", "sidebar_visible"));
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

    // The Media page's owner, wired as Library wires it.
    MixpiMedia media;
#ifndef BASELINE
    media.mountsChanged = [&library] {
        library.releaseGoneFolder();
    };
#endif
    media.tick(); // the first look at the mount table

    auto closeMenu = [&] {
        sidebar.hide();
        screenControl.setAndConfirm(0);
        sidebarVisible.setAndConfirm(0);
        settle();
    };
    auto openMenu = [&] {
        screenControl.setAndConfirm(1);
        sidebarVisible.setAndConfirm(1);
        sidebar.show();
        settle();
    };
    auto toTop = [&] {
        while (sidebar.isSourceMenuInside()) {
            back->click();
            settle();
        }
    };
    auto edges = [&] {
        int count = 0;
        for (auto* tile : sidebar.sourceTiles()) {
            count += tile->isChecked() ? 1 : 0;
        }
        return count;
    };
    auto rowNamed = [&](const QString& name) {
        for (int row = 0; row < model.rowCount(sidebar.rootIndex()); ++row) {
            const QModelIndex index = model.index(row, 0, sidebar.rootIndex());
            if (index.data().toString() == name && !sidebar.isRowHidden(row, sidebar.rootIndex())) {
                return index;
            }
        }
        return QModelIndex();
    };
    // Taps along a path in Folders, from the top level: the last row is a
    // folder of tracks (no folders below it), so the tap shows it in Tracks
    // and closes Sources.
    auto openFolders = [&](const QStringList& steps) {
        openMenu();
        toTop();
        tileNamed(sidebar, "Folders")->click();
        settle();
        for (const auto& step : steps) {
            const QModelIndex row = rowNamed(step);
            if (!row.isValid()) {
                std::cout << "OBSERVE no row " << step.toStdString() << std::endl;
                return false;
            }
            QTest::mouseClick(sidebar.viewport(), Qt::LeftButton, {}, sidebar.visualRect(row).center());
            settle();
        }
        closeMenu();
        return true;
    };
    auto topWithoutEdge = [&] {
        openMenu();
        const bool top = !sidebar.isSourceMenuInside() && edit->isVisible() && !place->isVisible();
        const bool none = edges() == 0 && !sidebar.currentIndex().isValid();
        std::cout << "OBSERVE top " << !sidebar.isSourceMenuInside() << " place '"
                  << sidebar.sourceCrumb().toStdString() << "' edges " << edges() << " current '"
                  << sidebar.currentIndex().data().toString().toStdString() << "'" << std::endl;
        closeMenu();
        return top && none;
    };
    auto table = [&] {
        return computer.m_browseModel.shown();
    };
    auto anyFrom = [&](const QString& drive) {
        // A row of the table read from DRIVE's folder (the table's folder).
        return !table().isEmpty() && computer.m_browseModel.m_currentDirectory.startsWith(drive + "/");
    };
    auto devices = [&] {
        QStringList names;
        const TreeItem* pDevices = computer.children.getRootItem()->child(1);
        for (int row = 0; row < pDevices->childRows(); ++row) {
            names.append(pDevices->child(row)->getLabel());
        }
        return names;
    };
    // The Media page's eject: its views released (releaseViews:
    // refreshMediaLifecycle, pruneRemovableDirectories), the unmount (the
    // drive leaves the mount table), then ejectFinished.
    auto eject = [&](const QString& drive) {
        computer.refreshMediaLifecycle();
        computer.pruneRemovableDirectories();
        settle();
        mounted.removeAll(drive);
        writeMounts();
        media.m_ejectingIdentity = "usb-" + QFileInfo(drive).fileName();
        media.m_ejectPaths = {drive};
        media.m_ejectName = QFileInfo(drive).fileName();
        media.ejectFinished(true, {});
        settle();
    };
    // Pulled out, the Media page closed: the mount table changes, and the
    // next tick sees it.
    auto pull = [&](const QString& drive) {
        mounted.removeAll(drive);
        writeMounts();
        media.tick();
        settle();
    };
    auto plugBack = [&](const QString& drive) {
        mounted.append(drive);
        writeMounts();
        media.tick();
        // Removable Devices read again when it is opened
        // (onLazyChildExpandation): the mounted drives.
        const QModelIndex devices = computer.children.index(1, 0);
        computer.children.removeRows(0, computer.children.rowCount(devices), devices);
        std::vector<std::unique_ptr<TreeItem>> rows;
        for (const auto& path : {gander, mantacore, stick}) {
            if (mounted.contains(path)) {
                rows.push_back(deviceRow(path));
            }
        }
        computer.children.insertTreeItemRows(std::move(rows), 0, devices);
        settle();
    };
    closeMenu();

    // 1. The card's steps (acceptance J, 201-203): Folders › Removable
    // Devices › GANDER1 › Contents › 21 Savage Metro Boomin Drake › SAVAGE
    // MODE II, then GANDER1 ejected from the Media page.
    require(openFolders({"Removable Devices", "GANDER1", "Contents", "21 Savage Metro Boomin Drake",
                    "SAVAGE MODE II"}) &&
                    table() == QStringList({"43 - Mr. Right Now.mp3"}),
            "GANDER1's SAVAGE MODE II is in the table through Folders › Removable Devices");
    eject(gander);
    require(table().isEmpty() && !anyFrom(gander),
            "J10 eject with GANDER1's folder in Tracks (Removable Devices): the table has 0 rows");
    require(topWithoutEdge(),
            "J10 eject (Removable Devices): ☰ opens at the top level, no row has the edge, nothing current");
    require(!devices().contains("GANDER1"), "after the eject, Removable Devices does not list GANDER1");

    // 2. A Quick Link to the same folder, then GANDER1 pulled out (the Media
    // page closed).
    plugBack(gander);
    require(openFolders({"Quick Links", "SAVAGE MODE II"}) && table() == QStringList({"43 - Mr. Right Now.mp3"}),
            "GANDER1's folder is in the table through a Quick Link");
    pull(gander);
    require(table().isEmpty() && !anyFrom(gander),
            "J10 pulled out with GANDER1's folder in Tracks (Quick Link): the table has 0 rows");
    require(topWithoutEdge(), "J10 pulled out (Quick Link): ☰ opens at the top level, no edge, nothing current");
    require(!devices().contains("GANDER1") && devices().contains("MANTACORE") && devices().contains("DJ STICK"),
            "after the pull, Removable Devices drops GANDER1 and keeps the drives still in");

    // 3. Through / to DJ STICK (a space in its mount point), then pulled out.
    readSlash();
    settle();
    require(openFolders({"/", "media", "pi", "DJ STICK", "Edits"}) && table() == QStringList({"07 - Edit Seven.mp3"}),
            "DJ STICK's Edits is in the table through /");
    pull(stick);
    require(table().isEmpty(), "J10 pulled out with DJ STICK's folder in Tracks (/): the table has 0 rows");
    require(topWithoutEdge(), "J10 pulled out (/): ☰ opens at the top level, no edge, nothing current");

    // 4. Another drive goes: nothing changes.
    plugBack(gander);
    plugBack(stick);
    require(openFolders({"Removable Devices", "GANDER1", "Contents", "21 Savage Metro Boomin Drake",
                    "SAVAGE MODE II"}) &&
                    table() == QStringList({"43 - Mr. Right Now.mp3"}),
            "GANDER1's SAVAGE MODE II is in the table again");
    const QPersistentModelIndex savage = sidebar.currentIndex();
    pull(mantacore);
    openMenu();
    require(table() == QStringList({"43 - Mr. Right Now.mp3"}) && savage.isValid() &&
                    sidebar.currentIndex() == QModelIndex(savage) && sidebar.isSourceMenuInside() &&
                    sidebar.sourceCrumb().endsWith(QString::fromUtf8("21 Savage Metro Boomin Drake")),
            "J10: pulling out another drive (MANTACORE) leaves the table and the menu alone");
    closeMenu();
    plugBack(mantacore);
    require(openFolders({"Removable Devices", "MANTACORE", "Contents", "Afro"}) &&
                    table() == QStringList({"01 - Afro One.mp3"}),
            "MANTACORE's Afro is in the table");
    eject(gander);
    require(table() == QStringList({"01 - Afro One.mp3"}),
            "J10: ejecting another drive (GANDER1) leaves the table alone");

    // 5. A folder of the Pi in Tracks: an eject changes nothing.
    plugBack(gander);
    require(openFolders({"Samples"}) && table() == QStringList({"kick.mp3"}), "the Pi's Samples folder is in the table");
    eject(gander);
    require(table() == QStringList({"kick.mp3"}), "J10: with a folder of the Pi in Tracks an eject leaves the table alone");

    // 6. A list of This Pi in Tracks after a drive's folder: an eject leaves
    // the menu where it is.
    plugBack(gander);
    require(openFolders({"Removable Devices", "GANDER1", "Contents", "21 Savage Metro Boomin Drake",
                    "SAVAGE MODE II"}),
            "GANDER1's folder in Tracks, then This Pi");
    openMenu();
    toTop();
    tileNamed(sidebar, "This Pi")->click();
    settle();
    const QModelIndex thisPiTracks = library.sourceRow("MixxxLibraryFeature");
    QTest::mouseClick(sidebar.viewport(), Qt::LeftButton, {}, sidebar.visualRect(thisPiTracks).center());
    settle();
    closeMenu();
    eject(gander);
    openMenu();
    require(sidebar.isSourceMenuInside() && sidebar.sourceCrumb() == "This Pi" &&
                    sidebar.currentIndex() == library.sourceRow("MixxxLibraryFeature"),
            "J10: with This Pi's list in Tracks an eject leaves the menu inside This Pi on TRACKS");
    toTop();
    require(tileNamed(sidebar, "This Pi")->isChecked() && edges() == 1,
            "J10: with This Pi's list in Tracks the edge stays on This Pi");
    closeMenu();

    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == savedStart,
            "J10 does not change the saved start (★)");
    require(treeDigest(gander) == ganderBefore && treeDigest(mantacore) == mantacoreBefore &&
                    treeDigest(stick) == stickBefore,
            "nothing on the drives was written");
    std::cout << "OK " << failures << std::endl;
    return failures ? 1 : 0;
}
