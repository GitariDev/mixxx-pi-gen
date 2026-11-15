#include <QApplication>
#include <QMouseEvent>
#include <QScrollBar>
#include <QStandardItemModel>
#include <QTableView>
#include <iostream>

#include "widget/libraryinterface.h"
#include "widget/touchsourcenavigation.h"

int failures = 0;
void require(bool condition, const char* name) {
    std::cout << (condition ? "PASS " : "FAIL ") << name << std::endl;
    failures += condition ? 0 : 1;
}

void click(QWidget* widget, QPoint position) {
    const QPoint global = widget->mapToGlobal(position);
    QMouseEvent press(QEvent::MouseButtonPress, position, global,
            Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    QApplication::sendEvent(widget, &press);
    QMouseEvent release(QEvent::MouseButtonRelease, position, global,
            Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    QApplication::sendEvent(widget, &release);
    QApplication::processEvents();
}

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    const bool baseline = argc > 1 && QString::fromUtf8(argv[1]) == "baseline";
    const bool holdout = argc > 1 && QString::fromUtf8(argv[1]) == "holdout";
    LibraryInterface::VisibilityMenu sources;
    int changes = 0;
    QList<QCheckBox*> choices;
    if (baseline) {
        auto* action = sources.addAction("Tracks");
        action->setCheckable(true);
        action->setChecked(true);
        QObject::connect(action, &QAction::triggered, [&changes] { ++changes; });
    } else {
        for (const auto& title : {QString("Tracks"), QString("Browse"), QString("Playlists")}) {
            auto* choice = LibraryInterface::addVisibilityChoice(&sources, title,
                    true, [&changes, &choices](bool) {
                        ++changes;
                        LibraryInterface::protectLastVisible(choices);
                    });
            choices.append(choice);
        }
    }
    sources.addAction("Close", &sources, &QMenu::close);
    sources.popup(QPoint(30, 30));
    application.processEvents();
    if (baseline) {
        click(&sources, sources.actionGeometry(sources.actions().first()).center());
    } else {
        click(choices[0], QPoint(8, choices[0]->height() / 2));
    }
    require(changes == 1, "source preference receives click");
    require(sources.isVisible(), "source chooser stays open after first change");
    if (!baseline) {
        click(choices[1], QPoint(8, choices[1]->height() / 2));
        require(changes == 2 && sources.isVisible(), "multiple source changes in one popup");
        require(!choices[2]->isEnabled(), "last visible source protected dynamically");
        sources.setActiveAction(sources.actions()[2]);
        QKeyEvent protectedEnter(QEvent::KeyPress, Qt::Key_Return, Qt::NoModifier);
        QApplication::sendEvent(&sources, &protectedEnter);
        require(choices[2]->isChecked() && changes == 2 && sources.isVisible(),
                "last visible source protected from keyboard without closing");
        sources.actions()[2]->trigger();
        require(choices[2]->isChecked() && changes == 2,
                "direct QAction activation cannot bypass last-visible protection");
        sources.popup(QPoint(30, 30));
        application.processEvents();
        click(choices[0], QPoint(8, choices[0]->height() / 2));
        require(choices[2]->isEnabled(), "newly enabled source releases previous last source");
        sources.setActiveAction(sources.actions().first());
        QKeyEvent enter(QEvent::KeyPress, Qt::Key_Return, Qt::NoModifier);
        QApplication::sendEvent(&sources, &enter);
        require(sources.isVisible() && changes == 4, "keyboard Enter changes visibility without closing");
        sources.actions().last()->trigger();
        require(!sources.isVisible(), "explicit Close closes chooser");
    }

    QStandardItemModel sourceModel;
    auto* root = new QStandardItem("Browse");
    auto* folder = new QStandardItem("Music");
    folder->appendRow(new QStandardItem("Nested playlist"));
    root->appendRow(folder);
    sourceModel.appendRow(root);
    sourceModel.appendRow(new QStandardItem("Tracks"));
    QTreeView view;
    view.setModel(&sourceModel);
    TouchSourceNavigation navigation(&view);
    navigation.enter(root->index());
    navigation.enter(folder->index());
    require(view.rootIndex() == folder->index(), "real native folder navigation enters nested root");
    view.selectionModel()->select(folder->child(0)->index(), QItemSelectionModel::ClearAndSelect);
    view.selectionModel()->clearCurrentIndex();
    view.hide();
    view.show();
    require(view.rootIndex() == folder->index(), "hide/show preserves folder");
    view.setRowHidden(0, QModelIndex(), true);
    require(LibraryInterface::hasHiddenContext(&view), "hidden active root detected without current index");
    navigation.home();
    require(LibraryInterface::hasHiddenContext(&view), "hidden selected source survives root reset detection");
    view.selectionModel()->clear();
    view.setRowHidden(0, QModelIndex(), false);
    navigation.enter(root->index());
    navigation.back();
    require(!navigation.canGoBack() && view.currentIndex() == root->index(), "Back retains folder selection without activation");

    QStandardItemModel lazyModel;
    auto* lazySource = new QStandardItem("Lazy source");
    lazyModel.appendRow(lazySource);
    QTreeView lazyView;
    lazyView.setModel(&lazyModel);
    TouchSourceNavigation lazyNavigation(&lazyView);
    lazyNavigation.enter(lazySource->index());
    require(!lazyNavigation.canGoBack(), "empty lazy source waits for children");
    lazyView.setRowHidden(0, QModelIndex(), true);
    lazyNavigation.home();
    lazySource->appendRow(new QStandardItem("Delayed folder"));
    require(!lazyNavigation.canGoBack(), "hidden source cannot reenter on delayed child insertion");
    lazyView.setRowHidden(0, QModelIndex(), false);
    lazyNavigation.enter(lazySource->index());
    require(lazyNavigation.canGoBack(), "reenabled lazy source enters existing children");
    lazyModel.clear();
    require(!lazyNavigation.canGoBack() && !lazyView.rootIndex().isValid(),
            "model reset clears native navigation safely");

    QStandardItemModel tracks(100, 6);
    tracks.setHorizontalHeaderLabels({"Album", "Key", "Artist", "Last played", "Title", "BPM"});
    QTableView table;
    table.setModel(&tracks);
    table.resize(800, 444);
    table.show();
    table.selectRow(40);
    table.scrollTo(tracks.index(40, 4));
    application.processEvents();
    const int scroll = table.verticalScrollBar()->value();
    const auto selection = table.selectionModel()->selectedRows();
    auto* header = table.horizontalHeader();
    QMap<int, int> widths;
    LibraryInterface::rememberColumnWidths(header, &widths);
    header->resizeSection(4, 247);
    LibraryInterface::initialColumns(header, {4, 2, 5, 1}, {0, 1, 2, 3, 4, 5});
    require(header->logicalIndex(0) == 4 && header->logicalIndex(1) == 2 &&
                    header->logicalIndex(2) == 5 && header->logicalIndex(3) == 1,
            "initial Title Artist BPM Key order");
    require(header->isSectionHidden(3), "Last played initially hidden, not removed");
    int saves = 0;
    auto* dialog = LibraryInterface::arrangeColumns(header, {0, 1, 2, 3, 4, 5}, [&saves] { ++saves; });
    auto* list = dialog->findChild<QListWidget*>();
    application.processEvents();
    require(dialog->windowModality() == Qt::WindowModal &&
                    QApplication::activeModalWidget() == dialog,
            "column chooser blocks competing parent-window edits");
    auto* repeated = LibraryInterface::arrangeColumns(header, {0, 1, 2, 3, 4, 5}, [&saves] { ++saves; });
    require(repeated == dialog, "reopening columns reuses the active chooser");
    list->item(1)->setCheckState(Qt::Unchecked);
    repeated->findChild<QListWidget*>()->item(2)->setCheckState(Qt::Unchecked);
    require(header->isSectionHidden(2) && header->isSectionHidden(5),
            "later checkbox edit cannot resurrect earlier hidden column");
    list->item(1)->setCheckState(Qt::Checked);
    list->item(2)->setCheckState(Qt::Checked);
    QListWidgetItem* lastPlayed = nullptr;
    for (int row = 0; row < list->count(); ++row) {
        if (list->item(row)->data(Qt::UserRole).toInt() == 3) {
            lastPlayed = list->item(row);
        }
    }
    require(lastPlayed, "Last played available in real column chooser");
    lastPlayed->setCheckState(Qt::Checked);
    require(!header->isSectionHidden(3) && saves > 0, "column visibility applies and requests persistence");
    list->setCurrentRow(1);
    for (auto* button : dialog->findChildren<QPushButton*>()) {
        if (button->text() == "Up") {
            button->click();
        }
    }
    require(header->logicalIndex(0) == 2, "touch Up reorders actual header");
    const int movedColumn = list->item(0)->data(Qt::UserRole).toInt();
    const bool moved = list->model()->moveRows(QModelIndex(), 0, 1, QModelIndex(), 3);
    require(moved && header->logicalIndex(2) == movedColumn,
            "native list-model drag move updates actual column order");
    for (int row = 0; row < list->count(); ++row) {
        list->setCurrentRow(row);
        list->item(row)->setCheckState(Qt::Unchecked);
    }
    int visibleColumns = 0;
    for (int column = 0; column < header->count(); ++column) {
        visibleColumns += !header->isSectionHidden(column) ? 1 : 0;
    }
    require(visibleColumns >= 1, "column chooser cannot hide every column");
    require(widths.value(4) == 247, "column arrangement preserves deliberate hidden-column width for serialization");
    require(table.selectionModel()->selectedRows() == selection &&
                    table.verticalScrollBar()->value() == scroll,
            "column edits preserve track selection and vertical scroll");
    dialog->close();

    QMenu decks;
    QMenu original;
    int loads = 0;
    auto* deck = decks.addAction("Deck 2", [&loads] { ++loads; });
    auto* disabled = decks.addAction("Deck 1");
    disabled->setEnabled(false);
    original.addAction("Native context command");
    auto* actions = LibraryInterface::actionsMenu(&table, &decks, &original, [] {});
    require(actions->actions()[0]->text() == "Load" &&
                    actions->actions()[1]->text() == "Arrange columns" &&
                    actions->actions().last()->menu() == &original,
            "approved primary order and original native menu identity");
    auto* load = actions->actions().first()->menu();
    require(load->actions().first() == deck && !load->actions().last()->isEnabled(),
            "deck actions retain native identity and disabled state");
    load->actions().first()->trigger();
    require(loads == 1, "native deck QAction callback invoked once");
    decks.setEnabled(false);
    auto* multi = LibraryInterface::actionsMenu(&table, &decks, &original, [] {});
    require(!multi->actions().first()->isEnabled(), "multi-selection load disabled by native menu state");
    original.setEnabled(false);
    auto* empty = LibraryInterface::actionsMenu(&table, nullptr, &original, [] {});
    require(!empty->actions().first()->isEnabled() && empty->actions()[1]->isEnabled(),
            "empty selection retains Arrange columns without stale deck actions");
    require(LibraryInterface::preferredSourceRow("BrowseFeature",
                    {"TracksFeature", "BrowseFeature"}, {true, true}) == 1,
            "default source resolves stable identity");
    require(LibraryInterface::preferredSourceRow("BrowseFeature",
                    {"BrowseFeature", "TracksFeature"}, {true, true}) == 0,
            "default source survives lazy reordered insertion");
    require(LibraryInterface::preferredSourceRow("BrowseFeature",
                    {"TracksFeature"}, {true}) == -1 &&
                    LibraryInterface::preferredSourceRow("BrowseFeature",
                            {"TracksFeature", "BrowseFeature"}, {true, false}) == -1,
            "absent or hidden default requests safe fallback without rewriting preference");
    require(LibraryInterface::preferredSourceRow("", {"TracksFeature"}, {true}) == -1,
            "unset default preserves prior deliberate model preference");
    if (holdout) {
        tracks.setHeaderData(4, Qt::Horizontal, QString(500, QChar('T')));
        auto* longDialog = LibraryInterface::arrangeColumns(header, {0, 1, 2, 3, 4, 5}, [] {});
        require(longDialog->findChild<QListWidget*>()->count() == 6, "long-title holdout keeps all column identities");
        sourceModel.removeRow(0);
        require(!navigation.canGoBack(), "model removal holdout invalidates navigation safely");
        require(table.selectionModel()->selectedRows() == selection,
                "context selection holdout remains untouched by menus");
        longDialog->close();
    }
    std::cout << "FAILURES " << failures << std::endl;
    return failures ? 1 : 0;
}
