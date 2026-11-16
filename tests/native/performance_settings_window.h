#pragma once
#include <QWidget>

// Test double for MixxxMainWindow: only the public slot that the shipping
// settings object invokes by name (PIN src/mixxxmainwindow.h:58-63).
class PreferencesWindow : public QWidget {
    Q_OBJECT
  public:
    int calls = 0;
    bool insideRequest = false;
    bool calledInsideRequest = false;

  public slots:
    void slotOptionsPreferences() {
        ++calls;
        calledInsideRequest = calledInsideRequest || insideRequest;
    }
};
