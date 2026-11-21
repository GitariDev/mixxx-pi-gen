// Council round 6 (Fable), confirmed on the card (acceptance K,
// 70-now.png): J10's Removable Devices pruning (BrowseFeature::
// releaseGoneFolder, mixxx-eject-folders-view.patch) dropped every row whose
// path was not a mount point, on any change of the mount table, so the card's
// /media/SD-Backup (a plain folder of the Pi's own card) left the list when a
// drive was plugged in, pulled out or ejected. Build B and stock Mixxx list
// it. mixxx-removable-rows-fix.patch drops only a row that was a drive's
// mount point when the mount table was last read and is not one now.
//
// As tests/native/eject_folders_view_test.cpp: the real WLibrarySidebar as
// the 320x380 menu with the real SidebarModel, the actual Library methods
// (sourceGroupTiles, noteBrowsePlaceShown, releaseGoneFolder, ...), from the
// patched browsefeature.cpp the actual BrowseFeature::activateChild,
// refreshMediaLifecycle, pruneRemovableDirectories, releaseGoneFolder and
// the mount table helpers, from browsetablemodel.h the actual
// BrowseTableModel::releasePath, and from mixpimedia.h the actual
// MixpiMedia::tick and ejectFinished, with the mount table pointed at the
// fixture's file. Stand-ins: the other features, the folder table, the
// settings and the controls; Removable Devices is read (as
// createRemovableDevices reads /media, then /media/pi) when it is opened.
// tests/native/removable_rows_fix_runner.py builds this; --baseline is the
// source without mixxx-removable-rows-fix.patch (J10 kept).
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
#include "browse_release.inc"
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
    QString releaseGoneFolder();
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
    void releaseGoneFolder();
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
    // The card's /media: SD-Backup, a plain folder of the Pi's own card (not
    // a mount point), and the drives mounted below /media/pi.
    const QString backup = QDir(home.path()).filePath("media/SD-Backup");
    const QString user = QDir(home.path()).filePath("media/pi");
    const QString gander = user + "/GANDER1";
    const QString ixian = user + "/IXIAN";
    const QString samples = QDir(home.path()).filePath("Music/Samples");
    const QString album = gander + "/Contents/21 Savage Metro Boomin Drake/SAVAGE MODE II";
    touch(album + "/43 - Mr. Right Now.mp3");
    touch(ixian + "/Contents/House/02 - House Two.mp3");
    touch(backup + "/backup.mp3");
    touch(samples + "/kick.mp3");
    const QByteArray ganderBefore = treeDigest(gander);
    const QByteArray ixianBefore = treeDigest(ixian);
    const QByteArray backupBefore = treeDigest(backup);
    kFixtureMountTable = QDir(home.path()).filePath("mountinfo");
    // The mount table: / (the Pi; SD-Backup lies in it), and the drives.
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
    mounted = {gander, ixian};
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
    // A row under Removable Devices (createRemovableDevices), with its
    // folders read.
    auto deviceRow = [&](const QString& path) {
        auto row = std::make_unique<TreeItem>(QFileInfo(path).fileName(), QVariant(path + "/"));
        if (path == gander) {
            folder(folder(folder(row.get(), gander + "/Contents"),
                           gander + "/Contents/21 Savage Metro Boomin Drake"),
                    album);
        } else if (path == ixian) {
            folder(folder(row.get(), ixian + "/Contents"), ixian + "/Contents/House");
        }
        return row;
    };
    // Removable Devices read (onLazyChildExpandation, when it is opened):
    // the folders in /media, then in /media/pi (createRemovableDevices), so
    // SD-Backup and the drives mounted now.
    auto readDevices = [&] {
        const QModelIndex devices = computer.children.index(1, 0);
        computer.children.removeRows(0, computer.children.rowCount(devices), devices);
        std::vector<std::unique_ptr<TreeItem>> rows;
        rows.push_back(deviceRow(backup));
        for (const auto& path : {gander, ixian}) {
            if (mounted.contains(path)) {
                rows.push_back(deviceRow(path));
            }
        }
        computer.children.insertTreeItemRows(std::move(rows), 0, devices);
    };
    {
        auto* root = computer.children.getRootItem();
        root->appendChild("Quick Links", QUICK_LINK_NODE);
        root->appendChild("Removable Devices", DEVICE_NODE);
        root->appendChild("/", "/");
        root->appendChild("Samples", QString(samples + "/"));
    }
    readDevices();
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
    media.mountsChanged = [&library] {
        library.releaseGoneFolder();
    };
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
    // Plugged in, the Media page closed: the drive's mount enters the mount
    // table, and the next tick sees it. Removable Devices is not read again
    // (it is read when it is opened).
    auto plugIn = [&](const QString& drive) {
        mounted.append(drive);
        writeMounts();
        media.tick();
        settle();
    };
    // The rows the open Removable Devices list shows in the menu.
    auto menuRows = [&] {
        QStringList names;
        for (int row = 0; row < model.rowCount(sidebar.rootIndex()); ++row) {
            if (!sidebar.isRowHidden(row, sidebar.rootIndex())) {
                names.append(model.index(row, 0, sidebar.rootIndex()).data().toString());
            }
        }
        return names;
    };
    auto inDevices = [&] {
        return sidebar.isSourceMenuInside() && sidebar.rootIndex().data().toString() == "Removable Devices";
    };
    // Sources › Folders › Removable Devices: the tap reads the list
    // (onLazyChildExpandation), then the menu shows its rows.
    auto openDevices = [&] {
        openMenu();
        toTop();
        tileNamed(sidebar, "Folders")->click();
        settle();
        readDevices();
        settle();
        const QModelIndex row = rowNamed("Removable Devices");
        QTest::mouseClick(sidebar.viewport(), Qt::LeftButton, {}, sidebar.visualRect(row).center());
        settle();
    };
    auto observe = [&](const char* when) {
        std::cout << "OBSERVE " << when << ": list '" << devices().join(", ").toStdString() << "' menu '"
                  << menuRows().join(", ").toStdString() << "' inside " << inDevices() << std::endl;
    };
    closeMenu();

    // 1. The card's list (acceptance K, 52-removable.png): SD-Backup, a
    // plain folder, and two drives. The list stays open in the menu.
    openDevices();
    observe("opened");
    require(inDevices() && devices() == QStringList({"SD-Backup", "GANDER1", "IXIAN"}) &&
                    menuRows() == devices(),
            "the open Removable Devices list shows SD-Backup, GANDER1 and IXIAN");

    // 2. GANDER1 pulled out (no Media page), the list open.
    pull(gander);
    observe("after the pull");
    require(devices().contains("SD-Backup") && menuRows().contains("SD-Backup") && inDevices(),
            "J11 pull: the open list keeps SD-Backup (a plain folder, never a mount)");
    require(!devices().contains("GANDER1") && !menuRows().contains("GANDER1"),
            "J11 pull: the pulled drive's row (GANDER1) goes");
    require(devices().contains("IXIAN"), "J11 pull: the drive still in (IXIAN) stays");
    closeMenu();

    // 3. IXIAN ejected through the Media page. Its releaseViews empties
    // every folder row below Computer (build B), so the list is read again
    // when it is opened; the next tick then sees the mount table changed
    // since its last look.
    eject(ixian);
    observe("after the eject, before the list is opened again");
    openDevices();
    media.tick();
    settle();
    observe("after the eject, the list opened again and the next tick");
    require(devices() == QStringList({"SD-Backup"}) && menuRows() == devices() && inDevices(),
            "J11 eject: the open list keeps SD-Backup");
    require(!devices().contains("IXIAN"), "J11 eject: the ejected drive's row (IXIAN) goes");

    // 4. GANDER1 plugged in again, the list open.
    plugIn(gander);
    observe("after the plug-in, the list open");
    require(devices().contains("SD-Backup") && menuRows().contains("SD-Backup") && inDevices(),
            "J11 plug-in: the open list keeps SD-Backup");
    require(!devices().contains("IXIAN"), "J11 plug-in: the ejected drive's row does not come back");
    std::cout << "OBSERVE a drive plugged in while the list is open is listed at once: "
              << devices().contains("GANDER1") << std::endl;
    closeMenu();
    openDevices();
    observe("after the plug-in, the list opened again");
    require(devices() == QStringList({"SD-Backup", "GANDER1"}) && menuRows() == devices(),
            "the list opened again shows SD-Backup and the drive plugged in (GANDER1), as build B");

    // 5. SD-Backup's folder in Tracks (it lies in /, which never goes), then
    // a drive pulled out: the table and the menu stay.
    QTest::mouseClick(sidebar.viewport(), Qt::LeftButton, {}, sidebar.visualRect(rowNamed("SD-Backup")).center());
    settle();
    closeMenu();
    require(table() == QStringList({"backup.mp3"}), "SD-Backup's folder is in the table through Removable Devices");
    const QPersistentModelIndex shownBackup = sidebar.currentIndex();
    pull(gander);
    openMenu();
    require(table() == QStringList({"backup.mp3"}) && shownBackup.isValid() &&
                    sidebar.currentIndex() == QModelIndex(shownBackup) && inDevices(),
            "J11: with SD-Backup's folder in Tracks a pull leaves the table, the row and the menu alone");
    closeMenu();

    // 6. J10 still holds: GANDER1's folder in Tracks, then GANDER1 pulled
    // out: 0 rows, ☰ at the top level, and only GANDER1's row goes.
    plugIn(gander);
    plugIn(ixian);
    readDevices(); // the tap on Removable Devices reads it
    require(openFolders({"Removable Devices", "GANDER1", "Contents", "21 Savage Metro Boomin Drake",
                    "SAVAGE MODE II"}) &&
                    table() == QStringList({"43 - Mr. Right Now.mp3"}),
            "GANDER1's SAVAGE MODE II is in the table");
    pull(gander);
    require(table().isEmpty() && !anyFrom(gander), "J10 with J11: the pulled drive's folder leaves the table");
    require(topWithoutEdge(), "J10 with J11: ☰ opens at the top level, no edge, nothing current");
    require(devices() == QStringList({"SD-Backup", "IXIAN"}),
            "J10 with J11: Removable Devices drops GANDER1 and keeps SD-Backup and IXIAN");

    require(settings.getValueString(ConfigKey(kConfigGroup, "SidebarDefaultSource")) == savedStart,
            "J11 does not change the saved start (★)");
    require(treeDigest(gander) == ganderBefore && treeDigest(ixian) == ixianBefore &&
                    treeDigest(backup) == backupBefore,
            "nothing on the drives or in SD-Backup was written");
    std::cout << "OK " << failures << std::endl;
    return failures ? 1 : 0;
}
