// Build F (spec 2c, plan 12.7): one column setup for every track table,
// saved within a second of each change, through the shipped
// WTrackTableViewHeader, MixpiSharedColumns, MixpiTableFit, ProxyTrackModel,
// BrowseTableModel, SettingsDAO, ConfigObject and ConfigAutosave. The view
// code (the store, the header swap and its build F lines) is copied verbatim
// from the patched wtracktableview.cpp by shared_columns_runner.py.
//
// usage: shared-columns-test MODE DIRECTORY
//   checks     every check but the kill
//   widths     build G: a column shown again keeps its saved width, and
//              opening lists writes nothing
//   kill       makes a change, prints CHANGED, then waits to be killed
//   after-kill reads the setup the killed process left in mixxx.cfg
#include <QApplication>
#include <QCheckBox>
#include <QDialog>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QFile>
#include <QListWidget>
#include <QMouseEvent>
#include <QMutex>
#include <QPointer>
#include <QScrollBar>
#include <QSqlDatabase>
#include <QSqlQuery>
#include <QStandardItemModel>
#include <QTableView>
#include <QTimer>
#include <cstdio>
#include <functional>
#include <iostream>
#include <memory>

#include "control/controlobject.h"
#include "library/browse/browsetablemodel.h"
#include "library/dao/settingsdao.h"
#include "library/proxytrackmodel.h"
#include "library/trackcollectionmanager.h"
#include "preferences/usersettings.h"
#include "proto/headers.pb.h"
#include "recording/recordingmanager.h"
#include "widget/mixpisharedcolumns.h"
#include "widget/mixpitablefit.h"
#include "widget/wtracktableviewheader.h"

namespace {

int failures = 0;
int asserts = 0;
int saves = 0;
QMutex messagesMutex;

void require(bool condition, const char* name) {
    std::cout << (condition ? "PASS " : "FAIL ") << name << std::endl;
    failures += condition ? 0 : 1;
}

void spin(int ms) {
    QEventLoop loop;
    QTimer::singleShot(ms, &loop, &QEventLoop::quit);
    loop.exec();
}

bool waitFor(int maxMs, const std::function<bool()>& condition) {
    QElapsedTimer timer;
    timer.start();
    while (!condition()) {
        if (timer.elapsed() > maxMs) {
            return false;
        }
        spin(10);
    }
    return true;
}

QByteArray readAll(const QString& path) {
    QFile file(path);
    return file.open(QIODevice::ReadOnly) ? file.readAll() : QByteArray();
}

// The SharedColumns line of mixxx.cfg as the file holds it now.
QString fileValue(const QString& path) {
    for (const QByteArray& line : readAll(path).split('\n')) {
        if (line.startsWith("SharedColumns ")) {
            return QString::fromLatin1(line.mid(14)).trimmed();
        }
    }
    return {};
}

} // namespace

// The Library double: the store reads This Pi > Tracks' row through it.
class Library : public QObject {
  public:
    explicit Library(TrackCollectionManager* manager)
            : m_manager(manager) {
    }
    TrackCollectionManager* trackCollectionManager() const {
        return m_manager;
    }

  private:
    TrackCollectionManager* m_manager;
};

#include "store_constants.inc"

// A list with SQL field names, like BaseTrackTableModel: This Pi > Tracks
// ("mixxx.db.model.library"), a playlist with # ("position"), Auto DJ.
class NamedModel final : public QStandardItemModel, public TrackModel {
  public:
    NamedModel(const QSqlDatabase& db, const char* settingsNamespace, QStringList names, QStringList labels)
            : QStandardItemModel(0, static_cast<int>(names.size())),
              TrackModel(db, settingsNamespace),
              m_names(std::move(names)) {
        setHorizontalHeaderLabels(labels);
        for (int column = 0; column < m_names.size(); ++column) {
            setHeaderData(column, Qt::Horizontal, m_names[column], kHeaderNameRole);
            setHeaderData(column, Qt::Horizontal, 100, kHeaderWidthRole);
        }
        for (int row = 0; row < 3; ++row) {
            QList<QStandardItem*> items;
            for (int column = 0; column < m_names.size(); ++column) {
                items.append(new QStandardItem(QStringLiteral("%1 %2").arg(labels[column]).arg(row)));
            }
            appendRow(items);
        }
    }
    int fieldIndex(const QString& name) const override {
        return static_cast<int>(m_names.indexOf(name));
    }
    TrackPointer getTrack(const QModelIndex&) const override { return {}; }
    TrackPointer getTrackByRef(const TrackRef&) const override { return {}; }
    QUrl getTrackUrl(const QModelIndex&) const override { return {}; }
    QString getTrackLocation(const QModelIndex&) const override { return {}; }
    TrackId getTrackId(const QModelIndex&) const override { return {}; }
    CoverInfo getCoverInfo(const QModelIndex&) const override { return {}; }
    const QVector<int> getTrackRows(TrackId) const override { return {}; }
    void search(const QString&) override {}
    const QString currentSearch() const override { return {}; }
    bool isColumnInternal(int) override { return false; }
    bool isColumnHiddenByDefault(int column) override {
        return m_names[column] == QStringLiteral("preview");
    }
    SortColumnId sortColumnIdFromColumnIndex(int) const override { return SortColumnId::Invalid; }
    int columnIndexFromSortColumnId(SortColumnId) const override { return -1; }
    QString modelKey(bool) const override { return m_names.join(','); }
    bool updateTrackGenre(Track*, const QString&) const override { return false; }

  private:
    QStringList m_names;
};

// WTrackTableView's parts that keep the header: the store (constructor),
// the header swap with its build F lines (loadTrackModel), the fit after a
// resize and at the end of loadTrackModel, and the save when it goes away.
class View : public QTableView {
  public:
    View(UserSettingsPointer pConfig, Library* pLibrary, QWidget* parent = nullptr)
            : QTableView(parent), m_pConfig(pConfig), m_pLibrary(pLibrary) {
        verticalHeader()->hide(); // as WLibraryTableView
#include "store_block.inc"
    }
    ~View() override {
        if (auto* pHeader = qobject_cast<WTrackTableViewHeader*>(horizontalHeader())) {
            m_columnFit.withFullWidths(pHeader, [pHeader] { pHeader->saveHeaderState(); });
        }
    }
    void loadTrackModel(QAbstractItemModel* pNewModel) {
#include "header_swap.inc"
        setVisible(true);
        m_columnFit.fit();
        QApplication::processEvents();
    }
    WTrackTableViewHeader* header() const {
        return qobject_cast<WTrackTableViewHeader*>(horizontalHeader());
    }

    UserSettingsPointer m_pConfig;
    Library* m_pLibrary;
    bool m_sorting = true;
    MixpiTableFit m_columnFit{this, [](QHeaderView* pHeader) {
                                  auto* pTrackHeader = qobject_cast<WTrackTableViewHeader*>(pHeader);
                                  return pTrackHeader ? pTrackHeader->stretchColumnIndex() : -1;
                              }};

  protected:
    void resizeEvent(QResizeEvent* event) override {
        QTableView::resizeEvent(event);
        m_columnFit.fit();
    }
};

namespace {

QString nameOf(const QHeaderView* header, int column) {
    return header->model()->headerData(column, Qt::Horizontal, TrackModel::kHeaderNameRole).toString();
}

int columnNamed(const QHeaderView* header, const QString& name) {
    for (int column = 0; column < header->count(); ++column) {
        if (nameOf(header, column) == name) {
            return column;
        }
    }
    return -1;
}

QStringList shownOrder(const QHeaderView* header) {
    QStringList order;
    for (int visual = 0; visual < header->count(); ++visual) {
        const int column = header->logicalIndex(visual);
        if (!header->isSectionHidden(column)) {
            order.append(nameOf(header, column));
        }
    }
    return order;
}

int widthOf(const QHeaderView* header, const QString& name) {
    const int column = columnNamed(header, name);
    return column < 0 ? -1 : header->sectionSize(column);
}

void observe(const char* label, const QHeaderView* header) {
    std::cout << "OBSERVE " << label << ":";
    for (int visual = 0; visual < header->count(); ++visual) {
        const int column = header->logicalIndex(visual);
        if (!header->isSectionHidden(column)) {
            std::cout << ' ' << nameOf(header, column).toStdString() << '=' << header->sectionSize(column);
        }
    }
    std::cout << std::endl;
}

MixpiSharedColumns::Column sharedColumn(const QString& value, const QString& name) {
    for (const auto& column : MixpiSharedColumns::parse(value)) {
        if (column.name == name) {
            return column;
        }
    }
    return {QString(), true, -1};
}

QStringList sharedShown(const QString& value) {
    QStringList order;
    for (const auto& column : MixpiSharedColumns::parse(value)) {
        if (!column.hidden) {
            order.append(column.name);
        }
    }
    return order;
}

void mouse(QWidget* widget, QEvent::Type type, QPoint position, Qt::MouseButtons buttons) {
    QMouseEvent event(type, QPointF(position), QPointF(widget->mapToGlobal(position)),
            type == QEvent::MouseMove ? Qt::NoButton : Qt::LeftButton, buttons, Qt::NoModifier);
    QApplication::sendEvent(widget, &event);
    QApplication::processEvents();
}

// A finger on a column's right edge, dragged by delta px in steps moves.
void resizeByDrag(QHeaderView* header, const QString& name, int delta, int steps) {
    const int column = columnNamed(header, name);
    const int x = header->sectionViewportPosition(column) + header->sectionSize(column) - 1;
    const int y = header->height() / 2;
    QWidget* surface = header->viewport();
    mouse(surface, QEvent::MouseButtonPress, {x, y}, Qt::LeftButton);
    for (int step = 1; step <= steps; ++step) {
        mouse(surface, QEvent::MouseMove, {x + delta * step / steps, y}, Qt::LeftButton);
    }
    mouse(surface, QEvent::MouseButtonRelease, {x + delta, y}, Qt::NoButton);
}

// A finger on a column's label, dragged onto the column now at toVisual.
void moveByDrag(QHeaderView* header, const QString& name, int toVisual) {
    const int column = columnNamed(header, name);
    const int from = header->visualIndex(column);
    const int x = header->sectionViewportPosition(column) + header->sectionSize(column) / 2;
    const int y = header->height() / 2;
    const int target = header->logicalIndex(toVisual);
    const int tx = header->sectionViewportPosition(target) +
            (toVisual < from ? 4 : header->sectionSize(target) - 4);
    QWidget* surface = header->viewport();
    mouse(surface, QEvent::MouseButtonPress, {x, y}, Qt::LeftButton);
    constexpr int kSteps = 12;
    for (int step = 1; step <= kSteps; ++step) {
        mouse(surface, QEvent::MouseMove, {x + (tx - x) * step / kSteps, y}, Qt::LeftButton);
    }
    mouse(surface, QEvent::MouseButtonRelease, {tx, y}, Qt::NoButton);
}

QCheckBox* menuChoice(WTrackTableViewHeader* header, const QString& label) {
    for (auto* choice : header->findChildren<QCheckBox*>()) {
        if (choice->text() == label) {
            return choice;
        }
    }
    return nullptr;
}

QString settingsRow(const QSqlDatabase& db, const QString& name) {
    return SettingsDAO(db).getValue(name);
}

QString headerRow(const QList<std::tuple<QString, bool, int>>& columns, int sortSection, int sortOrder) {
    mixxx::library::HeaderViewState state;
    int visual = 0;
    for (const auto& [name, hidden, size] : columns) {
        auto* entry = state.add_header_state();
        entry->set_column_name(name.toStdString());
        entry->set_hidden(hidden);
        entry->set_size(size);
        entry->set_logical_index(visual);
        entry->set_visual_index(visual++);
    }
    state.set_sort_indicator_shown(true);
    state.set_sort_indicator_section(sortSection);
    state.set_sort_order(sortOrder);
    QByteArray bytes(static_cast<int>(state.ByteSizeLong()), '\0');
    state.SerializeToArray(bytes.data(), static_cast<int>(bytes.size()));
    return QString::fromLatin1(bytes.toBase64());
}

const QStringList kLibraryNames{"preview", "artist", "title", "album", "bpm", "key", "duration"};
const QStringList kLibraryLabels{"Preview", "Artist", "Title", "Album", "BPM", "Key", "Duration"};
const QStringList kPlaylistNames{"position", "artist", "title", "album", "bpm", "key", "duration"};
const QStringList kPlaylistLabels{"#", "Artist", "Title", "Album", "BPM", "Key", "Duration"};

QSqlDatabase openDatabase() {
    auto db = QSqlDatabase::addDatabase(QStringLiteral("QSQLITE"), QStringLiteral("table-columns"));
    db.setDatabaseName(QStringLiteral(":memory:"));
    require(db.open(), "sqlite settings database opens");
    QSqlQuery(db).exec(QStringLiteral(
            "CREATE TABLE settings (name TEXT UNIQUE NOT NULL, value TEXT, "
            "locked INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0)"));
    return db;
}

UserSettingsPointer makeConfig(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    if (!QFile::exists(path)) {
        QFile file(path);
        file.open(QIODevice::WriteOnly);
        file.write("\n[Test]\nexisting 1\n");
    }
    return UserSettingsPointer(new UserSettings(path, QStringLiteral("/res/"), directory));
}

void setViewport(View* view, int width) {
    view->resize(view->width() - view->viewport()->width() + width, 300);
    QApplication::processEvents();
}

// Every shown column but the stretch one has its shared (full) width.
bool fullWidths(const View* view, const QString& value) {
    const auto* header = view->header();
    const int stretch = const_cast<WTrackTableViewHeader*>(view->header())->stretchColumnIndex();
    bool ok = true;
    for (int column = 0; column < header->count(); ++column) {
        if (header->isSectionHidden(column) || column == stretch) {
            continue;
        }
        const auto shared = sharedColumn(value, nameOf(header, column));
        if (shared.size >= 0 && shared.size != header->sectionSize(column)) {
            std::cout << "OBSERVE " << nameOf(header, column).toStdString() << " is "
                      << header->sectionSize(column) << " not " << shared.size << std::endl;
            ok = false;
        }
    }
    return ok;
}

int checks(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    auto db = openDatabase();
    // The owner's saved setups before build F. This Pi > Tracks: TITLE,
    // ARTIST 210, BPM 98, KEY 52, sorted by ARTIST descending.
    const QString tracksRowName = QStringLiteral("mixxx.db.model.library.header_state_pb");
    const QString playlistRowName = QStringLiteral("mixxx.db.model.playlist.header_state_pb");
    const QString tracksRow = headerRow({{"title", false, 300}, {"artist", false, 210}, {"bpm", false, 98},
                                                {"key", false, 52}, {"album", true, 150},
                                                {"preview", true, 0}, {"duration", true, 80}},
            1, Qt::DescendingOrder);
    // A playlist with its own, different setup (ALBUM shown), sorted by BPM.
    const QString playlistRow = headerRow({{"album", false, 260}, {"title", false, 300},
                                                  {"position", false, 40}, {"artist", true, 100},
                                                  {"bpm", false, 70}, {"key", true, 50},
                                                  {"duration", true, 80}},
            4, Qt::AscendingOrder);
    SettingsDAO(db).setValue(tracksRowName, tracksRow);
    SettingsDAO(db).setValue(playlistRowName, playlistRow);

    UserSettingsPointer pConfig = makeConfig(directory);
    mixxx::ConfigAutosave autosave(pConfig);
    autosave.start();

    TrackCollectionManager manager;
    Library library(&manager);
    RecordingManager recording;
    BrowseTableModel browse(nullptr, &manager, &recording);
    ProxyTrackModel folder(&browse, true);
    NamedModel tracks(db, "mixxx.db.model.library", kLibraryNames, kLibraryLabels);
    NamedModel playlist(db, "mixxx.db.model.playlist", kPlaylistNames, kPlaylistLabels);
    NamedModel autodj(db, "mixxx.db.model.autodj", kPlaylistNames, kPlaylistLabels);

    // The table sits in the 800 px screen; 776 px is its full width.
    constexpr int kFull = 776;
    constexpr int kNarrow = 456;
    QWidget window;
    window.resize(800, 480);
    auto* page = new QWidget(&window); // the library page the skin hides
    page->resize(800, 480);
    window.show();
    auto view = std::make_unique<View>(pConfig, &library, page);
    view->resize(700, 300);
    view->show();
    setViewport(view.get(), kFull);

    // 1. The first run starts from This Pi > Tracks, whichever list opens.
    view->loadTrackModel(&playlist);
    auto* header = view->header();
    observe("playlist on the first run", header);
    require(shownOrder(header) == QStringList({"title", "artist", "bpm", "key"}) &&
                    widthOf(header, "artist") == 210 && widthOf(header, "bpm") == 98 &&
                    widthOf(header, "key") == 52,
            "first run: a playlist opened first shows This Pi > Tracks' columns, order and widths");
    require(waitFor(1500, [&] { return !fileValue(path).isEmpty(); }) &&
                    sharedShown(fileValue(path)) == QStringList({"title", "artist", "bpm", "key"}),
            "first run: the shared setup is written to mixxx.cfg");
    require(settingsRow(db, tracksRowName) == tracksRow && settingsRow(db, playlistRowName) == playlistRow,
            "first run: the old per-list rows stay as they were");
    require(header->sortIndicatorSection() == 4 && header->sortIndicatorOrder() == Qt::AscendingOrder,
            "first run: the playlist keeps its own sort (BPM ascending)");

    view->loadTrackModel(&tracks);
    header = view->header();
    observe("This Pi > Tracks", header);
    require(shownOrder(header) == QStringList({"title", "artist", "bpm", "key"}) &&
                    widthOf(header, "artist") == 210,
            "This Pi > Tracks shows the same setup");
    require(header->sortIndicatorSection() == 1 && header->sortIndicatorOrder() == Qt::DescendingOrder,
            "This Pi > Tracks keeps its own sort (ARTIST descending)");

    view->loadTrackModel(&folder);
    header = view->header();
    observe("a folder (Browse)", header);
    QStringList folderShared = shownOrder(header);
    folderShared.removeAll(QStringLiteral("filename"));
    require(folderShared == QStringList({"title", "artist", "bpm", "key"}) &&
                    widthOf(header, "artist") == 210 && widthOf(header, "bpm") == 98 &&
                    widthOf(header, "key") == 52,
            "a folder (Browse) shows the shared columns in the shared order and widths");
    require(!shownOrder(header).isEmpty() && shownOrder(header).first() == QStringLiteral("filename"),
            "a folder keeps its own Filename column in its default place");

    // 2. A resize by a drag: on disk within 1 s, one write for the drag.
    int before = saves;
    resizeByDrag(header, QStringLiteral("artist"), 60, 15);
    QElapsedTimer sinceRelease;
    sinceRelease.start();
    const bool onDisk = waitFor(2000, [&] { return sharedColumn(fileValue(path), "artist").size == 270; });
    const qint64 delay = sinceRelease.elapsed();
    std::cout << "OBSERVE artist dragged to " << widthOf(header, "artist") << " px, on disk after " << delay
              << " ms" << std::endl;
    require(widthOf(header, "artist") == 270, "the drag resized ARTIST to 270 px");
    require(onDisk && delay <= 1000, "a resize by a drag in the header is on disk within 1 s");
    spin(1500);
    std::cout << "OBSERVE writes for the drag " << saves - before << std::endl;
    require(saves - before == 1, "a drag of 15 steps gives one write");

    view->loadTrackModel(&tracks);
    header = view->header();
    require(widthOf(header, "artist") == 270, "the new width shows in This Pi > Tracks");

    // 3. A move by a drag.
    moveByDrag(header, QStringLiteral("key"), 0);
    observe("Tracks after KEY was dragged to the front", header);
    require(shownOrder(header) == QStringList({"key", "title", "artist", "bpm"}),
            "the drag moved KEY to the front");
    require(waitFor(1000, [&] {
        return sharedShown(fileValue(path)) == QStringList({"filename", "key", "title", "artist", "bpm"});
    }),
            "a move by a drag is on disk within 1 s");
    view->loadTrackModel(&playlist);
    header = view->header();
    observe("playlist after the move", header);
    require(shownOrder(header) == QStringList({"key", "title", "artist", "bpm"}),
            "a column moved in one list moves in the others (playlist)");

    // 4. A column a list does not have keeps its place: # in the playlist.
    QCheckBox* number = menuChoice(header, QStringLiteral("#"));
    require(number && !number->isChecked(), "the header menu offers the hidden #");
    if (number) {
        number->setChecked(true);
        QApplication::processEvents();
    }
    moveByDrag(header, QStringLiteral("position"), 2);
    observe("playlist with # shown and moved", header);
    require(shownOrder(header) == QStringList({"key", "title", "position", "artist", "bpm"}),
            "# shown from the header menu and dragged to third");
    require(waitFor(1000, [&] {
        return sharedShown(fileValue(path)) == QStringList({"filename", "key", "title", "position", "artist", "bpm"});
    }),
            "the header menu and the move are on disk within 1 s");
    view->loadTrackModel(&tracks);
    header = view->header();
    require(shownOrder(header) == QStringList({"key", "title", "artist", "bpm"}),
            "a column a list does not have is skipped there (# in This Pi > Tracks)");
    moveByDrag(header, QStringLiteral("artist"), 0);
    require(shownOrder(header) == QStringList({"artist", "key", "title", "bpm"}),
            "ARTIST dragged to the front in This Pi > Tracks");
    view->loadTrackModel(&playlist);
    header = view->header();
    observe("playlist after the change in Tracks", header);
    require(shownOrder(header) == QStringList({"artist", "key", "position", "title", "bpm"}),
            "# keeps its place (third) in the playlist after a change in This Pi > Tracks");

    // 5. Show or hide in Arrange columns.
    view->loadTrackModel(&tracks);
    header = view->header();
    header->showColumnArrangement();
    QApplication::processEvents();
    if (auto* dialog = header->findChild<QDialog*>(QStringLiteral("MixpiColumnArrangement"))) {
        auto* list = dialog->findChild<QListWidget*>();
        for (int row = 0; list && row < list->count(); ++row) {
            if (list->item(row)->text() == QStringLiteral("BPM")) {
                list->item(row)->setCheckState(Qt::Unchecked);
            }
        }
        dialog->close();
    }
    QApplication::processEvents();
    require(waitFor(1000, [&] { return sharedColumn(fileValue(path), "bpm").hidden; }),
            "a column hidden in Arrange columns is on disk within 1 s");
    view->loadTrackModel(&folder);
    header = view->header();
    require(header->isSectionHidden(columnNamed(header, "bpm")),
            "a column hidden in Arrange columns is hidden in a folder too");
    view->loadTrackModel(&playlist);
    header = view->header();
    require(header->isSectionHidden(columnNamed(header, "bpm")) && !menuChoice(header, "BPM")->isChecked(),
            "... and in the playlist, with its header menu box clear");
    menuChoice(header, QStringLiteral("BPM"))->setChecked(true);
    QApplication::processEvents();
    require(waitFor(1000, [&] { return !sharedColumn(fileValue(path), "bpm").hidden; }),
            "a column shown from the header menu is on disk within 1 s");

    // 6. The sort stays per list and writes nothing to the shared setup.
    const QString beforeSort = fileValue(path);
    view->loadTrackModel(&tracks);
    view->header()->setSortIndicator(columnNamed(view->header(), "title"), Qt::AscendingOrder);
    view->loadTrackModel(&playlist);
    view->header()->setSortIndicator(columnNamed(view->header(), "bpm"), Qt::DescendingOrder);
    view->loadTrackModel(&folder);
    view->header()->setSortIndicator(columnNamed(view->header(), "key"), Qt::AscendingOrder);
    view->loadTrackModel(&tracks);
    header = view->header();
    require(header->sortIndicatorSection() == columnNamed(header, "title") &&
                    header->sortIndicatorOrder() == Qt::AscendingOrder,
            "sort per list: This Pi > Tracks is still by TITLE ascending");
    view->loadTrackModel(&playlist);
    header = view->header();
    require(header->sortIndicatorSection() == columnNamed(header, "bpm") &&
                    header->sortIndicatorOrder() == Qt::DescendingOrder,
            "sort per list: the playlist is still by BPM descending");
    view->loadTrackModel(&folder);
    header = view->header();
    require(header->sortIndicatorSection() == columnNamed(header, "key") &&
                    header->sortIndicatorOrder() == Qt::AscendingOrder,
            "sort per list: the folder is still by KEY ascending");
    spin(800);
    require(fileValue(path) == beforeSort, "sorting changes nothing in the shared setup");
    require(settingsRow(db, tracksRowName) == tracksRow && settingsRow(db, playlistRowName) == playlistRow,
            "the old per-list rows are still unused and unchanged");

    // 7. Another open table (Auto DJ has its own) shows a change at once.
    view->loadTrackModel(&tracks);
    QWidget other;
    other.resize(800, 480);
    other.show();
    auto autodjView = std::make_unique<View>(pConfig, &library, &other);
    autodjView->resize(700, 300);
    autodjView->show();
    setViewport(autodjView.get(), kFull);
    autodjView->loadTrackModel(&autodj);
    observe("Auto DJ before", autodjView->header());
    resizeByDrag(view->header(), QStringLiteral("key"), 30, 6);
    const int key = widthOf(view->header(), "key");
    observe("Auto DJ after a change in This Pi > Tracks", autodjView->header());
    require(!autodjView->m_columnFit.active() && widthOf(autodjView->header(), "key") == key && key == 82,
            "a change shows at once in another open table (Auto DJ)");
    autodjView.reset();

    // 8. The narrowed table (Sources open) fits; the fit is never saved and
    // every way of closing Sources or Edit sources brings the full widths.
    view->loadTrackModel(&tracks);
    header = view->header();
    QString full = fileValue(path);
    require(waitFor(1500, [&] { return fileValue(path) == pConfig->getValueString(kSharedColumnsConfigKey); }),
            "the file holds the setup before the fit checks");
    full = fileValue(path);
    before = saves;
    setViewport(view.get(), kNarrow);
    observe("narrowed (Sources open)", header);
    require(view->horizontalScrollBar()->maximum() == 0 && !fullWidths(view.get(), full),
            "fit: the narrowed table fits its columns");
    spin(1500);
    require(saves == before && fileValue(path) == full, "fit: the fitted widths are not saved");
    moveByDrag(header, QStringLiteral("bpm"), 1);
    observe("narrowed, BPM dragged to second", header);
    require(waitFor(1000, [&] { return fileValue(path) != full; }),
            "fit: a move while narrowed is saved within 1 s");
    {
        const QString value = fileValue(path);
        require(sharedShown(value) == QStringList({"filename", "artist", "bpm", "position", "key", "title"}) &&
                        sharedColumn(value, "artist").size == 270 && sharedColumn(value, "key").size == 82 &&
                        // BPM was hidden at 98 and shown again: 98 (build G; build F
                        // saved the 160 px of acceptance F's FAIL 1 here).
                        sharedColumn(value, "bpm").size == 98,
                "fit: a change while narrowed saves the full widths, never the fitted ones");
    }
    full = fileValue(path);
    setViewport(view.get(), kFull);
    observe("Sources closed", header);
    require(fullWidths(view.get(), full), "close path: Sources closed, the table widens: full widths");

    setViewport(view.get(), kNarrow);
    view->hide(); // Edit sources covers the page
    setViewport(view.get(), kFull); // ✕: Sources closes while the table is hidden
    view->show();
    QApplication::processEvents();
    observe("Edit sources closed with the table hidden", header);
    require(fullWidths(view.get(), full), "close path: Edit sources ✕ (table hidden): full widths");

    setViewport(view.get(), kNarrow);
    page->hide(); // another page over the library
    setViewport(view.get(), kFull);
    page->show();
    QApplication::processEvents();
    observe("Edit sources closed with the page hidden", header);
    require(fullWidths(view.get(), full), "close path: Edit sources ✕ (page hidden): full widths");

    setViewport(view.get(), kNarrow);
    page->hide();
    view->loadTrackModel(&playlist); // a list picked in Sources, then ✕
    setViewport(view.get(), kFull);
    page->show();
    QApplication::processEvents();
    header = view->header();
    observe("a list picked, then Sources closed while hidden", header);
    require(fullWidths(view.get(), full), "close path: a list picked, then ✕ while hidden: full widths");

    setViewport(view.get(), kNarrow);
    view->loadTrackModel(&tracks);
    view.reset(); // quit while narrowed
    spin(1200);
    require(fileValue(path) == full, "fit: quitting while narrowed saves nothing fitted");

    autosave.stop();
    require(asserts == 0, "no DEBUG_ASSERT fired");
    std::cout << "FAILURES " << failures << std::endl;
    return failures ? 1 : 0;
}

// Build G (acceptance F, FAIL 1 and note N1). The arrange dialog the header
// shows now.
QListWidget* arrangeList(WTrackTableViewHeader* header) {
    header->showColumnArrangement();
    QApplication::processEvents();
    for (auto* dialog : header->findChildren<QDialog*>(QStringLiteral("MixpiColumnArrangement"))) {
        if (dialog->isVisible()) {
            return dialog->findChild<QListWidget*>();
        }
    }
    return nullptr;
}

void closeArrange(QListWidget* list) {
    if (list) {
        qobject_cast<QDialog*>(list->window())->close();
    }
    spin(20);
}

bool arrange(QListWidget* list, const QString& label, bool shown) {
    for (int row = 0; list && row < list->count(); ++row) {
        if (list->item(row)->text() == label) {
            list->item(row)->setCheckState(shown ? Qt::Checked : Qt::Unchecked);
            QApplication::processEvents();
            return true;
        }
    }
    return false;
}

void choose(WTrackTableViewHeader* header, const QString& label, bool shown) {
    if (auto* choice = menuChoice(header, label)) {
        choice->setChecked(shown);
    }
    QApplication::processEvents();
}

bool savedAs(const QString& path, const char* name, bool hidden, int size) {
    return waitFor(1000, [&] {
        const auto column = sharedColumn(fileValue(path), name);
        return column.hidden == hidden && column.size == size;
    });
}

void observeSaved(const char* label, const QString& path) {
    std::cout << "OBSERVE " << label << " saved:";
    for (const auto& column : MixpiSharedColumns::parse(fileValue(path))) {
        std::cout << ' ' << column.name.toStdString() << (column.hidden ? "(hidden)" : "") << '='
                  << column.size;
    }
    std::cout << std::endl;
}

int widths(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    auto db = openDatabase();
    // The owner's shared setup on the test card: TITLE, ARTIST 200, BPM 100,
    // KEY 50; # hidden at 30; ALBUM and PREVIEW never shown (0); DURATION
    // never shown (20, after build F's start-up write).
    const QString preset = MixpiSharedColumns::serialize({{"title", false, 160}, {"artist", false, 200},
            {"bpm", false, 100}, {"key", false, 50}, {"position", true, 30}, {"album", true, 0},
            {"preview", true, 0}, {"duration", true, 20}});
    {
        QFile file(path);
        file.open(QIODevice::WriteOnly);
        file.write("\n[Library]\nSharedColumns " + preset.toLatin1() + "\n\n[Test]\nexisting 1\n");
    }
    UserSettingsPointer pConfig = makeConfig(directory);
    mixxx::ConfigAutosave autosave(pConfig);
    autosave.start();

    TrackCollectionManager manager;
    Library library(&manager);
    RecordingManager recording;
    BrowseTableModel browse(nullptr, &manager, &recording);
    ProxyTrackModel folder(&browse, true);
    NamedModel tracks(db, "mixxx.db.model.library", kLibraryNames, kLibraryLabels);
    NamedModel playlist(db, "mixxx.db.model.playlist", kPlaylistNames, kPlaylistLabels);

    QWidget window;
    window.resize(800, 480);
    window.show();
    auto view = std::make_unique<View>(pConfig, &library, &window);
    view->resize(700, 300);
    view->show();
    setViewport(view.get(), 776);

    // N1: opening lists, as at a start, is no change by the user.
    view->loadTrackModel(&tracks);
    view->loadTrackModel(&playlist);
    view->loadTrackModel(&folder);
    view->loadTrackModel(&tracks);
    spin(1500);
    observeSaved("after the lists opened", path);
    require(saves == 0 && fileValue(path) == preset,
            "start: opening lists writes nothing to the shared setup (note N1)");
    auto* header = view->header();
    observe("This Pi > Tracks", header);
    require(widthOf(header, "bpm") == 100 && widthOf(header, "key") == 50,
            "start: This Pi > Tracks shows BPM 100 and KEY 50");

    // Repro A: KEY hidden in Arrange columns, then shown again 1.5 s later.
    QListWidget* list = arrangeList(header);
    require(arrange(list, "Key", false) && savedAs(path, "key", true, 50),
            "repro A: KEY hidden in Arrange columns is saved hidden at 50 px");
    spin(1500);
    arrange(list, "Key", true);
    closeArrange(list);
    observe("KEY shown again in Arrange columns", header);
    require(widthOf(header, "key") == 50, "repro A: KEY shown again in Arrange columns is 50 px, not 160");
    require(savedAs(path, "key", false, 50), "repro A: the saved line has KEY shown at 50 px");

    // The same in one list, through the header menu: BPM.
    choose(header, "BPM", false);
    require(savedAs(path, "bpm", true, 100), "BPM hidden from the header menu is saved hidden at 100 px");
    choose(header, "BPM", true);
    observe("BPM shown again from the header menu", header);
    require(widthOf(header, "bpm") == 100, "BPM shown again from the header menu is 100 px, not 160");
    require(savedAs(path, "bpm", false, 100), "the saved line has BPM shown at 100 px");

    // # in the playlist: its saved 30 px, shown, hidden and shown again.
    view->loadTrackModel(&playlist);
    header = view->header();
    choose(header, "#", true);
    const int numberFirst = widthOf(header, "position");
    choose(header, "#", false);
    require(savedAs(path, "position", true, 30), "# hidden again is saved hidden at 30 px");
    list = arrangeList(header);
    arrange(list, "#", true);
    closeArrange(list);
    observe("# shown again", header);
    require(numberFirst == 30 && widthOf(header, "position") == 30,
            "# shown from the header menu and from Arrange columns is 30 px, not 160");
    require(savedAs(path, "position", false, 30), "the saved line has # shown at 30 px");

    // Repro B: hidden in one list, shown in another.
    view->loadTrackModel(&tracks);
    header = view->header();
    list = arrangeList(header);
    arrange(list, "BPM", false);
    closeArrange(list);
    require(savedAs(path, "bpm", true, 100), "repro B: BPM hidden in This Pi > Tracks, saved at 100 px");
    view->loadTrackModel(&playlist);
    header = view->header();
    require(header->isSectionHidden(columnNamed(header, "bpm")), "repro B: BPM is hidden in the playlist");
    list = arrangeList(header);
    arrange(list, "BPM", true);
    closeArrange(list);
    observe("BPM shown in the playlist", header);
    require(widthOf(header, "bpm") == 100, "repro B: BPM shown in the playlist is 100 px, not 160");
    require(savedAs(path, "bpm", false, 100), "repro B: the saved line has BPM shown at 100 px");
    choose(header, "Key", false);
    require(savedAs(path, "key", true, 50), "repro B: KEY hidden in the playlist, saved at 50 px");
    view->loadTrackModel(&folder);
    header = view->header();
    QCheckBox* folderKey = nullptr;
    for (auto* choice : header->findChildren<QCheckBox*>()) {
        if (choice->text().compare(QStringLiteral("Key"), Qt::CaseInsensitive) == 0) {
            folderKey = choice;
        }
    }
    if (folderKey) {
        folderKey->setChecked(true);
        QApplication::processEvents();
    }
    observe("KEY shown in a folder", header);
    require(folderKey && widthOf(header, "key") == 50,
            "repro B: KEY shown from a folder's header menu is 50 px, not 160");
    view->loadTrackModel(&tracks);
    header = view->header();
    observe("This Pi > Tracks after repro B", header);
    require(widthOf(header, "bpm") == 100 && widthOf(header, "key") == 50,
            "repro B: This Pi > Tracks has BPM 100 and KEY 50 again");
    {
        // The autosave writes within a second of the last change.
        const bool saved = waitFor(1000, [&] {
            const QString value = fileValue(path);
            const auto bpm = sharedColumn(value, "bpm");
            const auto key = sharedColumn(value, "key");
            const auto number = sharedColumn(value, "position");
            return !bpm.hidden && bpm.size == 100 && !key.hidden && key.size == 50 && !number.hidden &&
                    number.size == 30;
        });
        observeSaved("after repro B", path);
        require(saved, "the saved line keeps the old widths after every show (BPM 100, KEY 50, # 30)");
    }

    // A column never shown keeps build B's readable width.
    choose(header, "Album", true);
    list = arrangeList(header);
    arrange(list, "Duration", true);
    closeArrange(list);
    observe("ALBUM and DURATION shown for the first time", header);
    require(widthOf(header, "album") == 160 && widthOf(header, "duration") == 160,
            "a column never shown (saved 0 or 20 px) gets build B's 160 px");
    require(savedAs(path, "album", false, 160) && savedAs(path, "duration", false, 160),
            "... and that width is saved");

    view.reset();
    autosave.stop();
    require(asserts == 0, "widths: no DEBUG_ASSERT fired");
    std::cout << "FAILURES " << failures << std::endl;
    return failures ? 1 : 0;
}

int killMode(const QString& directory) {
    auto db = openDatabase();
    UserSettingsPointer pConfig = makeConfig(directory);
    mixxx::ConfigAutosave autosave(pConfig);
    autosave.start();
    TrackCollectionManager manager;
    Library library(&manager);
    NamedModel tracks(db, "mixxx.db.model.library", kLibraryNames, kLibraryLabels);
    QWidget window;
    window.resize(800, 480);
    window.show();
    View view(pConfig, &library, &window);
    view.resize(700, 300);
    view.show();
    setViewport(&view, 776);
    view.loadTrackModel(&tracks);
    resizeByDrag(view.header(), QStringLiteral("artist"), 50, 10);
    moveByDrag(view.header(), QStringLiteral("key"), 0);
    std::cout << "CHANGED " << widthOf(view.header(), "artist") << ' '
              << shownOrder(view.header()).join(',').toStdString() << std::endl;
    spin(60000);
    return 1;
}

int afterKill(const QString& directory) {
    const QString path = directory + QStringLiteral("/mixxx.cfg");
    auto db = openDatabase();
    std::cout << "FILE_VALUE " << fileValue(path).toStdString() << std::endl;
    UserSettingsPointer pConfig = makeConfig(directory);
    TrackCollectionManager manager;
    Library library(&manager);
    NamedModel playlist(db, "mixxx.db.model.playlist", kPlaylistNames, kPlaylistLabels);
    QWidget window;
    window.resize(800, 480);
    window.show();
    View view(pConfig, &library, &window);
    view.resize(700, 300);
    view.show();
    setViewport(&view, 776);
    view.loadTrackModel(&playlist);
    std::cout << "RESTORED " << widthOf(view.header(), "artist") << ' '
              << shownOrder(view.header()).join(',').toStdString() << std::endl;
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    qInstallMessageHandler([](QtMsgType type, const QMessageLogContext&, const QString& message) {
        QMutexLocker locker(&messagesMutex);
        if (type == QtCriticalMsg && message.startsWith(QStringLiteral("DEBUG ASSERT"))) {
            ++asserts;
        }
        if (message.startsWith(QStringLiteral("ConfigAutosave: saved"))) {
            ++saves;
        }
        std::cerr << message.toStdString() << std::endl;
    });
    QApplication app(argc, argv);
    if (argc < 3) {
        std::cerr << "usage: shared-columns-test MODE DIRECTORY" << std::endl;
        return 2;
    }
    const QString mode = QString::fromLocal8Bit(argv[1]);
    const QString directory = QString::fromLocal8Bit(argv[2]);
    if (mode == QStringLiteral("checks")) {
        return checks(directory);
    }
    if (mode == QStringLiteral("widths")) {
        return widths(directory);
    }
    if (mode == QStringLiteral("kill")) {
        return killMode(directory);
    }
    if (mode == QStringLiteral("after-kill")) {
        return afterKill(directory);
    }
    return 2;
}
