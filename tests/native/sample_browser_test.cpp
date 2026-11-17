// R-8 native part: the Load sample screen keeps its own place in the one
// library list. The actual Library methods (setupSampleBrowser,
// sampleSourcePlace, driveRows, showBrowsePlace, ...) from the patched
// library.cpp, the actual SampleBrowser and actionsMenu from libraryinterface.h,
// and the actual SidebarModel/TreeItemModel. Substitutes: the features (named
// trees), the controls, and the track list (one search text per list, and a
// scroll position that a new list resets).
#include <QApplication>
#include <QDir>
#include <QFileInfo>
#include <QMenu>
#include <QScopedPointer>
#include <QTemporaryDir>
#include <QTimer>
#include <QTreeView>
#include <iostream>
#include <memory>

#include "control/controlobject.h"
#include "library/libraryfeature.h"
#include "library/sidebarmodel.h"
#include "library/treeitem.h"
#include "preferences/configobject.h"
#include "widget/libraryinterface.h"

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

class SidebarView : public QTreeView {
  public:
    void selectIndex(const QModelIndex& index) {
        setCurrentIndex(index);
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
    SidebarModel* m_pSidebarModel;
    SidebarView* m_pSidebarWidget;
    QList<SidebarSource> m_sidebarSources;
    QList<LibraryFeature*> m_features;
    std::unique_ptr<LibraryInterface::SampleBrowser> m_pSampleBrowser;
    std::unique_ptr<LibraryInterface::BrowsePlace> m_pShownPlace;
    QScopedPointer<ControlObject> m_pSampleLoad;
    QScopedPointer<ControlObject> m_pSampleSource;
    QScopedPointer<ControlObject> m_pSampleSourceAvailable;
    QString m_samplesPath;
    QStringList m_driveOrder;

    // The track list: what it shows, each list's search, the scroll bar.
    QString shownList;
    QHash<QString, QString> searches;
    int scroll = 0;
    int defaultActivations = 0;

    Library(SidebarModel* model, SidebarView* view)
            : m_pSidebarModel(model), m_pSidebarWidget(view) {
    }
    void add(const QString& id, LibraryFeature* feature) {
        m_sidebarSources.append({id, feature->identity, ConfigKey("Library", id), feature, {}});
        m_features.append(feature);
        m_pSidebarModel->addLibraryFeature(feature);
    }
    // Library::slotShowTrackModel: a new list, scrolled to the top.
    void listShown(const QString& list) {
        shownList = list;
        scroll = 0;
        noteBrowsePlaceShown();
    }
    void restoreSearch(const QString&) {}
    void search(const QString& text) {
        searches[shownList] = text;
    }
    QString browseSearch() const {
        return searches.value(shownList);
    }
    int browseScroll() const {
        return scroll;
    }
    void setBrowseScroll(int value) {
        scroll = value;
    }

    void setupSampleBrowser();
    void leaveSampleMode(bool restoreTracks);
    void noteBrowsePlaceShown();
    LibraryInterface::BrowsePlace sampleSourcePlace(int source);
    void showBrowsePlace(const LibraryInterface::BrowsePlace& place);
    QModelIndex sourceRow(const QString& id) const;
    QList<QModelIndex> driveRows();
};

#include "library_sample_methods.h"

// The lambda WTrackTableView::showTrackMenu gives the Actions menu.
std::function<void()> tableLoadToPad() {
#include "load_to_pad.inc"
    return loadToPad;
}

ControlObject* control(const char* name) {
    return ControlObject::getControl(ConfigKey("[MixPi]", name));
}

void settle() {
    for (int round = 0; round < 3; ++round) {
        QApplication::processEvents();
    }
}

std::unique_ptr<TreeItem> item(const QString& label, const QVariant& data) {
    return std::make_unique<TreeItem>(label, data);
}

void insert(TreeItemModel& model, std::unique_ptr<TreeItem> child) {
    std::vector<std::unique_ptr<TreeItem>> rows;
    rows.push_back(std::move(child));
    model.insertTreeItemRows(std::move(rows), model.rowCount());
}

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    QTemporaryDir home;
    const QString samples = QDir(home.path()).filePath("Music/Samples");
    QDir().mkpath(samples);
    const QString stick = QDir(home.path()).filePath("media/STICK");
    const QString mantacore = QDir(home.path()).filePath("media/MANTACORE");
    QDir().mkpath(stick);
    QDir().mkpath(mantacore);

    SidebarModel model;
    SidebarView view;
    view.setModel(&model);
    Library library(&model, &view);
    library.m_samplesPath = samples;
    LibraryFeature tracks("Tracks");
    LibraryFeature playlists("Playlists");
    LibraryFeature computer("Computer");
    LibraryFeature recordings("Recordings");
    LibraryFeature rekordbox("Rekordbox");
    auto playlistTree = [&playlists] {
        auto root = TreeItem::newRoot(&playlists);
        root->appendChild("P", 1);
        root->appendChild("Q", 2);
        playlists.children.setRootItem(std::move(root));
    };
    playlistTree();
    {
        auto root = TreeItem::newRoot(&computer);
        root->appendChild("Quick Links", QUICK_LINK_NODE);
        root->appendChild("Removable Devices", DEVICE_NODE);
        root->appendChild("/", "/");
        root->appendChild("Samples", QString(samples + "/"));
        computer.children.setRootItem(std::move(root));
    }
    library.add("MixxxLibraryFeature", &tracks);
    library.add("PlaylistFeature", &playlists);
    library.add("BrowseFeature", &computer);
    library.add("RecordingFeature", &recordings);
    library.add("RekordboxFeature", &rekordbox);
    LibraryFeature::shown = [&library](const QString& list) { library.listShown(list); };
    library.setupSampleBrowser();

    auto* sampleLoad = control("sample_load");
    auto* sampleSource = control("sample_source");
    require(control("sample_source_available")->get() == 1 &&
                    control("sample_source_available")->m_readOnly,
            "sample_source_available is 1 and read-only");

    // Tracks on playlist P with search "abc", scrolled down.
    const QModelIndex p = model.index(0, 0, model.index(1, 0));
    view.selectIndex(p);
    model.clicked(p);
    library.search("abc");
    library.scroll = 120;
    require(library.shownList == "Playlists/P", "Tracks shows playlist P");

    sampleLoad->set(1);
    settle();
    require(sampleLoad->get() == 1, "sample_load 1 is confirmed");
    require(library.shownList == "Computer/Samples", "entering sample mode shows the Samples folder");
    require(library.browseSearch().isEmpty(), "the sample list's search is empty");
    require(sampleSource->get() == 1, "sample_source reads 1 (Samples)");

    sampleSource->set(2);
    settle();
    require(library.shownList == "Tracks" && sampleSource->get() == 2,
            "sample_source 2 shows the track collection");
    library.search("kick");
    library.scroll = 40;
    sampleSource->set(0);
    require(library.shownList == "Tracks" && sampleSource->get() == 2,
            "a button release (0) changes nothing");

    sampleLoad->set(0);
    settle();
    require(library.shownList == "Playlists/P", "leaving shows playlist P again");
    require(library.browseSearch() == "abc", "Tracks' search abc is back");
    require(library.scroll == 120, "Tracks' scroll position is back");
    require(sampleSource->get() == 0, "sample_source reads 0 outside sample mode");
    sampleSource->set(4);
    require(library.shownList == "Playlists/P", "a source button outside sample mode does nothing");

    sampleLoad->set(1);
    settle();
    require(library.shownList == "Tracks" && sampleSource->get() == 2,
            "entering again shows the collection, as left");
    require(library.browseSearch() == "kick" && library.scroll == 40,
            "the sample list's own search and scroll are back");

    sampleSource->set(4);
    settle();
    require(library.shownList == "Recordings" && sampleSource->get() == 4,
            "sample_source 4 shows Recordings");

    sampleSource->set(3);
    settle();
    require(library.shownList == "Computer/Samples" && sampleSource->get() == 1,
            "sample_source 3 without an open drive falls back to Samples");

    // A rekordbox drive, then a drive opened in Computer.
    QVariantList drive{mantacore, QString(), QStringLiteral("rev-1")};
    insert(rekordbox.children, item("MANTACORE", drive));
    settle();
    sampleSource->set(3);
    settle();
    require(library.shownList == "Rekordbox/MANTACORE" && sampleSource->get() == 3,
            "sample_source 3 shows the open rekordbox drive");
    insert(computer.children, item(stick, stick));
    settle();
    require(library.driveRows().size() == 2 &&
                    library.driveRows().first().data().toString() == "MANTACORE",
            "drives keep plug-in order; the fixed Computer rows are not drives");

    // The drive is pulled out while the sample browser shows it.
    rekordbox.children.removeRows(0, 1);
    settle();
    require(library.shownList == "Computer/Samples" && sampleSource->get() == 1,
            "a drive that vanished falls back to Samples");
    sampleSource->set(3);
    settle();
    require(library.shownList == QString("Computer/" + stick) && sampleSource->get() == 3,
            "sample_source 3 shows the drive opened in Computer");
    QDir(stick).removeRecursively();
    require(library.driveRows().isEmpty(), "a Computer drive whose folder is gone is not a drive");
    computer.children.removeRows(computer.children.rowCount() - 1, 1);
    settle();
    require(library.shownList == "Computer/Samples", "its row going away falls back to Samples");

    // A list picked in Sources while in sample mode.
    const QModelIndex q = model.index(1, 0, model.index(1, 0));
    view.selectIndex(q);
    model.clicked(q);
    require(library.shownList == "Playlists/Q" && sampleSource->get() == 0,
            "a list picked in Sources is the sample place; no source button is lit");
    sampleLoad->set(0);
    settle();
    require(library.shownList == "Playlists/P" && library.browseSearch() == "abc",
            "leaving still restores Tracks");

    // A reset of the sidebar model ends every persistent index.
    playlistTree();
    settle();
    sampleLoad->set(1);
    settle();
    require(library.shownList == "Playlists/Q", "after a model reset the sample place is found again");
    playlistTree();
    settle();
    sampleLoad->set(0);
    settle();
    require(library.shownList == "Playlists/P" && library.browseSearch() == "abc" &&
                    library.scroll == 120,
            "after a model reset Tracks' place is found again");

    // A drive opened from the media screen while in sample mode stays shown.
    sampleLoad->set(1);
    settle();
    QDir().mkpath(stick);
    insert(computer.children, item(stick, stick));
    const QModelIndex opened = model.index(computer.children.rowCount() - 1, 0, model.index(2, 0));
    view.selectIndex(opened);
    model.clicked(opened);
    library.leaveSampleMode(false);
    settle();
    require(sampleLoad->get() == 0 && library.shownList == QString("Computer/" + stick),
            "a drive opened from the media screen ends sample mode and stays in Tracks");

    // Tracks' place gone (its playlist deleted): the start source.
    const QModelIndex again = model.index(0, 0, model.index(1, 0));
    view.selectIndex(again);
    model.clicked(again);
    require(library.shownList == "Playlists/P", "Tracks shows P again");
    sampleLoad->set(1);
    settle();
    require(library.shownList == QString("Computer/" + stick), "the sample browser is back at its last place");
    {
        auto root = TreeItem::newRoot(&playlists);
        root->appendChild("Q", 2);
        playlists.children.setRootItem(std::move(root));
    }
    settle();
    sampleLoad->set(0);
    settle();
    require(library.shownList == "Tracks", "Tracks' place gone: leaving shows the start source");

    // Actions: "Load to a sampler pad…" opens Choose pad (screen 4).
    QWidget table;
    QMenu original;
    require(!tableLoadToPad(), "a skin without [MixPi],screen gets no sampler entry");
    ControlObject screen(ConfigKey("[MixPi]", "screen"));
    ControlObject pad(ConfigKey("[MixPi]", "sample_pad"));
    pad.setAndConfirm(5);
    QMenu decks;
    decks.addAction("Deck 1");
    auto* menu = LibraryInterface::actionsMenu(&table, &decks, &original, [] {}, tableLoadToPad());
    QAction* entry = nullptr;
    for (auto* action : menu->actions()) {
        if (action->objectName() == "MixpiLoadToPad") {
            entry = action;
        }
    }
    require(entry && entry->text() == QString::fromUtf8("Load to a sampler pad…") &&
                    menu->actions().indexOf(entry) == 1,
            "the Actions menu has Load to a sampler pad… after Load");
    require(entry && entry->isEnabled(), "the entry is on for one selected row");
    entry->trigger();
    require(screen.get() == 4 && pad.get() == 0 && sampleLoad->get() == 0,
            "the entry writes screen 4 (Choose pad), pad 0, and keeps Tracks' list");
    decks.setEnabled(false);
    auto* none = LibraryInterface::actionsMenu(&table, &decks, &original, [] {}, tableLoadToPad());
    require(!none->actions().at(1)->isEnabled(), "the entry is off when Load is off (several rows)");
    auto* plain = LibraryInterface::actionsMenu(&table, &decks, &original, [] {});
    require(plain->actions().at(1)->text() == "Arrange columns", "without it the menu is as before");

    std::cout << (failures ? "FAILED " : "OK ") << failures << std::endl;
    return failures ? 1 : 0;
}
