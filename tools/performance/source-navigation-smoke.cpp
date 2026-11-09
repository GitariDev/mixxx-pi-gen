#include "touchsourcenavigation.h"

#include <QApplication>
#include <QStandardItemModel>
#include <iostream>
#include <stdexcept>

void require(bool condition, const char* message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    QStandardItemModel model;
    QTreeView view;
    view.setModel(&model);
    TouchSourceNavigation nav(&view);
    bool backAvailable = false;
    nav.changed = [&](bool available) { backAvailable = available; };
    auto* source = new QStandardItem("Rekordbox");
    auto* drive = new QStandardItem("USB");
    auto* playlists = new QStandardItem("Playlists");
    auto* tracks = new QStandardItem("Set A");
    playlists->appendRow(tracks);
    drive->appendRow(playlists);
    source->appendRow(drive);
    model.appendRow(source);
    auto* lazy = new QStandardItem("Computer");
    model.appendRow(lazy);
    int clicked = 0;
    QObject::connect(&view, &QTreeView::clicked, [&] { ++clicked; });

    // Full-row taps enter a single level. A leaf remains highlighted in its
    // parent rather than replacing the pane with an empty level.
    view.clicked(source->index());
    require(view.rootIndex() == source->index() && backAvailable, "source tap");
    view.clicked(drive->index());
    view.clicked(playlists->index());
    view.setCurrentIndex(tracks->index());
    view.clicked(tracks->index());
    require(view.rootIndex() == playlists->index(), "leaf must not enter empty level");
    const int activations = clicked;
    nav.back();
    require(view.rootIndex() == drive->index(), "back one level");
    require(view.currentIndex() == playlists->index(), "back highlights departed folder");
    require(clicked == activations, "back must not change active track model/search");
    view.hide();
    view.show();
    require(view.rootIndex() == drive->index(), "Show/Hide preserves folder");
    nav.home();
    require(!view.rootIndex().isValid() && !backAvailable, "return home");

    // Synchronous lazy folder population uses the model's normal import hook.
    nav.requestChildren = [&](const QModelIndex& index) {
        if (index == lazy->index() && lazy->rowCount() == 0) {
            lazy->appendRow(new QStandardItem("Music"));
        }
    };
    view.clicked(lazy->index());
    require(view.rootIndex() == lazy->index(), "lazy folder populated before enter");
    nav.home();
    nav.requestChildren = {};

    // Asynchronous imports enter only the requested source. Back cancels a
    // pending request; adding children to some other source must not jump.
    auto* delayed = new QStandardItem("New USB");
    model.appendRow(delayed);
    view.clicked(delayed->index());
    lazy->appendRow(new QStandardItem("Unrelated"));
    require(!view.rootIndex().isValid(), "unrelated insertion steals navigation");
    delayed->appendRow(new QStandardItem("Imported playlist"));
    require(view.rootIndex() == delayed->index(), "async import enters requested source");
    nav.home();
    auto* cancelled = new QStandardItem("Cancelled import");
    model.appendRow(cancelled);
    view.clicked(cancelled->index());
    nav.back();
    cancelled->appendRow(new QStandardItem("Late playlist"));
    require(!view.rootIndex().isValid(), "Back cancels deferred navigation");

    // Removed nodes and same-label replacements cannot inherit pending state.
    nav.enter(source->index());
    nav.enter(drive->index());
    source->removeRow(0);
    require(!view.rootIndex().isValid() && !backAvailable, "removed active device returns home");
    auto* missing = new QStandardItem("Replacement");
    model.appendRow(missing);
    nav.enter(missing->index());
    model.removeRow(missing->row());
    auto* replacement = new QStandardItem("Replacement");
    replacement->appendRow(new QStandardItem("Different music"));
    model.appendRow(replacement);
    require(!view.rootIndex().isValid(), "same-label replacement entered without a tap");
    nav.enter(replacement->index());
    model.clear();
    require(!view.rootIndex().isValid() && !backAvailable, "reset clears invalid roots");

    auto* hidden = new QStandardItem("Hidden");
    hidden->appendRow(new QStandardItem("Nested"));
    model.appendRow(hidden);
    view.setRowHidden(0, QModelIndex(), true);
    nav.enter(hidden->index());
    require(!view.rootIndex().isValid(), "hidden source entered");
    view.setRowHidden(0, QModelIndex(), false);
    nav.reveal(hidden->child(0)->index());
    require(view.rootIndex() == hidden->index(), "programmatic selection reveals parent");
    std::cout << "Source navigation smoke checks passed\n";
}
