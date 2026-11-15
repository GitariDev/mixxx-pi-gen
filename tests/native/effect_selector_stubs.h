#pragma once
#include <QDomNode>
#include <QEvent>
#include <QList>
#include <QObject>
#include <QSharedPointer>
#include <QString>
#include <QWidget>

struct EffectManifest {
    QString title;
    QString uniqueId() const { return title; }
    QString displayName() const { return title; }
    QString name() const { return title; }
    QString description() const { return QStringLiteral("Native selector regression"); }
};
using EffectManifestPointer = QSharedPointer<EffectManifest>;
class VisibleEffectsList : public QObject {
    Q_OBJECT
  public:
    QList<EffectManifestPointer> entries;
    QList<EffectManifestPointer> getList() const { return entries; }
  signals:
    void visibleEffectsListChanged();
};
class EffectSlot : public QObject {
    Q_OBJECT
  public:
    EffectManifestPointer manifest;
    int loads = 0;
    EffectManifestPointer getManifest() const { return manifest; }
    void loadEffectWithDefaults(EffectManifestPointer value) {
        ++loads;
        manifest = value;
        emit effectChanged();
    }
  signals:
    void effectChanged();
};
using VisibleEffectsListPointer = QSharedPointer<VisibleEffectsList>;
using EffectSlotPointer = QSharedPointer<EffectSlot>;
using EffectChainPointer = QSharedPointer<int>;
inline const QString kNoEffectString = QStringLiteral("---");
inline constexpr bool kEffectDebugOutput = false;
class EffectsManager {
  public:
    VisibleEffectsListPointer effects = VisibleEffectsListPointer::create();
    EffectSlotPointer slot = EffectSlotPointer::create();
    VisibleEffectsListPointer getVisibleEffectsList() { return effects; }
    EffectsManager* getBackendManager() { return this; }
    EffectManifestPointer getManifestFromUniqueId(const QString& identity) {
        for (auto manifest : effects->entries) if (manifest->uniqueId() == identity) return manifest;
        return {};
    }
};
class SkinContext {};
class EffectWidgetUtils {
  public:
    static inline EffectSlotPointer slot;
    static EffectChainPointer getEffectChainFromNode(const QDomNode&, const SkinContext&, EffectsManager* manager) {
        slot = manager->slot;
        return EffectChainPointer::create(1);
    }
    static EffectSlotPointer getEffectSlotFromNode(const QDomNode&, const SkinContext&, EffectChainPointer) {
        return slot;
    }
};
class WBaseWidget {
  public:
    explicit WBaseWidget(QWidget* widget) : m_widget(widget) {}
    void setBaseTooltip(const QString& value) { m_widget->setToolTip(value); }
    void updateTooltip() {}
  private:
    QWidget* m_widget;
};
struct ConfigKey {
    ConfigKey(const char*, const char*) {}
};
struct ControlObject {
    static inline int refocus = 0;
    static void set(const ConfigKey&, double) { ++refocus; }
};
#define SKIN_WARNING(...) ((void)0)
