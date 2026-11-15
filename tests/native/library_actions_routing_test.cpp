#include <QApplication>
#include <iostream>
#include <stdexcept>
#include "widget/wlibrary.h"
#include "widget/wtracktableview.h"
#define CHECK(x) do { if (!(x)) throw std::runtime_error(#x); } while (false)
class Nested : public QWidget, public LibraryView {};
int main(int argc, char** argv) {
    QApplication app(argc, argv);
    try {
        WLibrary library(nullptr);
        LibraryControl control;
        auto* m_pLibraryControl = &control;
        auto* m_pLibraryWidget = &library;
        auto* pTrackTableView = new WTrackTableView;
        
        auto connect = [](auto... args) { return QObject::connect(args...); };
        Q_UNUSED(m_pLibraryWidget);
        Q_UNUSED(pTrackTableView);
#include "routing_wiring.inc"
        CHECK(library.registerView("Tracks", pTrackTableView));
        auto* recording = new Nested;
        auto* recordTable = new WTrackTableView(recording);
        CHECK(library.registerView("Recordings", recording));
        auto* browse = new WTrackTableView;
        CHECK(library.registerView("Browse", browse));
        CHECK(library.registerView("Unsupported", new Nested));
        auto* uninitialized = new WTrackTableView;
        uninitialized->setModel(nullptr);
        CHECK(library.registerView("Uninitialized", uninitialized));
        library.resize(640,480); library.show(); app.processEvents();
        // Main table / native menu callback remains owned by that table.
        pTrackTableView->selectRow(0);
        emit control.showHideTrackMenu(true);
        CHECK(pTrackTableView->menu.isVisible()); CHECK(control.visible);
        pTrackTableView->menu.actions().first()->trigger();
        CHECK(pTrackTableView->loaded == "synthetic-A");
        emit control.showHideTrackMenu(false); CHECK(!control.visible);
        // Exact nested Recordings selection; hidden main selection retained.
        library.switchToView("Recordings"); recordTable->selectRow(1);
        const int hiddenRequests = pTrackTableView->requests;
        emit control.showHideTrackMenu(true);
        CHECK(recordTable->menu.isVisible()); CHECK(control.visible);
        CHECK(pTrackTableView->requests == hiddenRequests);
        CHECK(recordTable->menu.actions().first()->isEnabled());
        recordTable->menu.actions().first()->trigger();
        CHECK(recordTable->loaded == "synthetic-B");
        CHECK(pTrackTableView->loaded == "synthetic-A");
        CHECK(pTrackTableView->selectionModel()->selectedRows().first().row() == 0);
        CHECK(recordTable->selectionModel()->selectedRows().first().row() == 1);
        // Switch while open: old menu closes and control resets.
        library.switchToView("Browse"); app.processEvents();
        CHECK(!recordTable->menu.isVisible()); CHECK(!control.visible);
        emit recordTable->trackMenuVisible(true); CHECK(!control.visible);
        emit pTrackTableView->trackMenuVisible(true); CHECK(!control.visible);
        browse->selectRow(0); emit control.showHideTrackMenu(true);
        CHECK(browse->menu.isVisible()); browse->menu.close(); CHECK(!control.visible);
        // Native context-menu feedback also follows the active view.
        browse->slotShowHideTrackMenu(true); CHECK(control.visible);
        browse->menu.close(); CHECK(!control.visible);
        // Empty active table never borrows hidden selections.
        browse->clearSelection(); emit control.showHideTrackMenu(true);
        CHECK(browse->menu.isVisible()); CHECK(!browse->menu.actions().first()->isEnabled());
        library.switchToView("Unsupported");
        emit control.showHideTrackMenu(true); CHECK(!control.visible);
        CHECK(!browse->menu.isVisible()); CHECK(!recordTable->menu.isVisible());
        // A registered table may not yet have loaded its TrackModel. Never
        // invoke its native slot (which initializes WTrackMenu from that model).
        library.switchToView("Uninitialized");
        emit control.showHideTrackMenu(true); CHECK(!control.visible);
        CHECK(uninitialized->requests == 0);
        // Child-table recreation within the same registered nested view.
        library.switchToView("Recordings"); CHECK(uninitialized->requests == 0);
        emit control.showHideTrackMenu(true);
        delete recordTable; app.processEvents(); CHECK(!control.visible);
        recordTable = new WTrackTableView(recording); recordTable->selectRow(0);
        emit control.showHideTrackMenu(true); CHECK(recordTable->menu.isVisible());
        CHECK(control.visible); emit control.showHideTrackMenu(false); CHECK(!control.visible);
        CHECK(recordTable->selectionModel()->selectedRows().first().row() == 0);
        library.switchToView("Tracks");
        CHECK(pTrackTableView->selectionModel()->selectedRows().first().row() == 0);
        emit control.showHideTrackMenu(true); CHECK(pTrackTableView->menu.isVisible());
        pTrackTableView->menu.close(); CHECK(!control.visible);
        if (argc > 1) {
            for (int i = 0; i < 24; ++i) {
                library.switchToView(i % 2 ? "Browse" : "Recordings");
                auto* active = library.getCurrentTrackTableView();
                active->selectRow(i % 2); emit control.showHideTrackMenu(true);
                CHECK(active->menu.isVisible()); CHECK(control.visible);
                active->menu.close(); CHECK(!control.visible);
            }
            // No current widget, including removal of the final view, is safe.
            while (library.count()) { auto* view = library.widget(0); library.removeWidget(view); delete view; }
            emit control.showHideTrackMenu(true); CHECK(!control.visible);
        }
        std::cout << "PASS production routing: Tracks, nested Recordings, Browse, hidden/empty/unsupported, switch, recreation, lifetime, close feedback" << std::endl;
        return 0;
    } catch (const std::exception& e) { std::cerr << "FAIL " << e.what() << std::endl; return 1; }
}
