#pragma once
// ControlObject for the sample_browser and source_groups fixtures. A control
// with a change-request handler sees every set (as a confirm-required
// control does in Mixxx); setAndConfirm stores the value.
#include <QHash>
#include <QString>
#include <functional>

#include "preferences/configobject.h"
#include "util/assert.h"

enum class ControlFlag { None = 0, NoAssertIfMissing = 2, NoWarnIfMissing = 6 };

class ControlObject {
  public:
    ControlObject() = default;
    explicit ControlObject(const ConfigKey& key) : m_key(key.key) {
        registry()[m_key] = this;
    }
    ~ControlObject() {
        if (!m_key.isEmpty() && registry().value(m_key) == this) {
            registry().remove(m_key);
        }
    }
    static QHash<QString, ControlObject*>& registry() {
        static QHash<QString, ControlObject*> controls;
        return controls;
    }
    // Missing and NoWarnIfMissing: none (a skin without the control).
    static ControlObject* getControl(const ConfigKey& key, ControlFlag flag = ControlFlag::None) {
        auto found = registry().find(key.key);
        if (found != registry().end()) {
            return found.value();
        }
        if (flag == ControlFlag::NoWarnIfMissing) {
            return nullptr;
        }
        auto* control = new ControlObject;
        registry()[key.key] = control;
        return control;
    }
    static void set(const ConfigKey& key, double value) {
        getControl(key)->set(value);
    }
    void set(double value) {
        ++writes;
        if (m_readOnly) {
            // As ControlObject::setReadOnly(): its change-request handler
            // drops every set(); only setAndConfirm() changes the value.
            return;
        }
        if (m_request) {
            m_request(value);
        } else {
            m_value = value;
        }
    }
    void setAndConfirm(double value) {
        m_value = value;
    }
    void setReadOnly() {
        m_readOnly = true;
    }
    double get() const {
        return m_value;
    }
    template<typename Receiver, typename Slot>
    void connectValueChangeRequest(Receiver*, Slot slot) {
        m_request = slot;
    }
    void requestChange(double value) {
        if (m_request) {
            m_request(value);
        }
    }
    int writes = 0;
    bool m_readOnly = false;

  private:
    QString m_key;
    double m_value = 0;
    std::function<void(double)> m_request;
};
