// Wave J9: lay out the Settings screen tree that zoom_setting_render.py
// evaluated from the generated skin, with plain Qt widgets and the generated
// style.qss, and save an 800x480 PNG (the 48 px top bar left blank).
//
// usage: render TREE.json STYLE.qss OUT.png
#include <QApplication>
#include <QFile>
#include <QFrame>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QPixmap>
#include <QPushButton>
#include <QRegularExpression>
#include <QStackedLayout>
#include <QVBoxLayout>
#include <cstdio>

namespace {

// LegacySkinParser::setupSize: "<n><policy>" per axis; no policy is fixed.
void setupSize(QWidget* pWidget, const QString& size) {
    const QStringList parts = size.split(',');
    if (parts.size() != 2) {
        return;
    }
    static const QRegularExpression pattern(QStringLiteral("^(\\d+)(me|min|max|f|e|i|p)?$"));
    QSizePolicy policy = pWidget->sizePolicy();
    for (int axis = 0; axis < 2; ++axis) {
        const auto match = pattern.match(parts[axis]);
        if (!match.hasMatch()) {
            continue;
        }
        const int value = match.captured(1).toInt();
        const QString kind = match.captured(2);
        QSizePolicy::Policy p = QSizePolicy::Fixed;
        if (kind == QStringLiteral("me")) {
            p = QSizePolicy::MinimumExpanding;
        } else if (kind == QStringLiteral("e")) {
            p = QSizePolicy::Expanding;
        } else if (kind == QStringLiteral("min")) {
            p = QSizePolicy::Minimum;
        } else if (kind == QStringLiteral("max")) {
            p = QSizePolicy::Maximum;
        } else if (kind == QStringLiteral("i")) {
            p = QSizePolicy::Ignored;
        } else if (kind == QStringLiteral("p")) {
            p = QSizePolicy::Preferred;
        }
        if (axis == 0) {
            policy.setHorizontalPolicy(p);
            if (p == QSizePolicy::Fixed) {
                pWidget->setFixedWidth(value);
            } else {
                pWidget->setMinimumWidth(value);
            }
        } else {
            policy.setVerticalPolicy(p);
            if (p == QSizePolicy::Fixed) {
                pWidget->setFixedHeight(value);
            } else {
                pWidget->setMinimumHeight(value);
            }
        }
    }
    pWidget->setSizePolicy(policy);
}

QWidget* build(const QJsonObject& node) {
    const QString kind = node.value(QStringLiteral("kind")).toString();
    QWidget* pWidget = nullptr;
    if (kind == QStringLiteral("group")) {
        auto* pFrame = new QFrame();
        const QString layout = node.value(QStringLiteral("layout")).toString();
        const QJsonArray children = node.value(QStringLiteral("children")).toArray();
        if (layout == QStringLiteral("stacked")) {
            auto* pStack = new QStackedLayout(pFrame);
            pStack->setStackingMode(QStackedLayout::StackAll);
            for (int i = children.size() - 1; i >= 0; --i) {
                pStack->addWidget(build(children[i].toObject()));
            }
            if (pStack->count() > 0) {
                pStack->setCurrentIndex(pStack->count() - 1);
            }
        } else {
            QBoxLayout* pBox = layout == QStringLiteral("horizontal")
                    ? static_cast<QBoxLayout*>(new QHBoxLayout(pFrame))
                    : static_cast<QBoxLayout*>(new QVBoxLayout(pFrame));
            pBox->setContentsMargins(0, 0, 0, 0);
            pBox->setSpacing(0);
            for (const auto& child : children) {
                pBox->addWidget(build(child.toObject()));
            }
        }
        pWidget = pFrame;
    } else if (kind == QStringLiteral("label")) {
        auto* pLabel = new QLabel(node.value(QStringLiteral("text")).toString());
        const QString align = node.value(QStringLiteral("align")).toString();
        if (align == QStringLiteral("center")) {
            pLabel->setAlignment(Qt::AlignCenter);
        } else if (align == QStringLiteral("right")) {
            pLabel->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
        } else {
            pLabel->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
        }
        pWidget = pLabel;
    } else if (kind == QStringLiteral("button")) {
        auto* pButton = new QPushButton(node.value(QStringLiteral("text")).toString());
        pButton->setProperty("value", node.value(QStringLiteral("value")).toInt());
        pButton->setProperty("pressed", false);
        pWidget = pButton;
    } else if (kind == QStringLiteral("slider")) {
        // WSliderComposed with a bar: the bar fills up to the thumb.
        auto* pFrame = new QFrame();
        pFrame->setStyleSheet(QStringLiteral("background: #1d222a; border: 1px solid #3a424e;"));
        auto* pBox = new QHBoxLayout(pFrame);
        pBox->setContentsMargins(0, 0, 0, 0);
        pBox->setSpacing(0);
        auto* pBar = new QFrame();
        pBar->setStyleSheet(QStringLiteral("background: %1; border: 0px;")
                        .arg(node.value(QStringLiteral("bar")).toString()));
        pBox->addWidget(pBar, static_cast<int>(node.value(QStringLiteral("value")).toDouble() * 100));
        pBox->addStretch(100 - static_cast<int>(node.value(QStringLiteral("value")).toDouble() * 100));
        pWidget = pFrame;
    } else {
        pWidget = new QWidget();
    }
    pWidget->setObjectName(node.value(QStringLiteral("name")).toString());
    if (node.contains(QStringLiteral("highlight"))) {
        pWidget->setProperty("highlight", node.value(QStringLiteral("highlight")).toInt());
    }
    if (node.contains(QStringLiteral("enabled"))) {
        pWidget->setEnabled(node.value(QStringLiteral("enabled")).toBool());
    }
    setupSize(pWidget, node.value(QStringLiteral("size")).toString());
    return pWidget;
}

QString readText(const char* path) {
    QFile file(QString::fromLocal8Bit(path));
    if (!file.open(QIODevice::ReadOnly)) {
        qFatal("cannot read %s", path);
    }
    return QString::fromUtf8(file.readAll());
}

} // namespace

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    if (argc != 4) {
        std::fprintf(stderr, "usage: %s TREE.json STYLE.qss OUT.png\n", argv[0]);
        return 2;
    }
    app.setStyleSheet(readText(argv[2]));
    const QJsonObject tree = QJsonDocument::fromJson(readText(argv[1]).toUtf8()).object();
    QFrame window;
    window.setObjectName(QStringLiteral("MixpiRenderWindow"));
    window.setStyleSheet(QStringLiteral("#MixpiRenderWindow { background: #0d1014; }"));
    window.setFixedSize(800, 480);
    auto* pBox = new QVBoxLayout(&window);
    pBox->setContentsMargins(0, 0, 0, 0);
    pBox->setSpacing(0);
    auto* pTop = new QFrame();
    pTop->setFixedHeight(48);
    pBox->addWidget(pTop);
    pBox->addWidget(build(tree));
    window.show();
    app.processEvents();
    // The rows' places, for the record.
    for (QWidget* pChild : window.findChildren<QWidget*>()) {
        const QString name = pChild->objectName();
        if (name.startsWith(QStringLiteral("MixpiSetting")) && pChild->isVisible() &&
                name != QStringLiteral("MixpiSettingText") && name != QStringLiteral("MixpiSettingTitle") &&
                name != QStringLiteral("MixpiSettingLabel")) {
            const QRect place(pChild->mapTo(&window, QPoint(0, 0)), pChild->size());
            std::printf("GEOMETRY %s %d %d %d %d\n", qPrintable(name),
                    place.x(), place.y(), place.width(), place.height());
        }
    }
    if (!window.grab().save(QString::fromLocal8Bit(argv[3]))) {
        return 1;
    }
    return 0;
}
