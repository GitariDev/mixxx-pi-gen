#pragma once
// MINIMAL DOUBLES: unrelated model, native menu/deck backend and LibraryControl.
// The production WLibrary TU and Library signal wiring are compiled unchanged.
#include <QTableView>
#include <QStandardItemModel>
#include <QMenu>
#include <QPointer>
#include "library/libraryview.h"
class TrackId { public: bool isValid() const { return true; } };
class WTrackTableView : public QTableView, public LibraryView {
    Q_OBJECT
public:
    QStandardItemModel rows{2, 1};
    QMenu menu{this};
    QString loaded;
    int requests = 0;
    explicit WTrackTableView(QWidget* parent = nullptr) : QTableView(parent) {
        setModel(&rows);
        rows.setData(rows.index(0,0), "synthetic-A");
        rows.setData(rows.index(1,0), "synthetic-B");
        connect(&menu, &QMenu::aboutToHide, this, [this] { emit trackMenuVisible(false); });
    }
    void slotShowHideTrackMenu(bool show) {
        ++requests;
        if (!show) { menu.close(); return; }
        menu.clear();
        auto* load = menu.addAction("Load");
        load->setEnabled(!selectionModel()->selectedRows().isEmpty());
        connect(load, &QAction::triggered, this, [this] {
            const auto selected = selectionModel()->selectedRows();
            if (!selected.isEmpty()) loaded = rows.data(selected.first()).toString();
        });
        menu.addAction("Arrange");
        menu.popup(mapToGlobal(QPoint(0,0)));
        emit trackMenuVisible(true);
    }
    bool isTrackInCurrentView(const TrackId&) { return true; }
    void selectTrack(const TrackId&) { selectRow(0); }
    void slotSaveCurrentViewState() {} void slotRestoreCurrentViewState() {}
signals:
    void trackMenuVisible(bool visible);
};
class LibraryControl : public QObject {
    Q_OBJECT
public:
    bool visible = false;
    void slotUpdateTrackMenuControl(bool value) { visible = value; }
signals:
    void showHideTrackMenu(bool show);
};
