// The Sources menu's shadow (agreed UI 2d): the patched WRightOverlayLayout
// places a third child, a 40 px strip, against the menu's left edge, over the
// table, and touches pass through it. The page is built as the skin builds
// MixpiBrowseBody: a base (the table with the 320 px room beside it, and a
// plain row under it) and the 320 px menu, then the strip, which carries the
// skin's #MixpiSourcesMenuShadow rule (argv[1]).
#include <QApplication>
#include <QFrame>
#include <QHeaderView>
#include <QHBoxLayout>
#include <QImage>
#include <QMouseEvent>
#include <QPushButton>
#include <QScrollBar>
#include <QTableWidget>
#include <QVBoxLayout>
#include <cstdio>
#include <cstdlib>

#include "widget/wrightoverlaylayout.h"

static int failures = 0;
static void check(bool condition, const char* name) {
    std::printf("%s %s\n", condition ? "PASS" : "FAIL", name);
    if (!condition) {
        ++failures;
    }
}

static QWidget* hit(QWidget& window, QPoint position) {
    return window.childAt(position);
}

static void send(QWidget* target, QWidget& window, QEvent::Type type, QPoint position,
        Qt::MouseButton button, Qt::MouseButtons buttons) {
    const QPoint local = target->mapFrom(&window, position);
    QMouseEvent event(type, local, target->mapToGlobal(local), button, buttons, Qt::NoModifier);
    QApplication::sendEvent(target, &event);
}

static bool near(QRgb pixel, int r, int g, int b) {
    return std::abs(qRed(pixel) - r) <= 3 && std::abs(qGreen(pixel) - g) <= 3 &&
            std::abs(qBlue(pixel) - b) <= 3;
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    std::printf("Qt %s platform %s\n", qVersion(), qPrintable(app.platformName()));
    const QString shadowRule = argc > 1 ? QString::fromUtf8(argv[1]) : QString();
    check(shadowRule.contains("qlineargradient"), "the skin's shadow rule is a plain gradient");
    app.setStyleSheet(shadowRule +
            "QScrollBar:vertical { width: 24px; background: #0d1014; border: 0px; margin: 0px; }"
            "QScrollBar::handle:vertical { min-height: 40px; background: #3a424e; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
            "#Plain { background-color: #1d222a; }"
            "#Room { background-color: #0d1014; }"
            "#Menu { background-color: #161a20; }");

    QWidget window;
    auto* layout = new WRightOverlayLayout;
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);
    window.setLayout(layout);

    auto* base = new QWidget;
    auto* baseLayout = new QVBoxLayout(base);
    baseLayout->setContentsMargins(0, 0, 0, 0);
    baseLayout->setSpacing(0);
    auto* tableRow = new QWidget;
    auto* tableLayout = new QHBoxLayout(tableRow);
    tableLayout->setContentsMargins(0, 0, 0, 0);
    tableLayout->setSpacing(0);
    auto* table = new QTableWidget(60, 4);
    table->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOn);
    table->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    table->setSelectionBehavior(QAbstractItemView::SelectRows);
    table->setSelectionMode(QAbstractItemView::SingleSelection);
    table->setFrameShape(QFrame::NoFrame);
    // The narrowed table fits its columns in its width (spec 2a).
    table->horizontalHeader()->setStretchLastSection(true);
    for (int row = 0; row < 60; ++row) {
        table->setRowHeight(row, 34);
        for (int column = 0; column < 4; ++column) {
            table->setItem(row, column, new QTableWidgetItem(QString::number(row)));
        }
    }
    auto* room = new QWidget;
    room->setObjectName("Room");
    room->setAttribute(Qt::WA_StyledBackground);
    room->setFixedWidth(320);
    tableLayout->addWidget(table);
    tableLayout->addWidget(room);
    auto* plain = new QWidget;
    plain->setObjectName("Plain");
    plain->setAttribute(Qt::WA_StyledBackground);
    plain->setFixedHeight(56);
    baseLayout->addWidget(tableRow);
    baseLayout->addWidget(plain);

    auto* menu = new QWidget;
    menu->setObjectName("Menu");
    menu->setAttribute(Qt::WA_StyledBackground);
    menu->setFixedWidth(320);
    auto* menuLayout = new QVBoxLayout(menu);
    auto* back = new QPushButton("BACK");
    menuLayout->addWidget(back);
    menuLayout->addStretch();

    // WWidgetGroup is a QFrame; the skin gives the strip "40f,0me".
    auto* shadow = new QFrame;
    shadow->setObjectName("MixpiSourcesMenuShadow");
    shadow->setFixedWidth(40);

    layout->addWidget(base);
    layout->addWidget(menu);
    layout->addWidget(shadow);
    window.resize(800, 384);
    window.show();
    app.processEvents();

    check(menu->geometry() == QRect(480, 0, 320, 384), "the menu stays 320 px at x 480-800");
    check(shadow->geometry() == QRect(440, 0, 40, 384),
            "the strip is 40 px against the menu's left edge (x 440-480)");
    check(table->geometry().width() == 480 && table->verticalScrollBar()->isVisible() &&
                    table->verticalScrollBar()->mapTo(&window, QPoint(0, 0)).x() == 456,
            "the table keeps its width; its scroll bar stays at x 456-480");

    // Drawn over the table: the plain #1d222a row darkens toward the menu
    // edge as the mockups draw it, and is untouched left of the strip.
    const QImage image = window.grab().toImage();
    const int y = 384 - 28;
    check(near(image.pixel(420, y), 0x1d, 0x22, 0x2a), "x 420 is not shaded");
    check(near(image.pixel(448, y), 0x1c, 0x21, 0x29), "x 448 reads about #1c2129");
    check(near(image.pixel(456, y), 0x1b, 0x20, 0x28), "x 456 reads about #1b2028");
    check(near(image.pixel(464, y), 0x19, 0x1e, 0x25), "x 464 reads about #191e25");
    check(near(image.pixel(472, y), 0x16, 0x1a, 0x21), "x 472 reads about #161a21");
    check(near(image.pixel(479, y), 0x14, 0x18, 0x1d), "x 479 reads about #14181d");
    check(near(image.pixel(481, y), 0x16, 0x1a, 0x20), "the menu at x 481 is not shaded");
    std::printf("PIXELS 420 %06x 448 %06x 456 %06x 464 %06x 472 %06x 479 %06x 481 %06x\n",
            image.pixel(420, y) & 0xffffff, image.pixel(448, y) & 0xffffff,
            image.pixel(456, y) & 0xffffff, image.pixel(464, y) & 0xffffff,
            image.pixel(472, y) & 0xffffff, image.pixel(479, y) & 0xffffff,
            image.pixel(481, y) & 0xffffff);

    // A tap on a row under the strip selects that row.
    const QRect rowRect = table->visualRect(table->model()->index(3, 0));
    const QPoint rowPoint(448,
            table->viewport()->mapTo(&window, rowRect.center()).y());
    // Sensitivity: a strip that is not transparent for touches takes them.
    check(shadow->testAttribute(Qt::WA_TransparentForMouseEvents),
            "the strip is transparent for touches");
    shadow->setAttribute(Qt::WA_TransparentForMouseEvents, false);
    check(hit(window, rowPoint) == shadow, "control: an opaque strip would take the tap");
    shadow->setAttribute(Qt::WA_TransparentForMouseEvents, true);
    QWidget* rowTarget = hit(window, rowPoint);
    check(rowTarget && (rowTarget == table || table->isAncestorOf(rowTarget)),
            "a tap at the strip on a row hits the table");
    if (rowTarget) {
        send(rowTarget, window, QEvent::MouseButtonPress, rowPoint, Qt::LeftButton, Qt::LeftButton);
        send(rowTarget, window, QEvent::MouseButtonRelease, rowPoint, Qt::LeftButton, Qt::NoButton);
    }
    check(table->currentRow() == 3, "a tap at the strip on a row selects that row");

    // A drag on the scroll bar's handle under the strip scrolls the table.
    QScrollBar* bar = table->verticalScrollBar();
    bar->setValue(0);
    app.processEvents();
    const QPoint barPoint(468, bar->mapTo(&window, QPoint(0, 0)).y() + 10);
    QWidget* barTarget = hit(window, barPoint);
    check(barTarget == bar, "a press at the strip on the scroll bar hits the scroll bar");
    bool down = false;
    if (barTarget) {
        send(barTarget, window, QEvent::MouseButtonPress, barPoint, Qt::LeftButton, Qt::LeftButton);
        down = bar->isSliderDown();
        for (int step = 1; step <= 10; ++step) {
            send(barTarget, window, QEvent::MouseMove, barPoint + QPoint(0, step * 10),
                    Qt::NoButton, Qt::LeftButton);
        }
        send(barTarget, window, QEvent::MouseButtonRelease, barPoint + QPoint(0, 100),
                Qt::LeftButton, Qt::NoButton);
    }
    check(down && bar->value() > 0, "a drag on the scroll bar under the strip scrolls the table");
    std::printf("SCROLL %d of %d\n", bar->value(), bar->maximum());

    // The menu still takes its own taps.
    int backs = 0;
    QObject::connect(back, &QPushButton::clicked, [&] { ++backs; });
    const QPoint backPoint = back->mapTo(&window, back->rect().center());
    QWidget* backTarget = hit(window, backPoint);
    if (backTarget) {
        send(backTarget, window, QEvent::MouseButtonPress, backPoint, Qt::LeftButton, Qt::LeftButton);
        send(backTarget, window, QEvent::MouseButtonRelease, backPoint, Qt::LeftButton, Qt::NoButton);
    }
    check(backs == 1, "the menu's BACK still takes its tap");

    // Hidden with the menu (the skin binds both to screen 1): nothing shaded.
    menu->hide();
    shadow->hide();
    app.processEvents();
    const QImage closed = window.grab().toImage();
    check(near(closed.pixel(479, y), 0x1d, 0x22, 0x2a), "closed: x 479 is not shaded");

    std::printf("FAILURES %d\n", failures);
    return failures ? 1 : 0;
}
