#pragma once

#include <QIcon>
#include <QFont>
#include <QObject>
#include <QUrl>
#include <QTreeView>
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
    // The source last opened: what the track pane shows.
    inline static LibraryFeature* shown = nullptr;
    // The last activation showed a list or a view (Library::slotShowTrackModel
    // or slotSwitchToView). A rekordbox drive whose playlists still load
    // shows nothing yet: showsList false.
    inline static bool listShown = false;
    bool showsList = true;
    void activate() { ++activations; shown = this; listShown = showsList; }
    void activateChild(const QModelIndex&) { ++activations; shown = this; listShown = showsList; }
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

class A final : public LibraryFeature {
    Q_OBJECT
  public:
    A() : LibraryFeature("A") {}
};
class B final : public LibraryFeature {
    Q_OBJECT
  public:
    B() : LibraryFeature("B") {}
};
class C final : public LibraryFeature {
    Q_OBJECT
  public:
    C() : LibraryFeature("C") {}
};
class D final : public LibraryFeature {
    Q_OBJECT
  public:
    D() : LibraryFeature("D") {}
};
class E final : public LibraryFeature {
    Q_OBJECT
  public:
    E() : LibraryFeature("E") {}
};
