#include <QApplication>
#include <QHBoxLayout>
#include <QMouseEvent>
#include <QPushButton>
#include <QTableWidget>
#include <QScrollBar>
#include <QVBoxLayout>
#include <QWheelEvent>
#include <cstdio>
#ifdef USE_OVERLAY
#include "widget/wrightoverlaylayout.h"
#endif

static int failures = 0;
static void check(bool condition, const char* message) {
    if (!condition) {
        std::fprintf(stderr, "FAIL: %s\n", message);
        ++failures;
    }
}

static void click(QWidget& window, QPoint position) {
    QWidget* target = window.childAt(position);
    check(target != nullptr, "hit target exists");
    if (!target) return;
    const QPoint local = target->mapFrom(&window, position);
    QMouseEvent press(QEvent::MouseButtonPress, local, target->mapToGlobal(local),
            Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    QApplication::sendEvent(target, &press);
    QMouseEvent release(QEvent::MouseButtonRelease, local, target->mapToGlobal(local),
            Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    QApplication::sendEvent(target, &release);
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    std::printf("Qt %s platform %s\n", qVersion(), qPrintable(app.platformName()));
    const bool holdout = argc > 1;
    for (int height : {444, 480}) {
        QWidget window;
#ifdef USE_OVERLAY
        auto* layout = new WRightOverlayLayout;
#else
        auto* layout = new QHBoxLayout;
#endif
        layout->setContentsMargins(0, 0, 0, 0);
        layout->setSpacing(0);
        layout->setAlignment(Qt::AlignCenter);
        window.setLayout(layout);
        auto* table = new QTableWidget(200, 4);
        table->setMinimumSize(0, 0);
        for (int column = 0; column < 4; ++column) table->setColumnWidth(column, 200);
        auto* sidebar = new QWidget;
        sidebar->setFixedWidth(290);
        auto* sidebarLayout = new QVBoxLayout(sidebar);
        auto* sources = new QPushButton("Sources");
        auto* back = new QPushButton("Back");
        sidebarLayout->addWidget(sources);
        sidebarLayout->addWidget(back);
        sidebarLayout->addStretch();
        sidebar->hide();
        layout->addWidget(table);
        layout->addWidget(sidebar);
        window.resize(800, height);
        window.show();
        app.processEvents();
        check(sidebar->isHidden(), "initial visibility retained");
        check(table->width() == 800, "hidden table full width");
        table->setCurrentCell(8, 1);
        table->verticalScrollBar()->setValue(3);
        const int scroll = table->verticalScrollBar()->value();
        int clicks = 0;
        QObject::connect(sources, &QPushButton::clicked, [&] { ++clicks; });
        for (int width : {800, 510, 220, 800}) {
            sidebar->show();
            window.resize(width, height);
            app.processEvents();
            check(table->geometry() == window.rect(), "open table full rectangle");
            check(sidebar->geometry() == QRect(qMax(0, width - 290), 0,
                    qMin(width, 290), height), "pane right anchored and clamped");
            if (width > 290) {
                QWidget* hit = window.childAt(10, 100);
                check(hit && (hit == table || table->isAncestorOf(hit)), "outside pane hits table");
            }
            const QPoint buttonPoint = sources->mapTo(&window, sources->rect().center());
            const int previousClicks = clicks;
            click(window, buttonPoint);
            check(clicks == previousClicks + 1, "pane button receives click above table");
            sidebar->hide();
            app.processEvents();
            QWidget* hit = window.childAt(width - 10, 100);
            check(hit && (hit == table || table->isAncestorOf(hit)), "hidden pane restores hit target");
            check(table->currentRow() == 8 && table->currentColumn() == 1,
                    "selection retained");
            check(table->verticalScrollBar()->value() == scroll, "scroll retained");
            table->horizontalScrollBar()->setValue(0);
            click(window, QPoint(width - 80, 100));
            check(table->currentRow() != 8, "hidden pane restores actual table click");
            table->setCurrentCell(8, 1);
            table->verticalScrollBar()->setValue(scroll);
            sidebar->show();
            app.processEvents();
            if (width > 290) {
                const QPoint wheelPosition(60, 100);
                QWidget* wheelTarget = window.childAt(wheelPosition);
                const QPoint local = wheelTarget->mapFrom(&window, wheelPosition);
                QWheelEvent wheel(local, wheelTarget->mapToGlobal(local), QPoint(),
                        QPoint(0, -120), Qt::NoButton, Qt::NoModifier,
                        Qt::NoScrollPhase, false);
                QApplication::sendEvent(wheelTarget, &wheel);
                check(table->verticalScrollBar()->value() > scroll,
                        "outside pane wheel scrolls native table");
                table->verticalScrollBar()->setValue(scroll);
            }
            sidebar->hide();
        }
        if (holdout) {
            layout->setContentsMargins(7, 11, 13, 17);
            window.setLayoutDirection(Qt::RightToLeft);
            for (QSize size : {QSize(1003, 517), QSize(173, 271)}) {
                window.resize(size);
                sidebar->show();
                app.processEvents();
                const QRect content = window.rect().marginsRemoved(QMargins(7, 11, 13, 17));
                check(table->geometry() == content, "holdout base respects margins");
                check(sidebar->geometry().right() == content.right(), "holdout physical right in RTL");
                check(sidebar->width() == qMin(290, content.width()), "holdout narrow clamp");
            }
            sidebar->hide();
            window.hide();
            window.show();
            app.processEvents();
            check(sidebar->isHidden(), "parent show does not reset pane visibility");
        }
    }
    std::printf("%s (%d failures)\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}
