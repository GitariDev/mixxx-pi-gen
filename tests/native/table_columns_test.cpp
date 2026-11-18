// F-7/F-8: Browse defaults, stretch and header persistence through the real
// WTrackTableViewHeader, ProxyTrackModel, BrowseTableModel and SettingsDAO.
// Build D (mixxx-table-fit-media-open.patch): the columns fit the narrowed
// table (Sources open, x 0-480) through the shipped MixpiTableFit.
#include <QApplication>
#include <QCheckBox>
#include <QDialog>
#include <QDir>
#include <QFile>
#include <QFontDatabase>
#include <QListWidget>
#include <QSqlDatabase>
#include <QSqlQuery>
#include <QStandardItemModel>
#include <QScrollBar>
#include <QTableView>
#include <iostream>

#include "library/browse/browsetablemodel.h"
#include "library/proxytrackmodel.h"
#include "library/trackcollectionmanager.h"
#include "proto/headers.pb.h"
#include "recording/recordingmanager.h"
#include "widget/wtracktableviewheader.h"
#if __has_include("widget/mixpitablefit.h")
#include "widget/mixpitablefit.h"
#define MIXPI_TABLE_FIT 1
#endif

int failures = 0;
int asserts = 0;
void require(bool condition, const char* name) {
    std::cout << (condition ? "PASS " : "FAIL ") << name << std::endl;
    failures += condition ? 0 : 1;
}

// Library-style model: has SQL field names, like BaseTrackTableModel.
class LibraryLikeModel final : public QStandardItemModel, public TrackModel {
  public:
    explicit LibraryLikeModel(const QSqlDatabase& db)
            : QStandardItemModel(0, 6), TrackModel(db, "mixxx.db.model.librarylike") {
        const QStringList names{"preview", "artist", "title", "album", "bpm", "key"};
        setHorizontalHeaderLabels({"Preview", "Artist", "Title", "Album", "BPM", "Key"});
        for (int column = 0; column < names.size(); ++column) {
            setHeaderData(column, Qt::Horizontal, names[column], kHeaderNameRole);
        }
    }
    int fieldIndex(const QString& name) const override {
        return QStringList({"preview", "artist", "title", "album", "bpm", "key"}).indexOf(name);
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
    bool isColumnHiddenByDefault(int column) override { return column == 0; }
    SortColumnId sortColumnIdFromColumnIndex(int) const override { return SortColumnId::Invalid; }
    int columnIndexFromSortColumnId(SortColumnId) const override { return -1; }
    QString modelKey(bool) const override { return QStringLiteral("librarylike"); }
    bool updateTrackGenre(Track*, const QString&) const override { return false; }
};

// The view part of WTrackTableView::loadTrackModel that swaps headers: the
// included block is copied verbatim from the patched wtracktableview.cpp.
// With the fit (build D) the view calls MixpiTableFit where WTrackTableView
// does: after a resize, at the end of loadTrackModel, and around the saves.
class View : public QTableView {
  public:
    bool m_sorting = true;
#ifdef MIXPI_TABLE_FIT
    MixpiTableFit m_columnFit{this, [](QHeaderView* pHeader) {
                                  auto* pTrackHeader = qobject_cast<WTrackTableViewHeader*>(pHeader);
                                  return pTrackHeader ? pTrackHeader->stretchColumnIndex() : -1;
                              }};
#endif
    void loadTrackModel(QAbstractItemModel* pNewModel) {
#include "header_swap.inc"
        show();
#ifdef MIXPI_TABLE_FIT
        m_columnFit.fit();
#endif
        QApplication::processEvents();
    }
    ~View() override {
        // WTrackTableView::~WTrackTableView saves the header state as well.
        if (auto* pHeader = qobject_cast<WTrackTableViewHeader*>(horizontalHeader())) {
#ifdef MIXPI_TABLE_FIT
            m_columnFit.withFullWidths(pHeader, [pHeader] { pHeader->saveHeaderState(); });
#else
            pHeader->saveHeaderState();
#endif
        }
    }
    WTrackTableViewHeader* header() const {
        return qobject_cast<WTrackTableViewHeader*>(horizontalHeader());
    }

  protected:
    void resizeEvent(QResizeEvent* event) override {
        QTableView::resizeEvent(event);
#ifdef MIXPI_TABLE_FIT
        m_columnFit.fit();
#endif
    }
};

QString settingsRow(const QString& name) {
    QSqlQuery query(QSqlDatabase::database(QStringLiteral("table-columns")));
    query.prepare(QStringLiteral("SELECT value FROM settings WHERE name=:name"));
    query.bindValue(QStringLiteral(":name"), name);
    if (query.exec() && query.first()) {
        return query.value(0).toString();
    }
    return {};
}

QList<int> visibleOrder(const QHeaderView* header) {
    QList<int> order;
    for (int visual = 0; visual < header->count(); ++visual) {
        const int logical = header->logicalIndex(visual);
        if (!header->isSectionHidden(logical)) {
            order.append(logical);
        }
    }
    return order;
}

int visibleWidth(const QHeaderView* header) {
    int width = 0;
    for (int column = 0; column < header->count(); ++column) {
        width += header->isSectionHidden(column) ? 0 : header->sectionSize(column);
    }
    return width;
}

// The column gets exactly the width the other visible columns leave.
bool takesRest(const QHeaderView* header, int column) {
    int others = 0;
    for (int section = 0; section < header->count(); ++section) {
        if (section != column && !header->isSectionHidden(section)) {
            others += header->sectionSize(section);
        }
    }
    std::cout << "OBSERVE column " << column << " width " << header->sectionSize(column)
              << " others " << others << " header viewport " << header->viewport()->width()
              << " stretchLast " << header->stretchLastSection() << std::endl;
    return !header->stretchLastSection() && !header->isSectionHidden(column) &&
            header->sectionSize(column) == header->viewport()->width() - others;
}

void printOrder(const char* label, const QHeaderView* header) {
    std::cout << "OBSERVE " << label << ":";
    for (int column : visibleOrder(header)) {
        std::cout << ' ' << header->model()->headerData(column, Qt::Horizontal).toString().toStdString();
    }
    std::cout << std::endl;
}

QDialog* arrange(View* view) {
    view->header()->showColumnArrangement();
    QApplication::processEvents();
    return view->header()->findChild<QDialog*>(QStringLiteral("MixpiColumnArrangement"));
}

void check(QListWidget* list, const QString& title, bool checked) {
    for (int row = 0; row < list->count(); ++row) {
        if (list->item(row)->text() == title) {
            list->item(row)->setCheckState(checked ? Qt::Checked : Qt::Unchecked);
        }
    }
}

// A column's size in a saved header row (-1 if absent).
int savedSize(const QString& row, int column) {
    mixxx::library::HeaderViewState state;
    const QByteArray bytes = QByteArray::fromBase64(row.toLatin1());
    state.ParseFromArray(bytes.constData(), static_cast<int>(bytes.size()));
    for (const auto& entry : state.header_state()) {
        if (entry.logical_index() == column) {
            return entry.size();
        }
    }
    return -1;
}

void setViewport(View* view, int width) {
    view->resize(view->width() - view->viewport()->width() + width, 300);
    QApplication::processEvents();
}

// Build D (agreed UI s5, spec 2a; m-sources-top.png): with Sources open the
// table is x 0-480, a 456 px viewport beside its 24 px scroll bar. TITLE,
// ARTIST, BPM and KEY all show with no sideways bar; at the full width
// (776 px) every column has its saved size back exactly, and the fitted
// sizes are never saved.
void fitChecks(LibraryLikeModel* library, ProxyTrackModel* proxy) {
    constexpr int kFull = 776;
    constexpr int kNarrow = 456;
    constexpr int kArtist = 1, kTitle = 2, kAlbum = 3, kBpm = 4, kKey = 5;
    const QString row = QStringLiteral("mixxx.db.model.librarylike.header_state_pb");
    // The table sits in a window that keeps its width, as in the skin; 776
    // px is the widest the table is (its full width).
    QWidget window;
    window.resize(800, 480);
    window.show();
    auto view = std::make_unique<View>();
    view->setParent(&window);
    view->resize(700, 300);
    view->loadTrackModel(library);
    setViewport(view.get(), kFull);
    auto* header = view->header();
    // The owner's Tracks columns on build C (k09-tracks.png): TITLE, ARTIST
    // 200, BPM 98, KEY 52.
    header->setSectionHidden(kAlbum, true);
    header->moveSection(header->visualIndex(kTitle), 0);
    header->resizeSection(kArtist, 200);
    header->resizeSection(kBpm, 98);
    header->resizeSection(kKey, 52);
    QApplication::processEvents();
    const int fullTitle = header->sectionSize(kTitle);
    std::cout << "OBSERVE full width: title " << fullTitle << " artist " << header->sectionSize(kArtist)
              << " bpm " << header->sectionSize(kBpm) << " key " << header->sectionSize(kKey) << std::endl;
    require(takesRest(header, kTitle) && visibleWidth(header) == kFull,
            "fit: at 776 px Title takes the rest and the columns fill the table");

    setViewport(view.get(), kNarrow);
    std::cout << "OBSERVE narrowed: title " << header->sectionSize(kTitle) << " artist "
              << header->sectionSize(kArtist) << " bpm " << header->sectionSize(kBpm) << " key "
              << header->sectionSize(kKey) << " sideways range " << view->horizontalScrollBar()->maximum()
              << std::endl;
    require(visibleWidth(header) == kNarrow,
            "fit: at 456 px TITLE, ARTIST, BPM and KEY fill the narrowed table exactly");
    require(view->horizontalScrollBar()->maximum() == 0, "fit: no sideways scroll bar in the narrowed table");
    require(header->sectionSize(kTitle) >= kNarrow / 2 && header->sectionSize(kKey) >= 40 &&
                    header->sectionSize(kArtist) > header->sectionSize(kBpm) &&
                    header->sectionSize(kBpm) > header->sectionSize(kKey),
            "fit: TITLE takes half, the others keep their order of size, none under 40 px");
    require(view->textElideMode() == Qt::ElideRight, "fit: cut text ends with an ellipsis");

    // A list switch while narrowed saves the full-width sizes.
    view->loadTrackModel(proxy);
    const QString saved = settingsRow(row);
    std::cout << "OBSERVE saved while narrowed: artist " << savedSize(saved, kArtist) << " bpm "
              << savedSize(saved, kBpm) << " key " << savedSize(saved, kKey) << std::endl;
    require(savedSize(saved, kArtist) == 200 && savedSize(saved, kBpm) == 98 && savedSize(saved, kKey) == 52,
            "fit: a list switch while narrowed saves the full-width sizes");
    view->loadTrackModel(library);
    header = view->header();
    require(visibleWidth(header) == kNarrow && view->horizontalScrollBar()->maximum() == 0,
            "fit: the list opened while narrowed fits too");

    setViewport(view.get(), kFull);
    std::cout << "OBSERVE widened: title " << header->sectionSize(kTitle) << " artist "
              << header->sectionSize(kArtist) << " bpm " << header->sectionSize(kBpm) << " key "
              << header->sectionSize(kKey) << std::endl;
    require(header->sectionSize(kArtist) == 200 && header->sectionSize(kBpm) == 98 &&
                    header->sectionSize(kKey) == 52 && header->sectionSize(kTitle) == fullTitle &&
                    takesRest(header, kTitle),
            "fit: back at 776 px every column has its full-width size exactly");

    // Columns the user made wider than the full table still scroll there
    // (build B's table-columns behaviour), and come back after a narrowing.
    header->resizeSection(kArtist, 600);
    QApplication::processEvents();
    setViewport(view.get(), kFull);
    require(header->sectionSize(kArtist) == 600 && header->sectionSize(kTitle) == 160,
            "fit: at the full width nothing is fitted (wide columns scroll as before)");
    setViewport(view.get(), kNarrow);
    require(visibleWidth(header) == kNarrow, "fit: the wide columns fit the narrowed table");
    setViewport(view.get(), kFull);
    require(header->sectionSize(kArtist) == 600, "fit: the wide column has its 600 px back at the full width");
    header->resizeSection(kArtist, 200);
    QApplication::processEvents();

    // Quit while narrowed: the full-width sizes are saved.
    setViewport(view.get(), kNarrow);
    view.reset();
    const QString quit = settingsRow(row);
    require(savedSize(quit, kArtist) == 200 && savedSize(quit, kBpm) == 98 && savedSize(quit, kKey) == 52,
            "fit: quitting while narrowed saves the full-width sizes");
}

QString renderStyle() {
    QString style;
    for (const auto& path : qEnvironmentVariable("MIXPI_SKIN_QSS").split(':', Qt::SkipEmptyParts)) {
        QFile file(path);
        if (file.open(QIODevice::ReadOnly)) {
            style += QString::fromUtf8(file.readAll()) + QLatin1Char('\n');
        }
    }
    return style;
}

// 800x480 renders of the table with the real stylesheets, where the Tracks
// screen has it (y 100-352): at 800 px, and at x 0-480 with Sources open
// (m-sources-top.png; the menu itself is not part of this fixture).
void renderFit(LibraryLikeModel* library, const QString& directory) {
    const QStringList rows[] = {
            {"Your Body", "Biscits", "-", "-"},
            {"YOU'RE THE ONE", "KAYTRANADA / Syd", "118.0", "Am"},
            {"Yo Soy Abacua", "Willie Rosario and His Orchestra", "-", "C"},
            {"Yiriyiribon - Mambo Afro", "Beny More / Orquesta Aragon", "163.5", "Gm"},
            {"Yetikimt Abeba", "The Roha Band", "-", "Eb"},
            {"Yetikimt Abeba", "The Roha Band", "-", "Eb"}};
    for (const auto& row : rows) {
        QList<QStandardItem*> items;
        for (const auto& text : {QString(), row[1], row[0], QString(), row[2], row[3]}) {
            items.append(new QStandardItem(text));
        }
        library->appendRow(items);
    }
    QDir().mkpath(directory);
    for (const int width : {800, 480}) {
        QWidget window;
        window.setObjectName(QStringLiteral("MixpiRenderRoot"));
        window.setStyleSheet(renderStyle() +
                QStringLiteral("\n#MixpiRenderRoot { background-color: #0d1014; }"));
        window.resize(800, 480);
        auto* wrapper = new QWidget(&window);
        wrapper->setObjectName(QStringLiteral("LibraryWrapper"));
        auto* view = new View;
        view->setParent(wrapper);
        view->verticalHeader()->hide(); // as WLibraryTableView
        view->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOn);
        // Shown at the full width first, then narrowed when Sources opens.
        wrapper->setGeometry(0, 100, 800, 252);
        view->setGeometry(0, 0, 800, 252);
        window.show();
        view->loadTrackModel(library);
        // The fixture view leaves the swapped header hidden; Mixxx shows it.
        view->horizontalHeader()->show();
        QApplication::processEvents();
        wrapper->setGeometry(0, 100, width, 252);
        view->setGeometry(0, 0, width, 252);
        QApplication::processEvents();
        const QString name = directory + QStringLiteral("/table-%1.png").arg(width);
        std::cout << "OBSERVE render " << name.toStdString() << " viewport " << view->viewport()->width()
                  << " sideways range " << view->horizontalScrollBar()->maximum() << " header shown "
                  << view->horizontalHeader()->isVisible() << " height " << view->horizontalHeader()->height()
                  << std::endl;
        for (int column : visibleOrder(view->header())) {
            std::cout << "OBSERVE render column "
                      << library->headerData(column, Qt::Horizontal).toString().toStdString() << " width "
                      << view->header()->sectionSize(column)
#ifdef MIXPI_TABLE_FIT
                      << " label " << MixpiTableFit::labelWidth(view->header(), column, view->font())
#endif
                      << " hint " << view->header()->sectionSizeHint(column) << " text "
                      << view->header()->fontMetrics().horizontalAdvance(
                                 library->headerData(column, Qt::Horizontal).toString())
                      << std::endl;
        }
        require(window.grab().save(name), "render: the table at its width is saved");
        if (width == 480) {
            require(view->horizontalScrollBar()->maximum() == 0,
                    "render: inside the 800 px screen, the 480 px table fits with no sideways bar");
#ifdef MIXPI_TABLE_FIT
            bool labels = true;
            for (int column : visibleOrder(view->header())) {
                labels = labels &&
                        view->header()->sectionSize(column) >=
                                MixpiTableFit::labelWidth(view->header(), column, view->font());
            }
            require(labels, "render: every header label fits in the narrowed table");
#endif
        }
        delete view;
    }
}

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    const bool baseline = argc > 1 && QString::fromUtf8(argv[1]) == "baseline";
    qInstallMessageHandler([](QtMsgType type, const QMessageLogContext&, const QString& message) {
        if (type == QtCriticalMsg && message.startsWith(QStringLiteral("DEBUG ASSERT"))) {
            ++asserts;
        }
        std::cerr << message.toStdString() << std::endl;
    });
    auto db = QSqlDatabase::addDatabase(QStringLiteral("QSQLITE"), QStringLiteral("table-columns"));
    db.setDatabaseName(QStringLiteral(":memory:"));
    require(db.open(), "sqlite settings database opens");
    QSqlQuery(db).exec(QStringLiteral(
            "CREATE TABLE settings (name TEXT UNIQUE NOT NULL, value TEXT, "
            "locked INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0)"));
    const QString browseRow = QStringLiteral("mixxx.db.model.browse.header_state_pb");

    TrackCollectionManager manager;
    RecordingManager recording;
    BrowseTableModel browse(nullptr, &manager, &recording);
    ProxyTrackModel proxy(&browse, true);
    LibraryLikeModel library(db);

    auto view = std::make_unique<View>();
    view->resize(770 + view->frameWidth() * 2 + 40, 300);
    view->show();
    view->loadTrackModel(&library);
    view->resize(view->width() - view->viewport()->width() + 770, 300);
    QApplication::processEvents();
    require(view->viewport()->width() == 770, "fixture viewport is 770 px");
    const int width = view->viewport()->width();

    // F-7 library: Title stretches and the visible sections fill the viewport.
    auto* header = view->header();
    require(takesRest(header, 2), "library Title column takes the free width");
    require(visibleWidth(header) == width, "library visible sections fill 770 px with Title");
    {
        auto* dialog = arrange(view.get());
        check(dialog->findChild<QListWidget*>(), QStringLiteral("Title"), false);
        dialog->close();
    }
    QApplication::processEvents();
    require(header->isSectionHidden(2) && header->stretchLastSection(),
            "library falls back to stretchLastSection without Title");
    require(visibleWidth(header) == width, "library visible sections fill 770 px without Title");
    {
        auto* dialog = arrange(view.get());
        check(dialog->findChild<QListWidget*>(), QStringLiteral("Title"), true);
        dialog->close();
    }
    QApplication::processEvents();
    require(takesRest(header, 2) && visibleWidth(header) == width,
            "library Title takes the free width again when shown");
    header->resizeSection(1, 700);
    QApplication::processEvents();
    require(header->sectionSize(2) == 160 && // LibraryInterface::kStretchColumnMinimumWidth
                    visibleWidth(header) > width,
            "wide other columns scroll instead of squeezing Title below 160 px");
    header->resizeSection(1, 100);
    QApplication::processEvents();
    require(takesRest(header, 2) && visibleWidth(header) == width,
            "Title takes the free width again after another column narrows");

    // F-8 step 1: Browse through the proxy, change the header, switch model,
    // read the settings row.
    view->loadTrackModel(&proxy);
    header = view->header();
    printOrder("browse first visit", header);
    require(visibleOrder(header) == QList<int>({COLUMN_FILENAME, COLUMN_BPM, COLUMN_KEY, COLUMN_DURATION}),
            "Browse default columns are Filename BPM Key Duration");
    require(header->isSectionHidden(COLUMN_PREVIEW), "Browse Preview column hidden by default");
    require(takesRest(header, COLUMN_FILENAME), "Browse Filename column takes the free width");
    require(visibleWidth(header) == width, "Browse default columns fill 770 px");

    // A direct header change, then a model switch: the switch saves the state.
    header->moveSection(header->visualIndex(COLUMN_FILENAME), header->count() - 1);
    const QList<int> moved = visibleOrder(header);
    printOrder("browse after moving Filename last", header);
    view->loadTrackModel(&library);
    const QString afterSwitch = settingsRow(browseRow);
    std::cout << "OBSERVE browse row after model switch: "
              << (afterSwitch.isEmpty() ? "absent" : "present") << std::endl;
    require(!afterSwitch.isEmpty(), "model switch writes mixxx.db.model.browse.header_state_pb");
    mixxx::library::HeaderViewState saved;
    const QByteArray bytes = QByteArray::fromBase64(afterSwitch.toLatin1());
    saved.ParseFromArray(bytes.constData(), static_cast<int>(bytes.size()));
    int unnamed = 0;
    for (const auto& state : saved.header_state()) {
        unnamed += state.column_name().empty() ? 1 : 0;
    }
    std::cout << "OBSERVE saved browse entries " << saved.header_state_size()
              << " without column name " << unnamed << std::endl;
    require(saved.header_state_size() == NUM_COLUMNS && unnamed == 0,
            "every saved Browse column has a stable name");
    view->loadTrackModel(&proxy);
    header = view->header();
    printOrder("browse after switch back", header);
    require(visibleOrder(header) == moved, "Browse order survives a model switch and a switch back");

    // Arrange (add Artist), switch model, switch back.
    {
        auto* dialog = arrange(view.get());
        check(dialog->findChild<QListWidget*>(), QStringLiteral("Artist"), true);
        dialog->close();
    }
    QApplication::processEvents();
    const QList<int> arranged = visibleOrder(header);
    printOrder("browse after Arrange adds Artist", header);
    require(arranged.contains(COLUMN_ARTIST), "Arrange shows Artist in Browse");
    // F-8 (acceptance finding 4): the added column was 26 px, only "A" showed.
    std::cout << "OBSERVE Artist width after Arrange " << header->sectionSize(COLUMN_ARTIST)
              << " px" << std::endl;
    require(header->sectionSize(COLUMN_ARTIST) >= 160, // LibraryInterface::kStretchColumnMinimumWidth
            "a column added in Arrange gets a readable width (at least 160 px)");
    require(!settingsRow(browseRow).isEmpty(), "Arrange change writes the Browse settings row");
    require(visibleWidth(header) == width, "Browse columns still fill 770 px after Arrange");
    view->loadTrackModel(&library);
    view->loadTrackModel(&proxy);
    header = view->header();
    printOrder("browse after Arrange and switch back", header);
    require(visibleOrder(header) == arranged, "Arrange order survives a model switch and a switch back");

    // A deliberate width is saved and restored, not reset to the floor.
    header->resizeSection(COLUMN_ARTIST, 210);
    QApplication::processEvents();
    require(header->sectionSize(COLUMN_ARTIST) == 210 && visibleWidth(header) == width,
            "Artist resized to 210 px; Filename still takes the rest");

    // Restart: a new view restores the saved row.
    view.reset();
    view = std::make_unique<View>();
    view->resize(770 + 40, 300);
    view->show();
    view->loadTrackModel(&proxy);
    view->resize(view->width() - view->viewport()->width() + 770, 300);
    QApplication::processEvents();
    header = view->header();
    printOrder("browse after restart", header);
    require(visibleOrder(header) == arranged, "Arrange order survives a restart");
    require(takesRest(header, COLUMN_FILENAME) && visibleWidth(header) == width,
            "restored Browse columns stretch Filename and fill 770 px");
    std::cout << "OBSERVE Artist width after restart " << header->sectionSize(COLUMN_ARTIST)
              << " px" << std::endl;
    require(header->sectionSize(COLUMN_ARTIST) == 210, "saved Artist width (210 px) is restored after a restart");
    {
        auto* dialog = arrange(view.get());
        check(dialog->findChild<QListWidget*>(), QStringLiteral("Artist"), false);
        check(dialog->findChild<QListWidget*>(), QStringLiteral("Artist"), true);
        dialog->close();
    }
    QApplication::processEvents();
    require(header->sectionSize(COLUMN_ARTIST) == 210,
            "hiding and showing Artist again keeps its 210 px width");
    // The header context menu path (showOrHideColumn) uses the same floor.
    QCheckBox* albumChoice = nullptr;
    for (auto* choice : header->findChildren<QCheckBox*>()) {
        if (choice->text() == QStringLiteral("Album")) {
            albumChoice = choice;
        }
    }
    require(albumChoice && !albumChoice->isChecked(), "header menu offers hidden Album");
    if (albumChoice) {
        albumChoice->setChecked(true);
        QApplication::processEvents();
        std::cout << "OBSERVE Album width from the header menu " << header->sectionSize(COLUMN_ALBUM)
                  << " px" << std::endl;
        require(!header->isSectionHidden(COLUMN_ALBUM) && header->sectionSize(COLUMN_ALBUM) >= 160,
                "a column shown from the header menu gets a readable width");
        albumChoice->setChecked(false);
        QApplication::processEvents();
    }
    require(visibleWidth(header) == width, "Browse columns fill 770 px after the menu changes");

    // Hide Filename: the fallback still fills the viewport.
    {
        auto* dialog = arrange(view.get());
        check(dialog->findChild<QListWidget*>(), QStringLiteral("Filename"), false);
        dialog->close();
    }
    QApplication::processEvents();
    require(header->isSectionHidden(COLUMN_FILENAME) && visibleWidth(header) == width,
            "Browse falls back to stretchLastSection without Filename");

    // A row saved before the fix (no column names) still restores by its
    // saved logical indexes, including the last visual column.
    {
        mixxx::library::HeaderViewState old;
        const QList<int> oldOrder{COLUMN_ARTIST, COLUMN_BPM, COLUMN_FILENAME};
        int visual = 0;
        for (int column : oldOrder) {
            auto* state = old.add_header_state();
            state->set_logical_index(column);
            state->set_visual_index(visual++);
            state->set_hidden(false);
            state->set_size(120);
        }
        for (int column = 0; column < NUM_COLUMNS; ++column) {
            if (!oldOrder.contains(column)) {
                auto* state = old.add_header_state();
                state->set_logical_index(column);
                state->set_visual_index(visual++);
                state->set_hidden(true);
                state->set_size(100);
            }
        }
        QByteArray array(static_cast<int>(old.ByteSizeLong()), '\0');
        old.SerializeToArray(array.data(), static_cast<int>(array.size()));
        view.reset();
        QSqlQuery query(db);
        query.prepare(QStringLiteral("REPLACE INTO settings (name, value) VALUES (:name, :value)"));
        query.bindValue(QStringLiteral(":name"), browseRow);
        query.bindValue(QStringLiteral(":value"), QString(array.toBase64()));
        require(query.exec(), "unnamed pre-fix Browse row stored");
        view = std::make_unique<View>();
        view->resize(810, 300);
        view->loadTrackModel(&proxy);
        printOrder("browse from an unnamed pre-fix row", view->header());
        require(visibleOrder(view->header()) == oldOrder,
                "unnamed pre-fix Browse row restores every saved column");
    }
    if (!baseline) {
        fitChecks(&library, &proxy);
        for (const auto& font : qEnvironmentVariable("MIXPI_FONTS").split(':', Qt::SkipEmptyParts)) {
            QFontDatabase::addApplicationFont(font);
        }
        renderFit(&library, qEnvironmentVariableIsSet("MIXPI_TABLE_RENDERS")
                        ? qEnvironmentVariable("MIXPI_TABLE_RENDERS")
                        : QDir::tempPath() + QStringLiteral("/mixpi-table-fit-renders"));
    }
    require(asserts == 0, "no DEBUG_ASSERT fired");
    std::cout << "FAILURES " << failures << (baseline ? " (baseline)" : "") << std::endl;
    return failures ? 1 : 0;
}
