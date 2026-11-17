#include <QApplication>
#include <QFile>
#include <QFontInfo>
#include <QImage>
#include <QKeyEvent>
#include <QMouseEvent>
#include <QResource>
#include <QScrollBar>
#include <QSignalBlocker>
#include <QStandardItemModel>
#include <QStyledItemDelegate>
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

int visibleWidth(const QHeaderView* header) {
    int width = 0;
    for (int column = 0; column < header->count(); ++column) {
        width += header->isSectionHidden(column) ? 0 : header->sectionSize(column);
    }
    return width;
}

QList<int> listOrder(const QListWidget* list) {
    QList<int> order;
    for (int row = 0; row < list->count(); ++row) {
        order.append(list->item(row)->data(Qt::UserRole).toInt());
    }
    return order;
}

void send(QWidget* widget, QEvent::Type type, QPoint position, Qt::MouseButtons buttons) {
    QMouseEvent event(type, position, widget->mapToGlobal(position),
            type == QEvent::MouseMove ? Qt::NoButton : Qt::LeftButton, buttons, Qt::NoModifier);
    QApplication::sendEvent(widget, &event);
    QApplication::processEvents();
}

// The option QStyledItemDelegate::paint() hands to the style for a row.
struct RowOption : QStyledItemDelegate {
    using QStyledItemDelegate::initStyleOption;
};

// Columns of pixels that differ between two grabs of the same row.
QPair<int, int> changedColumns(const QImage& a, const QImage& b) {
    int first = -1;
    int last = -1;
    for (int x = 0; x < std::min(a.width(), b.width()); ++x) {
        for (int y = 0; y < std::min(a.height(), b.height()); ++y) {
            if (a.pixel(x, y) != b.pixel(x, y)) {
                first = first < 0 ? x : first;
                last = x;
                break;
            }
        }
    }
    return {first, last};
}

// F-9 (acceptance check 10): in every Arrange row, checked or not, selected or
// not, the label starts right of the check box. Two checks with the real
// skin QSS: the style's own geometry, and the pixels Qt actually paints.
void arrangeRowChecks(QListWidget* list) {
    RowOption rowOption;
    bool geometry = true;
    bool painted = true;
    int rows = 0;
    int unchecked = 0;
    for (int row = 0; row < list->count(); ++row) {
        auto* item = list->item(row);
        list->scrollToItem(item);
        QApplication::processEvents();
        const QRect rect = list->visualItemRect(item);
        QStyleOptionViewItem option;
        option.initFrom(list->viewport());
        option.widget = list;
        option.rect = rect;
        rowOption.initStyleOption(&option, list->model()->index(row, 0));
        auto* style = list->style();
        const QRect check = style->subElementRect(QStyle::SE_ItemViewItemCheckIndicator, &option, list);
        const QRect text = style->subElementRect(QStyle::SE_ItemViewItemText, &option, list);
        geometry &= check.isValid() && text.left() > check.right();

        // Painted: label pixels (grab with and without the text) must start
        // right of the box pixels (grab checked and unchecked) and no further
        // left than the style's text rect. Qt clips the box area when it
        // hands a row to the base style, so a covered label shows up as text
        // pixels that start left of the style's text rect.
        const QSignalBlocker blocker(list);
        auto grab = [&] {
            QApplication::processEvents();
            return list->viewport()->grab(rect).toImage();
        };
        const QImage shown = grab();
        const QString label = item->text();
        item->setText(QString());
        const QImage noText = grab();
        item->setText(label);
        const Qt::CheckState state = item->checkState();
        unchecked += state == Qt::Unchecked ? 1 : 0;
        item->setCheckState(state == Qt::Checked ? Qt::Unchecked : Qt::Checked);
        const QImage toggled = grab();
        item->setCheckState(state);
        const auto labelColumns = changedColumns(shown, noText);
        const auto boxColumns = changedColumns(shown, toggled);
        const bool clear = labelColumns.first >= 0 && boxColumns.first >= 0 &&
                labelColumns.first > boxColumns.second &&
                labelColumns.first >= text.left() - rect.left();
        if (!clear || row < 2) {
            std::cout << "OBSERVE Arrange row " << row << ' ' << label.toStdString()
                      << (state == Qt::Checked ? " checked" : " unchecked")
                      << (list->currentRow() == row ? " selected" : "") << ": box x "
                      << boxColumns.first << ".." << boxColumns.second << ", text x from "
                      << labelColumns.first << " (style: box " << check.left() - rect.left()
                      << ".." << check.right() - rect.left() << ", text from "
                      << text.left() - rect.left() << ')' << std::endl;
        }
        painted &= clear;
        ++rows;
    }
    require(rows > 0 && unchecked > 0, "Arrange rows include unchecked columns");
    require(geometry, "style geometry: every Arrange label starts right of its check box");
    require(painted, "painted pixels: no Arrange check box covers its label, checked or not");
}

// F-9 (council round 1): where the style puts one Arrange row's check box
// (first) and label text (second), in viewport coordinates.
QPair<QRect, QRect> rowRects(QListWidget* list, QListWidgetItem* item) {
    list->scrollToItem(item);
    QApplication::processEvents();
    RowOption rowOption;
    QStyleOptionViewItem option;
    option.initFrom(list->viewport());
    option.widget = list;
    option.rect = list->visualItemRect(item);
    rowOption.initStyleOption(&option, list->model()->index(list->row(item), 0));
    auto* style = list->style();
    return {style->subElementRect(QStyle::SE_ItemViewItemCheckIndicator, &option, list),
            style->subElementRect(QStyle::SE_ItemViewItemText, &option, list)};
}

// The painted check box of one Arrange row.
QImage indicatorImage(QListWidget* list, QListWidgetItem* item) {
    return list->viewport()->grab(rowRects(list, item).first).toImage();
}

// Inside the box border: ink pixels (the tick, #0d1014) and accent fill
// pixels (#a3c45e), spec section 1 (the tick on the accent).
QPair<int, int> tickPixels(const QImage& image) {
    int ink = 0;
    int accent = 0;
    const QRect inside = image.rect().adjusted(5, 5, -5, -5);
    for (int y = inside.top(); y <= inside.bottom(); ++y) {
        for (int x = inside.left(); x <= inside.right(); ++x) {
            const QColor colour = image.pixelColor(x, y);
            accent += colour.green() > 160 && colour.red() > 120 && colour.red() < 200 &&
                            colour.blue() < 130
                    ? 1
                    : 0;
            // Ink only counts where the accent fill is around it (the
            // unchecked box's inside is the dark list surface).
            ink += colour.red() < 40 && colour.green() < 45 && colour.blue() < 45 ? 1 : 0;
        }
    }
    return {accent > 0 ? ink : 0, accent};
}

// F-7 width and F-9 touch dialog/menu, with the real pioneered-menus.qss.
void touchTableChecks() {
    QStandardItemModel model(10, 6);
    model.setHorizontalHeaderLabels({"Album", "Key", "Artist", "Last played", "Title", "BPM"});
    QTableView table;
    table.setModel(&model);
    table.show();
    table.resize(table.width() - table.viewport()->width() + 770, 300);
    QApplication::processEvents();
    auto* header = table.horizontalHeader();
    LibraryInterface::initialColumns(header, {4, 2, 5, 1}, {0, 1, 2, 3, 4, 5});
    LibraryInterface::stretchColumn(header, 4);
    QApplication::processEvents();
    require(table.viewport()->width() == 770 && visibleWidth(header) == 770,
            "at a 770 px viewport the visible columns fill the table with Title");
    header->setSectionHidden(4, true);
    LibraryInterface::stretchColumn(header, 4);
    QApplication::processEvents();
    require(header->stretchLastSection() && visibleWidth(header) == 770,
            "at a 770 px viewport the visible columns fill the table without Title");
    header->setSectionHidden(4, false);
    LibraryInterface::stretchColumn(header, 4);
    QApplication::processEvents();
    require(!header->stretchLastSection() && visibleWidth(header) == 770,
            "Title fills the table again when shown");
    header->resizeSection(2, 700);
    LibraryInterface::stretchColumn(header, 4);
    require(header->sectionSize(4) == LibraryInterface::kStretchColumnMinimumWidth,
            "wide columns never squeeze Title below its minimum width");

    // Mixxx's own compiled-in images (res/mixxx.qrc); the skin style uses
    // :/images/ic_checkmark.svg for the Arrange tick.
    require(QResource::registerResource(qEnvironmentVariable("MIXPI_MIXXX_RCC")) &&
                    QFile::exists(":/images/ic_checkmark.svg"),
            "Mixxx's ic_checkmark.svg resource is available as in the program");
    QFile file(qEnvironmentVariable("MIXPI_MENUS_QSS"));
    require(file.open(QIODevice::ReadOnly), "real pioneered-menus.qss is readable");
    const QString style = QString::fromUtf8(file.readAll());
    require(style.contains("#MixpiColumnArrangement"), "pioneered-menus.qss styles the Arrange dialog");
    // The skin applies its style sheet to the window that hosts the library.
    QWidget window;
    window.setStyleSheet(style);
    auto* layout = new QVBoxLayout(&window);
    auto* actions = new QPushButton("Actions", &window);
    actions->setObjectName("LibraryActionsButton");
    layout->addWidget(actions);
    QStandardItemModel columns(30, 21);
    QStringList titles;
    for (int column = 0; column < 21; ++column) {
        titles.append(QString("Column %1").arg(column));
    }
    columns.setHorizontalHeaderLabels(titles);
    auto* tracks = new QTableView(&window);
    tracks->setModel(&columns);
    layout->addWidget(tracks);
    window.resize(800, 440);
    window.show();
    QApplication::processEvents();

    const QPoint row(10, 10);
    require(LibraryInterface::actionsMenuPosition(tracks, row) ==
                    actions->mapToGlobal(QPoint(0, actions->height())),
            "Actions control opens the menu just under the Actions button");
    actions->hide();
    require(LibraryInterface::actionsMenuPosition(tracks, row) == row,
            "without a visible Actions button the menu keeps the row position");
    actions->show();

    QList<int> all;
    for (int column = 0; column < 21; ++column) {
        all.append(column);
    }
    // Some hidden columns, so the dialog has unchecked rows as well.
    for (int column : {2, 5, 9}) {
        tracks->horizontalHeader()->setSectionHidden(column, true);
    }
    auto* dialog = LibraryInterface::arrangeColumns(tracks->horizontalHeader(), all, [] {});
    QApplication::processEvents();
    require(dialog->size() == QSize(520, 400) && dialog->width() <= 780 && dialog->height() <= 420,
            "Arrange dialog is 520x400, inside the 780x420 float limit");
    auto* list = dialog->findChild<QListWidget*>();
    int shortest = 1000;
    for (int index = 0; index < list->count(); ++index) {
        shortest = std::min(shortest, list->visualItemRect(list->item(index)).height());
    }
    std::cout << "OBSERVE shortest Arrange row " << shortest << " px" << std::endl;
    require(shortest >= 48, "every Arrange list row is at least 48 px high");
    QStringList buttonTexts;
    bool tallButtons = true;
    for (auto* button : dialog->findChildren<QPushButton*>()) {
        buttonTexts.append(button->text());
        tallButtons &= button->height() >= 48;
        std::cout << "OBSERVE button " << button->text().toStdString() << ' '
                  << button->height() << " px" << std::endl;
    }
    require(buttonTexts.contains("Up") && buttonTexts.contains("Down"), "Up and Down buttons stay");
    require(tallButtons, "every Arrange button is at least 48 px high");
    require(QFontInfo(list->font()).pixelSize() == 17, "Arrange list text is 17 px");
    const QImage image = list->viewport()->grab().toImage();
    double luminance = 0;
    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            luminance += qGray(image.pixel(x, y));
        }
    }
    luminance /= image.width() * image.height();
    std::cout << "OBSERVE Arrange list mean grey " << luminance << std::endl;
    require(luminance < 80, "Arrange list background is dark in a grabbed image");
    list->setCurrentRow(1);
    arrangeRowChecks(list);
    list->scrollToTop();
    QApplication::processEvents();

    // Drag to reorder stays: it does not fight the scroll bar or a tap.
    const QList<int> before = listOrder(list);
    auto* bar = list->verticalScrollBar();
    require(bar->maximum() > 0, "Arrange list scrolls with 21 columns");
    const QPoint handle(bar->width() / 2, bar->width() + 4);
    send(bar, QEvent::MouseButtonPress, handle, Qt::LeftButton);
    send(bar, QEvent::MouseMove, handle + QPoint(0, 60), Qt::LeftButton);
    send(bar, QEvent::MouseButtonRelease, handle + QPoint(0, 60), Qt::NoButton);
    require(bar->value() > 0 && listOrder(list) == before,
            "dragging the scroll bar scrolls the list and reorders nothing");
    auto* item = list->itemAt(list->viewport()->rect().center());
    const QRect rect = list->visualItemRect(item);
    const QPoint label(rect.right() - 40, rect.center().y());
    const Qt::CheckState checked = item->checkState();
    const Qt::CheckState other = checked == Qt::Checked ? Qt::Unchecked : Qt::Checked;
    auto* trackHeader = tracks->horizontalHeader();
    const int column = item->data(Qt::UserRole).toInt();
    send(list->viewport(), QEvent::MouseButtonPress, label, Qt::LeftButton);
    send(list->viewport(), QEvent::MouseMove, label + QPoint(4, 3), Qt::LeftButton);
    send(list->viewport(), QEvent::MouseButtonRelease, label + QPoint(4, 3), Qt::NoButton);
    require(list->currentItem() == item && listOrder(list) == before,
            "a tap that moves a few pixels selects the row and reorders nothing");

    // F-9 (council round 1): a tap anywhere on a row, the label too,
    // shows or hides that column; the box itself toggles once, not twice.
    require(item->checkState() == other && trackHeader->isSectionHidden(column) == (other != Qt::Checked),
            "a tap on the label text toggles the row's column");
    const auto [box, textRect] = rowRects(list, item);
    const QPoint labelText(textRect.left() + list->fontMetrics().horizontalAdvance(item->text()) / 2,
            textRect.center().y());
    std::cout << "OBSERVE Arrange tap on the label text at x " << labelText.x() - rect.left()
              << " (box x " << box.left() - rect.left() << ".." << box.right() - rect.left() << ')' << std::endl;
    click(list->viewport(), labelText);
    require(item->checkState() == checked && trackHeader->isSectionHidden(column) == (checked != Qt::Checked),
            "a second tap on the label text toggles it back");
    click(list->viewport(), box.center());
    require(item->checkState() == other, "a tap on the check box toggles it once");
    click(list->viewport(), box.center());
    require(item->checkState() == checked, "a second tap on the check box toggles it back");
    QKeyEvent space(QEvent::KeyPress, Qt::Key_Space, Qt::NoModifier, " ");
    list->setCurrentItem(item);
    QApplication::sendEvent(list, &space);
    QApplication::processEvents();
    require(item->checkState() == other, "Space on the current row still toggles it");
    QApplication::sendEvent(list, &space);
    QApplication::processEvents();
    require(item->checkState() == checked && listOrder(list) == before,
            "the row taps change no order");

    // F-9 (council round 1), spec section 1: a checked box shows a clear
    // tick, the skin's mixpi-icon-tick.svg: ink tick pixels on the accent
    // fill, which an unchecked box does not have.
    QListWidgetItem* tickedItem = nullptr;
    QListWidgetItem* emptyItem = nullptr;
    for (int row = 0; row < list->count(); ++row) {
        auto* candidate = list->item(row);
        if (candidate != list->currentItem()) {
            (candidate->checkState() == Qt::Checked ? tickedItem : emptyItem) = candidate;
        }
    }
    require(tickedItem && emptyItem, "the Arrange list has a checked and an unchecked row");
    if (tickedItem && emptyItem) {
        const QImage ticked = indicatorImage(list, tickedItem);
        const QImage empty = indicatorImage(list, emptyItem);
        const auto tick = tickPixels(ticked);
        const auto none = tickPixels(empty);
        std::cout << "OBSERVE checked box " << ticked.width() << 'x' << ticked.height()
                  << ": tick " << tick.first << " px, fill " << tick.second << " px; unchecked box: tick "
                  << none.first << " px, fill " << none.second << " px" << std::endl;
        const auto evidence = qEnvironmentVariable("MIXPI_ARRANGE_GRAB_DIR");
        if (!evidence.isEmpty()) {
            ticked.save(evidence + "/arrange-checked-box.png");
            empty.save(evidence + "/arrange-unchecked-box.png");
            dialog->grab().save(evidence + "/arrange-dialog.png");
        }
        require(ticked != empty, "checked and unchecked boxes look different in a grab");
        require(tick.first >= 20 && tick.second >= 40,
                "a checked box shows an ink tick on the accent");
        require(none.second == 0, "an unchecked box has no tick");
    }
    dialog->close();

    // Menu rows: the Actions menu and the chooser checkbox rows.
    auto* menu = LibraryInterface::actionsMenu(&window, nullptr, new QMenu("Native", &window), [] {});
    LibraryInterface::addVisibilityChoice(menu, "Tracks", true, [](bool) {});
    menu->popup(actions->mapToGlobal(QPoint(0, actions->height())));
    QApplication::processEvents();
    int shortestMenuRow = 1000;
    for (auto* action : menu->actions()) {
        if (!action->isSeparator()) {
            shortestMenuRow = std::min(shortestMenuRow, menu->actionGeometry(action).height());
        }
    }
    std::cout << "OBSERVE shortest menu row " << shortestMenuRow << " px" << std::endl;
    require(shortestMenuRow >= 48, "every menu row is at least 48 px high");
    menu->close();
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
    if (!baseline) {
        touchTableChecks();
    }
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
