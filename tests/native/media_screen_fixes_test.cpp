// Acceptance B repairs (mixxx-media-screen-fixes.patch): the Media page,
// the insert ping and the Safe strip are children of the skin root (the
// widget the skin stylesheet is set on, the main window's central widget),
// and the page opens one event-loop turn after [MixPi],screen is written.
#include <QApplication>
#include <QFile>
#include <QMainWindow>
#include <QTimer>
#include <iostream>

#include "library/mixpimediapage.h"

namespace {
int failures = 0;
int checks = 0;
void check(bool condition, const std::string& message) {
    ++checks;
    if (!condition) {
        ++failures;
        std::cerr << "FAIL " << message << '\n';
    } else {
        std::cout << "PASS " << message << '\n';
    }
}
void settle(int milliseconds = 0) {
    QElapsedTimer timer;
    timer.start();
    do {
        QApplication::processEvents(QEventLoop::AllEvents, 10);
    } while (timer.elapsed() < milliseconds);
}
QColor pixel(QWidget* widget, QPoint point) {
    return widget->grab().toImage().pixelColor(point);
}
} // namespace

int main(int argc, char** argv) {
    QApplication application(argc, argv);
    QString style;
    for (const auto& path : qEnvironmentVariable("MIXPI_SKIN_QSS").split(':', Qt::SkipEmptyParts)) {
        QFile file(path);
        if (file.open(QIODevice::ReadOnly)) {
            style += QString::fromUtf8(file.readAll());
        }
    }
    check(style.contains(QStringLiteral("#MixpiPage")), "the installed menu style has #MixpiPage rules");
    // As MixxxMainWindow: the skin root, carrying the skin stylesheet, is the
    // central widget; the main window itself has no skin style.
    QMainWindow window;
    auto* root = new QWidget;
    root->setObjectName(QStringLiteral("SkinRootDouble"));
    root->setStyleSheet(style);
    window.setCentralWidget(root);
    auto* library = new QWidget(root); // stands in for WLibrary, what m_parent() returns
    window.resize(800, 480);
    window.show();
    settle();
    check(mixpiSkinRoot(library) == root, "skin root: a skin widget resolves to the central widget");

    // Production (MixpiMedia::ensureWidgets): MixpiMediaPage(window(), ...)
    // with window() == mixpiSkinRoot(m_parent()).
    double screen = -1;
    QList<bool> visibleAtWrite;
    MixpiMediaPage* page = nullptr;
    page = new MixpiMediaPage(mixpiSkinRoot(library), [&](double value) {
        screen = value;
        visibleAtWrite.append(page && page->isVisible());
    });
    page->openSoon();
    check(screen == 2 && !page->isVisible(), "open: screen 2 is written first and the page is not shown yet");
    settle();
    check(page->isVisible() && visibleAtWrite.value(0) == false,
            "open: the page shows on the next event-loop turn");
    check(root->children().last() == page, "open: the page is raised above the skin widgets");
    settle(MixpiPage::kRepaintMs + 80);
    check(page->isVisible() && root->children().last() == page, "open: still on top after the repaint");
    check(page->parentWidget() == root && page->geometry() == QRect(0, 48, 800, 432),
            "geometry: under the 48 px top bar of the skin root at 800x480");
    // Bottom left: the drive column (the right column is the #121821 panel).
    const QColor background = pixel(page, QPoint(4, page->height() - 4));
    check(background == QColor(QStringLiteral("#0a0d12")),
            "style: the page resolves the #MixpiPage background from the skin root's stylesheet (" +
                    background.name().toStdString() + ")");
    const QColor header = pixel(page, QPoint(400, 2));
    check(header == QColor(QStringLiteral("#121821")), "style: the header resolves #MixpiPageHeader (" +
                    header.name().toStdString() + ")");
    auto* close = page->closeButton();
    const QColor closeFill = pixel(close, QPoint(4, 24));
    check(closeFill == QColor(QStringLiteral("#19212d")),
            "style: the close button resolves its own rule (" + closeFill.name().toStdString() + ")");

    window.resize(800, 444);
    settle();
    check(page->geometry() == QRect(0, 48, 800, 396), "geometry: follows the skin root to 800x444");
    window.resize(800, 480);
    settle();
    check(page->geometry() == QRect(0, 48, 800, 432), "geometry: and back to 800x480");

    MixpiBottomStrip strip(mixpiSkinRoot(library));
    strip.showSafe(QStringLiteral("d"), QStringLiteral("Spare"));
    settle();
    check(strip.parentWidget() == root && strip.geometry() == QRect(0, 424, 800, 56),
            "strip: a child of the skin root over its bottom 56 px");
    const QColor safe = pixel(&strip, QPoint(400, 40));
    check(safe == QColor(QStringLiteral("#1d7a4a")) || safe == QColor(QStringLiteral("#2fae68")),
            "style: the Safe strip resolves its green from the skin root's stylesheet (" + safe.name().toStdString() + ")");

    // The cause found in acceptance: a page parented to the main window (as
    // build B did) is outside the styled subtree and stays unstyled.
    MixpiPage outside(&window, 2, QStringLiteral("USB & MEDIA"), {}, {});
    outside.open();
    settle();
    const QColor unstyled = pixel(&outside, QPoint(outside.width() - 4, outside.height() - 4));
    check(unstyled != QColor(QStringLiteral("#0a0d12")),
            "cause: a page under the main window does not get the skin root's style (" + unstyled.name().toStdString() + ")");
    outside.closePage();

    page->screenChanged(0);
    check(!page->isVisible(), "a tab tap still closes the page");
    delete page;
    std::cout << checks << " checks, " << failures << " failures\n";
    return failures ? 1 : 0;
}
