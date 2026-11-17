#pragma once

// LibraryFeature for SidebarModel in the sample_browser and source_groups
// fixtures: a named source with its own child tree. An activation reports
// what it shows, as Library::slotShowTrackModel would.
#include <QFont>
#include <QIcon>
#include <QObject>
#include <QTreeView>
#include <QUrl>
#include <functional>

#include "library/treeitemmodel.h"

class LibraryFeature : public QObject {
    Q_OBJECT
  public:
    QString identity;
    TreeItemModel children;
    int activations = 0;
    explicit LibraryFeature(QString name);
    QVariant title() { return identity; }
    QIcon icon() const { return {}; }
    QString iconName() const { return {}; }
    TreeItemModel* sidebarModel() { return &children; }
    // The list now shown: "Playlists/P", "Tracks", ...
    inline static std::function<void(const QString&)> shown;
    void activate() {
        ++activations;
        if (shown) {
            shown(identity);
        }
    }
    void activateChild(const QModelIndex& index) {
        ++activations;
        if (shown) {
            shown(identity + "/" + index.data().toString());
        }
    }
    void onLazyChildExpandation(const QModelIndex&) {}
    void onRightClick(const QPoint&) {}
    void onRightClickChild(const QPoint&, const QModelIndex&) {}
    void renameItem(const QModelIndex&) {}
    void deleteItem(const QModelIndex&) {}
    void clear() {}
    void paste() {}
    void pasteChild(const QModelIndex&) {}
    void bindLibraryWidget(QWidget*, QObject*) {}
    void bindSidebarWidget(QTreeView*) {}
    bool hasTrackTable() { return true; }
    bool dropAccept(const QList<QUrl>&, QObject*) { return false; }
    bool dropAcceptChild(const QModelIndex&, const QList<QUrl>&, QObject*) { return false; }
    bool dragMoveAccept(const QUrl&) { return false; }
    bool dragMoveAcceptChild(const QModelIndex&, const QUrl&) { return false; }
  signals:
    void featureIsLoading(LibraryFeature*, bool);
    void featureLoadingFinished(LibraryFeature*);
    void featureSelect(LibraryFeature*, const QModelIndex&);
};
