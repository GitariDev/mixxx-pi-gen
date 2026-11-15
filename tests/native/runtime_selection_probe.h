#pragma once

#include <QAbstractItemView>
#include <QJsonArray>
#include <QJsonObject>
#include <QPersistentModelIndex>
#include <QPointer>
#include <QTableView>
#include <QTest>

inline QJsonObject selectRuntimeRow(QAbstractItemView* view, const QJsonObject& command) {
    auto refused = [](const QString& reason) {
        return QJsonObject{{"success", false}, {"reason", reason}, {"clicked", false}};
    };
    if (!view || !view->model() || !view->isVisible() || !view->isEnabled()) {
        return refused("View unavailable");
    }
    auto* model = view->model();
    QModelIndex index = view->rootIndex();
    const auto path = command.value("path").toArray();
    if (path.isEmpty()) return refused("No row path");
    for (const auto& value : path) {
        if (!value.isDouble() || value.toDouble() != value.toInt(-1) || value.toInt(-1) < 0) {
            return refused("Invalid row path");
        }
        index = model->index(value.toInt(), 0, index);
        if (!index.isValid()) return refused("Row unavailable");
    }
    QString identity;
    int identityColumn = -1;
    if (command.contains("identityColumn") || command.contains("identityValue")) {
        const auto column = command.value("identityColumn");
        const auto expected = command.value("identityValue");
        if (!column.isDouble() || column.toDouble() != column.toInt(-1) ||
                column.toInt(-1) < 0 || column.toInt() >= model->columnCount(index.parent()) ||
                !expected.isString() || expected.toString().isEmpty()) {
            return refused("Invalid identity assertion");
        }
        identity = index.siblingAtColumn(column.toInt()).data().toString();
        identityColumn = column.toInt();
        if (identity != expected.toString()) return refused("Selected row identity differs");
        int matches = 0;
        for (int row = 0; row < model->rowCount(index.parent()); ++row) {
            if (model->index(row, column.toInt(), index.parent()).data().toString() == identity) ++matches;
        }
        if (matches != 1) return refused("Ambiguous row identity");
    }
    if (auto* table = qobject_cast<QTableView*>(view)) {
        int visibleColumn = -1;
        for (int column = 0; column < model->columnCount(index.parent()); ++column) {
            if (!table->isColumnHidden(column) && table->columnWidth(column) > 0) {
                visibleColumn = column;
                break;
            }
        }
        if (visibleColumn < 0) return refused("No visible column");
        index = index.siblingAtColumn(visibleColumn);
    }
    view->scrollTo(index);
    if (!(index.flags() & Qt::ItemIsEnabled) || !(index.flags() & Qt::ItemIsSelectable)) {
        return refused("Row is not selectable");
    }
    const auto rectangle = view->visualRect(index).intersected(view->viewport()->rect());
    if (rectangle.isEmpty()) return refused("Row has no visible rectangle");
    const QPointer<QAbstractItemView> guard(view);
    const QPersistentModelIndex selected(index);
    const auto point = rectangle.center();
    QTest::mouseClick(view->viewport(), Qt::LeftButton, Qt::NoModifier, point);
    if (!guard || !selected.isValid() || guard->currentIndex().model() != selected.model() ||
            guard->currentIndex().row() != selected.row() ||
            guard->currentIndex().parent() != selected.parent() ||
            (identityColumn >= 0 && QModelIndex(selected).siblingAtColumn(identityColumn).data().toString() != identity)) {
        return {{"success", false}, {"reason", "Click did not select requested row"}, {"clicked", true}};
    }
    if (command.value("double").toBool()) QTest::mouseDClick(guard->viewport(), Qt::LeftButton, Qt::NoModifier, point);
    const bool success = guard && selected.isValid() && guard->currentIndex().model() == selected.model() &&
            guard->currentIndex().row() == selected.row() &&
            guard->currentIndex().parent() == selected.parent() &&
            (identityColumn < 0 || QModelIndex(selected).siblingAtColumn(identityColumn).data().toString() == identity);
    return {{"success", success}, {"clicked", true}, {"row", selected.row()},
            {"column", selected.column()}, {"identity", identity}};
}
