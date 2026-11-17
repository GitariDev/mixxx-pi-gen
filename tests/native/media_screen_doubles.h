#pragma once
// Interface doubles for the media_screen fixture: the parts of the skin
// system that the production widget/wlabel.cpp needs (WBaseWidget,
// SkinContext, WSkinColor). The Label itself is the pinned Mixxx WLabel.
#include <QColor>
#include <QDomElement>
#include <QDomNode>
#include <QString>
#include <QStringList>
#include <QWidget>

class WBaseWidget {
  public:
    explicit WBaseWidget(QWidget* widget)
            : m_widget(widget) {
    }
    virtual ~WBaseWidget() = default;
    void updateTooltip() {
    }
    virtual void fillDebugTooltip(QStringList* debug) {
        Q_UNUSED(debug);
    }
    QWidget* toQWidget() {
        return m_widget;
    }

  private:
    QWidget* m_widget;
};

class SkinContext {
  public:
    double getScaleFactor() const {
        return 1.0;
    }
    static QDomNode selectNode(const QDomNode& node, const QString& name) {
        return node.namedItem(name);
    }
    static QDomElement selectElement(const QDomNode& node, const QString& name) {
        return selectNode(node, name).toElement();
    }
    QString nodeToString(const QDomNode& node) const {
        return node.toElement().text();
    }
    QString selectString(const QDomNode& node, const QString& name) const {
        return nodeToString(selectElement(node, name));
    }
    bool hasNodeSelectString(const QDomNode& node, const QString& name, QString* value) const {
        const auto child = selectNode(node, name);
        if (child.isNull()) {
            return false;
        }
        *value = nodeToString(child);
        return true;
    }
};

class WSkinColor {
  public:
    static QColor getCorrectColor(QColor color) {
        return color;
    }
};
