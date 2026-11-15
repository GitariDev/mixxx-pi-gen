#include <QApplication>
#include <QHeaderView>
#include <QMouseEvent>
#include <QSortFilterProxyModel>
#include <QStandardItemModel>
#include <QTableView>
#include <iostream>
#include "runtime_selection_probe.h"

struct Clicks : QObject {
    int presses = 0;
    int doubles = 0;
    bool eventFilter(QObject*, QEvent* event) override {
        if (event->type() == QEvent::MouseButtonPress) ++presses;
        if (event->type() == QEvent::MouseButtonDblClick) ++doubles;
        return false;
    }
};

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    const bool holdout = application.arguments().contains("holdout");
    QStandardItemModel model(3, 3);
    for (int row = 0; row < 3; ++row) {
        model.setData(model.index(row, 0), "same displayed title");
        model.setData(model.index(row, 1), QString("recording-%1.wav").arg(row));
        model.setData(model.index(row, 2), QString("/synthetic/recording-%1.wav").arg(row));
    }
    QTableView table;
    table.setModel(&model);
    table.resize(400, 180);
    table.show();
    QApplication::processEvents();
    Clicks clicks;
    table.viewport()->installEventFilter(&clicks);
    int failures = 0;
    int checks = 0;
    auto require = [&](bool condition, const char* label) {
        ++checks;
        if (!condition) { ++failures; std::cerr << "FAIL " << label << '\n'; }
    };
    auto request = [](int row, const QString& path) {
        return QJsonObject{{"path", QJsonArray{row}}, {"identityColumn", 2}, {"identityValue", path}};
    };
    auto rejectedWithoutClick = [&](QJsonObject command, const char* label) {
        const auto before = clicks.presses;
        const auto result = selectRuntimeRow(&table, command);
        require(!result.value("success").toBool() && clicks.presses == before, label);
    };
    if (!holdout) {
        table.hideColumn(0);
        auto result = selectRuntimeRow(&table, request(1, "/synthetic/recording-1.wav"));
        require(result.value("success").toBool() && table.currentIndex().row() == 1, "hidden first column selects exact recording");
        require(clicks.presses == 1, "valid selection dispatches one actual press");
        rejectedWithoutClick(request(1, "/synthetic/recording-2.wav"), "wrong row identity");
        rejectedWithoutClick(request(9, "/synthetic/recording-1.wav"), "invalid row");
        model.setData(model.index(2, 2), "/synthetic/recording-1.wav");
        rejectedWithoutClick(request(1, "/synthetic/recording-1.wav"), "ambiguous identity");
        model.setData(model.index(2, 2), "/synthetic/recording-2.wav");
        for (int column = 0; column < 3; ++column) table.hideColumn(column);
        rejectedWithoutClick(request(1, "/synthetic/recording-1.wav"), "all columns hidden sends no click");
        table.showColumn(1);
        table.hideRow(1);
        rejectedWithoutClick(request(1, "/synthetic/recording-1.wav"), "hidden row sends no click");
        table.showRow(1);
        table.setEnabled(false);
        rejectedWithoutClick(request(1, "/synthetic/recording-1.wav"), "disabled table sends no click");
        table.setEnabled(true);
        table.hide();
        rejectedWithoutClick(request(1, "/synthetic/recording-1.wav"), "hidden table sends no click");
        table.show();
        rejectedWithoutClick({{"path", QJsonArray{0.5}}}, "fractional index rejected");
        rejectedWithoutClick({{"path", QJsonArray{-1, 0}}}, "invalid ancestor rejected");
        rejectedWithoutClick({{"path", QJsonArray{1}}, {"identityColumn", 9}, {"identityValue", "wrong"}}, "invalid identity column");
        model.item(1, 1)->setFlags(Qt::ItemIsEnabled);
        rejectedWithoutClick(request(1, "/synthetic/recording-1.wav"), "nonselectable cell sends no click");
        model.item(1, 1)->setFlags(Qt::ItemIsEnabled | Qt::ItemIsSelectable);
        table.setCurrentIndex(model.index(0, 1));
        const auto connection = QObject::connect(table.selectionModel(), &QItemSelectionModel::currentChanged,
                &table, [&](const QModelIndex& current) {
                    if (current.row() == 1) model.setData(model.index(1, 2), "/synthetic/replaced.wav");
                });
        auto command = request(1, "/synthetic/recording-1.wav");
        command.insert("double", true);
        result = selectRuntimeRow(&table, command);
        require(!result.value("success").toBool() && clicks.doubles == 0, "identity changes during selection prevent activation");
        QObject::disconnect(connection);
        model.setData(model.index(1, 2), "/synthetic/recording-1.wav");
        table.setCurrentIndex(model.index(0, 1));
        QStandardItemModel replacement(3, 3);
        const auto replacementConnection = QObject::connect(table.selectionModel(), &QItemSelectionModel::currentChanged,
                &table, [&](const QModelIndex& current) {
                    if (current.row() == 1) {
                        table.setModel(&replacement);
                        table.setCurrentIndex(replacement.index(1, 1));
                    }
                });
        result = selectRuntimeRow(&table, command);
        require(!result.value("success").toBool() && clicks.doubles == 0, "model replacement prevents activation");
        QObject::disconnect(replacementConnection);
    } else {
        QSortFilterProxyModel proxy;
        proxy.setSourceModel(&model);
        proxy.sort(1, Qt::DescendingOrder);
        table.setModel(&proxy);
        table.hideColumn(0);
        table.hideColumn(2);
        QApplication::processEvents();
        rejectedWithoutClick(request(0, "/synthetic/recording-0.wav"), "sorted stale ordinal rejected");
        auto result = selectRuntimeRow(&table, request(0, "/synthetic/recording-2.wav"));
        require(result.value("success").toBool() && proxy.mapToSource(table.currentIndex()).row() == 2, "sorted exact identity selected");
        proxy.setFilterKeyColumn(1);
        proxy.setFilterFixedString("recording-1");
        QApplication::processEvents();
        rejectedWithoutClick(request(0, "/synthetic/recording-2.wav"), "filtered stale identity rejected");
        result = selectRuntimeRow(&table, request(0, "/synthetic/recording-1.wav"));
        require(result.value("success").toBool() && proxy.mapToSource(table.currentIndex()).row() == 1, "filtered exact identity selected");
    }
    std::cout << "Runtime selection " << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
